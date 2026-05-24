#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import traceback
from typing import Any, Callable, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import (
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.external_system_config import (
    ExternalSystemConfigListType,
    ExternalSystemConfigType,
)
from ..utils.normalization import normalize_to_json

_SECRET_RESOLVER: Callable[[str], str | None] | None = None

class SystemProviderIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "system_provider_index"

    partition_key = UnicodeAttribute(hash_key=True)
    system_provider_key = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ExternalSystemConfigModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-external_system_configs"

    partition_key = UnicodeAttribute(hash_key=True)
    config_uuid = UnicodeAttribute(range_key=True)
    system_code = UnicodeAttribute()
    system_kind = UnicodeAttribute()
    namespace = UnicodeAttribute(default="DEFAULT")
    provider_corp_external_id = UnicodeAttribute(null=True)
    system_provider_key = UnicodeAttribute()
    endpoint_url = UnicodeAttribute()
    adapter_id = UnicodeAttribute(null=True)
    auth_strategy = UnicodeAttribute()
    # Plaintext credential. WRITE-ONLY via GraphQL: accepted on mutations, but stripped
    # from ExternalSystemConfigType in get_external_system_config_type() so it never
    # leaves the engine through the API. Handlers read it via resolve_credential_for().
    auth_secret_value = UnicodeAttribute(null=True)
    # External secrets-manager ARN / SSM path. Used only when auth_secret_value is null.
    auth_secret_ref = UnicodeAttribute(null=True)
    timeout_seconds = NumberAttribute(default=30)
    cache_ttl_seconds = NumberAttribute(default=300)
    extra_config = MapAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    system_provider_index = SystemProviderIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                result = original_function(*args, **kwargs)
                from ..models.cache import purge_entity_cascading_cache

                entity_keys = {}
                entity = kwargs.get("entity")
                if entity:
                    entity_keys["config_uuid"] = getattr(entity, "config_uuid", None)
                if not entity_keys.get("config_uuid"):
                    entity_keys["config_uuid"] = kwargs.get("config_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="external_system_config",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=1,
                )
                return result
            except Exception as e:
                log = traceback.format_exc()
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "external_system_config"),
    cache_enabled=Config.is_cache_enabled,
)
def get_external_system_config(
    partition_key: str, config_uuid: str
) -> ExternalSystemConfigModel:
    return ExternalSystemConfigModel.get(partition_key, config_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_external_system_config(
    partition_key: str, config_uuid: str
) -> ExternalSystemConfigModel:
    return ExternalSystemConfigModel.get(partition_key, config_uuid)


def get_external_system_config_count(partition_key: str, config_uuid: str) -> int:
    return ExternalSystemConfigModel.count(
        partition_key, ExternalSystemConfigModel.config_uuid == config_uuid
    )


def get_external_system_config_type(
    info: ResolveInfo, config: ExternalSystemConfigModel
) -> ExternalSystemConfigType:
    """
    Build the GraphQL output type for a config row.

    SECURITY: `auth_secret_value` is stripped here so it can never reach the
    GraphQL response, even if `ExternalSystemConfigType` is later extended.
    Handlers must use `resolve_credential_for()` to read the credential.
    """
    _ = info
    config_dict = config.__dict__["attribute_values"].copy()
    config_dict.pop("auth_secret_value", None)
    return ExternalSystemConfigType(**normalize_to_json(config_dict))


def register_secret_resolver(resolver: Callable[[str], str | None] | None) -> None:
    global _SECRET_RESOLVER
    _SECRET_RESOLVER = resolver


def resolve_credential_for(config: ExternalSystemConfigModel) -> str | None:
    """
    Read the credential for a config row at handler call time.

    Resolution order:
      1. `auth_secret_ref` resolved through a registered backend.
      2. `auth_secret_value` only when explicitly enabled for local/test execution.
      3. `None` (handler must surface a structured `auth_unavailable` error).

    Callers MUST NOT log or return the result. The string lives in memory only
    for the duration of the outbound call.
    """
    inline = getattr(config, "auth_secret_value", None)
    ref = getattr(config, "auth_secret_ref", None)
    if ref and _SECRET_RESOLVER is not None:
        return _SECRET_RESOLVER(ref)
    if inline and Config.allow_inline_auth_secret_value():
        return inline
    return None


def resolve_external_system_config(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ExternalSystemConfigType | None:
    partition_key = info.context.get("partition_key")
    count = get_external_system_config_count(partition_key, kwargs["config_uuid"])
    if count == 0:
        return None
    return get_external_system_config_type(
        info,
        get_external_system_config(partition_key, kwargs["config_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "config_uuid",
        "system_code",
        "system_kind",
        "namespace",
        "status",
        "updated_at",
    ],
    list_type_class=ExternalSystemConfigListType,
    type_funct=get_external_system_config_type,
)
def resolve_external_system_config_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    system_code = kwargs.get("system_code")
    system_kind = kwargs.get("system_kind")
    namespace = kwargs.get("namespace")
    status = kwargs.get("status")

    args = []
    inquiry_funct = ExternalSystemConfigModel.scan
    count_funct = ExternalSystemConfigModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = ExternalSystemConfigModel.updated_at_index.query
        count_funct = ExternalSystemConfigModel.updated_at_index.count

    the_filters = None
    if system_code:
        the_filters &= ExternalSystemConfigModel.system_code == system_code
    if system_kind:
        the_filters &= ExternalSystemConfigModel.system_kind == system_kind
    if namespace:
        the_filters &= ExternalSystemConfigModel.namespace == namespace
    if status:
        the_filters &= ExternalSystemConfigModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def _build_system_provider_key(system_kind, system_code, namespace, provider_corp_external_id):
    provider = provider_corp_external_id or "DEFAULT"
    return f"{system_kind}#{system_code}#{namespace}#{provider}"


def resolve_external_system_model_for(
    info: ResolveInfo,
    system_kind: str,
    system_code: str,
    namespace: str = "DEFAULT",
    provider_corp_external_id: str = None,
) -> ExternalSystemConfigModel | None:
    """
    Internal resolver returning the raw model row (including ``auth_secret_value``).

    INTERNAL USE ONLY. Handlers call this to read credentials; the returned model
    must never be passed back to GraphQL callers — use
    ``resolve_external_system_for`` for the API surface, which strips the
    credential via ``get_external_system_config_type``.
    """
    partition_key = info.context.get("partition_key")
    candidate_keys = [
        _build_system_provider_key(
            system_kind, system_code, namespace, provider_corp_external_id
        ),
        _build_system_provider_key(system_kind, system_code, namespace, None),
    ]
    if system_kind != "both":
        candidate_keys.extend(
            [
                _build_system_provider_key(
                    "both", system_code, namespace, provider_corp_external_id
                ),
                _build_system_provider_key("both", system_code, namespace, None),
            ]
        )

    for key in dict.fromkeys(candidate_keys):
        configs = ExternalSystemConfigModel.system_provider_index.query(
            partition_key,
            ExternalSystemConfigModel.system_provider_key == key,
            filter_condition=ExternalSystemConfigModel.status == "active",
        )
        for config in configs:
            return config
    return None


def resolve_external_system_for(
    info: ResolveInfo,
    system_kind: str,
    system_code: str,
    namespace: str = "DEFAULT",
    provider_corp_external_id: str = None,
) -> ExternalSystemConfigType | None:
    """
    Public resolver returning the credential-stripped GraphQL type.

    Use this everywhere except inside catalog/availability handlers — those need
    ``resolve_external_system_model_for`` to read ``auth_secret_value``.
    """
    config = resolve_external_system_model_for(
        info,
        system_kind=system_kind,
        system_code=system_code,
        namespace=namespace,
        provider_corp_external_id=provider_corp_external_id,
    )
    if config is None:
        return None
    return get_external_system_config_type(info, config)


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "config_uuid",
    },
    model_funct=_get_external_system_config,
    count_funct=get_external_system_config_count,
    type_funct=get_external_system_config_type,
)
@purge_cache()
def insert_update_external_system_config(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> None:
    if (
        kwargs.get("auth_secret_value") not in (None, "null", "")
        and not Config.allow_inline_auth_secret_value()
    ):
        raise ValueError(
            "auth_secret_value is disabled; provide auth_secret_ref or enable local/test inline secrets"
        )
    if kwargs.get("entity") is None:
        partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
        config_uuid = kwargs.get("config_uuid")
        system_code = kwargs.get("system_code", "")
        system_kind = kwargs.get("system_kind", "")
        namespace = kwargs.get("namespace", "DEFAULT")
        provider_corp_external_id = kwargs.get("provider_corp_external_id")
        system_provider_key = _build_system_provider_key(
            system_kind, system_code, namespace, provider_corp_external_id
        )

        cols = {
            "updated_by": kwargs["updated_by"],
            "system_code": system_code,
            "system_kind": system_kind,
            "namespace": namespace,
            "provider_corp_external_id": provider_corp_external_id,
            "system_provider_key": system_provider_key,
            "endpoint_url": kwargs.get("endpoint_url", ""),
            "auth_strategy": kwargs.get("auth_strategy", "none"),
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "adapter_id",
            "auth_secret_value",
            "auth_secret_ref",
            "timeout_seconds",
            "cache_ttl_seconds",
            "extra_config",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        ExternalSystemConfigModel(
            partition_key,
            config_uuid,
            **cols,
        ).save()
        return

    config = kwargs.get("entity")
    actions = [
        ExternalSystemConfigModel.updated_by.set(kwargs["updated_by"]),
        ExternalSystemConfigModel.updated_at.set(pendulum.now("UTC")),
    ]

    field_map = {
        "system_code": ExternalSystemConfigModel.system_code,
        "system_kind": ExternalSystemConfigModel.system_kind,
        "namespace": ExternalSystemConfigModel.namespace,
        "provider_corp_external_id": ExternalSystemConfigModel.provider_corp_external_id,
        "endpoint_url": ExternalSystemConfigModel.endpoint_url,
        "adapter_id": ExternalSystemConfigModel.adapter_id,
        "auth_strategy": ExternalSystemConfigModel.auth_strategy,
        "auth_secret_value": ExternalSystemConfigModel.auth_secret_value,
        "auth_secret_ref": ExternalSystemConfigModel.auth_secret_ref,
        "timeout_seconds": ExternalSystemConfigModel.timeout_seconds,
        "cache_ttl_seconds": ExternalSystemConfigModel.cache_ttl_seconds,
        "extra_config": ExternalSystemConfigModel.extra_config,
        "status": ExternalSystemConfigModel.status,
    }

    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Recompute system_provider_key if component fields changed
    if any(
        k in kwargs
        for k in ("system_kind", "system_code", "namespace", "provider_corp_external_id")
    ):
        sc = kwargs.get("system_code", getattr(config, "system_code", ""))
        sk = kwargs.get("system_kind", getattr(config, "system_kind", ""))
        ns = kwargs.get("namespace", getattr(config, "namespace", "DEFAULT"))
        pid = kwargs.get(
            "provider_corp_external_id",
            getattr(config, "provider_corp_external_id", None),
        )
        actions.append(
            ExternalSystemConfigModel.system_provider_key.set(
                _build_system_provider_key(sk, sc, ns, pid)
            )
        )

    config.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "config_uuid",
    },
    model_funct=get_external_system_config,
)
@purge_cache()
def delete_external_system_config(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
