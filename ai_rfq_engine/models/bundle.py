#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import MapAttribute, UnicodeAttribute, UTCDateTimeAttribute
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
from ..types.bundle import BundleListType, BundleType
from ..utils.normalization import normalize_to_json
from .bundle_component import resolve_bundle_component_list


class BundleCodeIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "bundle_code-index"

    partition_key = UnicodeAttribute(hash_key=True)
    bundle_code = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UTCDateTimeAttribute(range_key=True)


class BundleModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-bundles"

    partition_key = UnicodeAttribute(hash_key=True)
    bundle_uuid = UnicodeAttribute(range_key=True)
    bundle_code = UnicodeAttribute(null=True)
    bundle_name = UnicodeAttribute()
    bundle_type = UnicodeAttribute(default="package")
    description = UnicodeAttribute(null=True)
    extra = MapAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    bundle_code_index = BundleCodeIndex()
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
                    entity_keys["bundle_uuid"] = getattr(entity, "bundle_uuid", None)
                if not entity_keys.get("bundle_uuid"):
                    entity_keys["bundle_uuid"] = kwargs.get("bundle_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="bundle",
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
    cache_name=Config.get_cache_name("models", "bundle"),
    cache_enabled=Config.is_cache_enabled,
)
def get_bundle(partition_key: str, bundle_uuid: str) -> BundleModel:
    return BundleModel.get(partition_key, bundle_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_bundle(partition_key: str, bundle_uuid: str) -> BundleModel:
    return BundleModel.get(partition_key, bundle_uuid)


def get_bundle_count(partition_key: str, bundle_uuid: str) -> int:
    return BundleModel.count(partition_key, BundleModel.bundle_uuid == bundle_uuid)


def get_bundle_type(info: ResolveInfo, bundle: BundleModel) -> BundleType:
    _ = info
    bundle_dict = bundle.__dict__["attribute_values"].copy()
    return BundleType(**normalize_to_json(bundle_dict))


def resolve_bundle(info: ResolveInfo, **kwargs: Dict[str, Any]) -> BundleType | None:
    partition_key = info.context.get("partition_key")
    count = get_bundle_count(partition_key, kwargs["bundle_uuid"])
    if count == 0:
        return None
    return get_bundle_type(info, get_bundle(partition_key, kwargs["bundle_uuid"]))


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "bundle_uuid",
        "bundle_code",
        "bundle_name",
        "bundle_type",
        "status",
        "updated_at",
    ],
    list_type_class=BundleListType,
    type_funct=get_bundle_type,
)
def resolve_bundle_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    bundle_code = kwargs.get("bundle_code")
    bundle_type = kwargs.get("bundle_type")
    status = kwargs.get("status")

    args = []
    inquiry_funct = BundleModel.scan
    count_funct = BundleModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = BundleModel.updated_at_index.query
        count_funct = BundleModel.updated_at_index.count
        if bundle_code and args[1] is None:
            args[1] = BundleModel.bundle_code == bundle_code
            inquiry_funct = BundleModel.bundle_code_index.query
            count_funct = BundleModel.bundle_code_index.count

    the_filters = None
    if bundle_type:
        the_filters &= BundleModel.bundle_type == bundle_type
    if status:
        the_filters &= BundleModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "bundle_uuid",
    },
    model_funct=_get_bundle,
    count_funct=get_bundle_count,
    type_funct=get_bundle_type,
)
@purge_cache()
def insert_update_bundle(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
    if kwargs.get("entity") is None:
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "bundle_code",
            "bundle_name",
            "bundle_type",
            "description",
            "extra",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        BundleModel(partition_key, kwargs["bundle_uuid"], **cols).save()
        return

    bundle = kwargs.get("entity")
    actions = [
        BundleModel.updated_by.set(kwargs["updated_by"]),
        BundleModel.updated_at.set(pendulum.now("UTC")),
    ]
    field_map = {
        "bundle_code": BundleModel.bundle_code,
        "bundle_name": BundleModel.bundle_name,
        "bundle_type": BundleModel.bundle_type,
        "description": BundleModel.description,
        "extra": BundleModel.extra,
        "status": BundleModel.status,
    }
    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))
    bundle.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "bundle_uuid",
    },
    model_funct=get_bundle,
)
@purge_cache()
def delete_bundle(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    component_list = resolve_bundle_component_list(
        info, **{"bundle_uuid": kwargs.get("entity").bundle_uuid}
    )
    if component_list.total > 0:
        return False
    kwargs.get("entity").delete()
    return True
