#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import BooleanAttribute, MapAttribute, NumberAttribute
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
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
from ..types.bundle_component import BundleComponentListType, BundleComponentType
from ..utils.normalization import normalize_to_json
from .utils import (
    validate_bundle_exists,
    validate_item_exists,
    validate_provider_item_exists,
)


class BundleUuidIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "bundle_uuid-index"

    partition_key = UnicodeAttribute(hash_key=True)
    bundle_uuid = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UTCDateTimeAttribute(range_key=True)


class BundleComponentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-bundle_components"

    partition_key = UnicodeAttribute(hash_key=True)
    bundle_component_uuid = UnicodeAttribute(range_key=True)
    bundle_uuid = UnicodeAttribute()
    item_uuid = UnicodeAttribute()
    provider_item_uuid = UnicodeAttribute(null=True)
    component_role = UnicodeAttribute(null=True)
    required = BooleanAttribute(default=True)
    default_qty = NumberAttribute(null=True)
    sort_order = NumberAttribute(null=True)
    extra = MapAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    bundle_uuid_index = BundleUuidIndex()
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
                    entity_keys["bundle_component_uuid"] = getattr(
                        entity, "bundle_component_uuid", None
                    )
                    entity_keys["bundle_uuid"] = getattr(entity, "bundle_uuid", None)
                if not entity_keys.get("bundle_component_uuid"):
                    entity_keys["bundle_component_uuid"] = kwargs.get(
                        "bundle_component_uuid"
                    )
                if not entity_keys.get("bundle_uuid"):
                    entity_keys["bundle_uuid"] = kwargs.get("bundle_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="bundle_component",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=2,
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
    cache_name=Config.get_cache_name("models", "bundle_component"),
    cache_enabled=Config.is_cache_enabled,
)
def get_bundle_component(
    partition_key: str, bundle_component_uuid: str
) -> BundleComponentModel:
    return BundleComponentModel.get(partition_key, bundle_component_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_bundle_component(
    partition_key: str, bundle_component_uuid: str
) -> BundleComponentModel:
    return BundleComponentModel.get(partition_key, bundle_component_uuid)


def get_bundle_component_count(partition_key: str, bundle_component_uuid: str) -> int:
    return BundleComponentModel.count(
        partition_key,
        BundleComponentModel.bundle_component_uuid == bundle_component_uuid,
    )


def get_bundle_component_type(
    info: ResolveInfo, component: BundleComponentModel
) -> BundleComponentType:
    _ = info
    component_dict = component.__dict__["attribute_values"].copy()
    return BundleComponentType(**normalize_to_json(component_dict))


def resolve_bundle_component(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> BundleComponentType | None:
    partition_key = info.context.get("partition_key")
    count = get_bundle_component_count(partition_key, kwargs["bundle_component_uuid"])
    if count == 0:
        return None
    return get_bundle_component_type(
        info, get_bundle_component(partition_key, kwargs["bundle_component_uuid"])
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "bundle_component_uuid",
        "bundle_uuid",
        "item_uuid",
        "provider_item_uuid",
        "status",
        "updated_at",
    ],
    list_type_class=BundleComponentListType,
    type_funct=get_bundle_component_type,
)
def resolve_bundle_component_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    bundle_uuid = kwargs.get("bundle_uuid")
    item_uuid = kwargs.get("item_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    component_role = kwargs.get("component_role")
    status = kwargs.get("status")

    args = []
    inquiry_funct = BundleComponentModel.scan
    count_funct = BundleComponentModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = BundleComponentModel.updated_at_index.query
        count_funct = BundleComponentModel.updated_at_index.count
        if bundle_uuid and args[1] is None:
            args[1] = BundleComponentModel.bundle_uuid == bundle_uuid
            inquiry_funct = BundleComponentModel.bundle_uuid_index.query
            count_funct = BundleComponentModel.bundle_uuid_index.count

    the_filters = None
    if item_uuid:
        the_filters &= BundleComponentModel.item_uuid == item_uuid
    if provider_item_uuid:
        the_filters &= BundleComponentModel.provider_item_uuid == provider_item_uuid
    if component_role:
        the_filters &= BundleComponentModel.component_role == component_role
    if status:
        the_filters &= BundleComponentModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def validate_bundle_component_for_bundle(
    partition_key: str, bundle_uuid: str, bundle_component_uuid: str
) -> bool:
    if get_bundle_component_count(partition_key, bundle_component_uuid) == 0:
        return False
    component = get_bundle_component(partition_key, bundle_component_uuid)
    return component.bundle_uuid == bundle_uuid


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "bundle_component_uuid",
    },
    model_funct=_get_bundle_component,
    count_funct=get_bundle_component_count,
    type_funct=get_bundle_component_type,
)
@purge_cache()
def insert_update_bundle_component(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = kwargs.get("partition_key") or info.context.get("partition_key")

    bundle_uuid = kwargs.get("bundle_uuid")
    if bundle_uuid and not validate_bundle_exists(partition_key, bundle_uuid):
        raise ValueError(f"bundle_uuid '{bundle_uuid}' does not exist")

    item_uuid = kwargs.get("item_uuid")
    if item_uuid and not validate_item_exists(partition_key, item_uuid):
        raise ValueError(f"item_uuid '{item_uuid}' does not exist")

    provider_item_uuid = kwargs.get("provider_item_uuid")
    if provider_item_uuid and not validate_provider_item_exists(
        partition_key, provider_item_uuid
    ):
        raise ValueError(f"provider_item_uuid '{provider_item_uuid}' does not exist")

    if kwargs.get("entity") is None:
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "bundle_uuid",
            "item_uuid",
            "provider_item_uuid",
            "component_role",
            "required",
            "default_qty",
            "sort_order",
            "extra",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        BundleComponentModel(
            partition_key, kwargs["bundle_component_uuid"], **cols
        ).save()
        return

    component = kwargs.get("entity")
    actions = [
        BundleComponentModel.updated_by.set(kwargs["updated_by"]),
        BundleComponentModel.updated_at.set(pendulum.now("UTC")),
    ]
    field_map = {
        "bundle_uuid": BundleComponentModel.bundle_uuid,
        "item_uuid": BundleComponentModel.item_uuid,
        "provider_item_uuid": BundleComponentModel.provider_item_uuid,
        "component_role": BundleComponentModel.component_role,
        "required": BundleComponentModel.required,
        "default_qty": BundleComponentModel.default_qty,
        "sort_order": BundleComponentModel.sort_order,
        "extra": BundleComponentModel.extra,
        "status": BundleComponentModel.status,
    }
    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))
    component.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "bundle_component_uuid",
    },
    model_funct=get_bundle_component,
)
@purge_cache()
def delete_bundle_component(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
