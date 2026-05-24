#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import (
    MapAttribute,
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
from ..types.cancellation_policy import (
    CancellationPolicyListType,
    CancellationPolicyType,
)
from ..utils.normalization import normalize_to_json


class ProviderItemUuidIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "provider_item_uuid-index"

    partition_key = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class CancellationPolicyModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-cancellation_policies"

    partition_key = UnicodeAttribute(hash_key=True)
    policy_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute(null=True)
    label = UnicodeAttribute(null=True)
    description = UnicodeAttribute(null=True)
    tiers = MapAttribute(null=True)
    notes_template_uuid = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
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
                    entity_keys["policy_uuid"] = getattr(entity, "policy_uuid", None)
                if not entity_keys.get("policy_uuid"):
                    entity_keys["policy_uuid"] = kwargs.get("policy_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="cancellation_policy",
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
    cache_name=Config.get_cache_name("models", "cancellation_policy"),
    cache_enabled=Config.is_cache_enabled,
)
def get_cancellation_policy(partition_key: str, policy_uuid: str) -> CancellationPolicyModel:
    return CancellationPolicyModel.get(partition_key, policy_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_cancellation_policy(partition_key: str, policy_uuid: str) -> CancellationPolicyModel:
    return CancellationPolicyModel.get(partition_key, policy_uuid)


def get_cancellation_policy_count(partition_key: str, policy_uuid: str) -> int:
    return CancellationPolicyModel.count(
        partition_key, CancellationPolicyModel.policy_uuid == policy_uuid
    )


def get_cancellation_policy_type(
    info: ResolveInfo, policy: CancellationPolicyModel
) -> CancellationPolicyType:
    _ = info
    policy_dict = policy.__dict__["attribute_values"].copy()
    return CancellationPolicyType(**normalize_to_json(policy_dict))


def resolve_cancellation_policy(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> CancellationPolicyType | None:
    partition_key = info.context.get("partition_key")
    count = get_cancellation_policy_count(partition_key, kwargs["policy_uuid"])
    if count == 0:
        return None
    return get_cancellation_policy_type(
        info,
        get_cancellation_policy(partition_key, kwargs["policy_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "policy_uuid",
        "provider_item_uuid",
        "status",
        "updated_at",
    ],
    list_type_class=CancellationPolicyListType,
    type_funct=get_cancellation_policy_type,
)
def resolve_cancellation_policy_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    status = kwargs.get("status")

    args = []
    inquiry_funct = CancellationPolicyModel.scan
    count_funct = CancellationPolicyModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = CancellationPolicyModel.updated_at_index.query
        count_funct = CancellationPolicyModel.updated_at_index.count
        if provider_item_uuid:
            count_funct = CancellationPolicyModel.provider_item_uuid_index.count
            args[1] = (
                CancellationPolicyModel.provider_item_uuid == provider_item_uuid
            )
            inquiry_funct = CancellationPolicyModel.provider_item_uuid_index.query

    the_filters = None
    if status:
        the_filters &= CancellationPolicyModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "policy_uuid",
    },
    model_funct=_get_cancellation_policy,
    count_funct=get_cancellation_policy_count,
    type_funct=get_cancellation_policy_type,
)
@purge_cache()
def insert_update_cancellation_policy(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    if kwargs.get("entity") is None:
        partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_item_uuid",
            "label",
            "description",
            "tiers",
            "notes_template_uuid",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        CancellationPolicyModel(
            partition_key,
            kwargs["policy_uuid"],
            **cols,
        ).save()
        return

    policy = kwargs.get("entity")
    actions = [
        CancellationPolicyModel.updated_by.set(kwargs["updated_by"]),
        CancellationPolicyModel.updated_at.set(pendulum.now("UTC")),
    ]

    field_map = {
        "provider_item_uuid": CancellationPolicyModel.provider_item_uuid,
        "label": CancellationPolicyModel.label,
        "description": CancellationPolicyModel.description,
        "tiers": CancellationPolicyModel.tiers,
        "notes_template_uuid": CancellationPolicyModel.notes_template_uuid,
        "status": CancellationPolicyModel.status,
    }

    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    policy.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "policy_uuid",
    },
    model_funct=get_cancellation_policy,
)
@purge_cache()
def delete_cancellation_policy(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
