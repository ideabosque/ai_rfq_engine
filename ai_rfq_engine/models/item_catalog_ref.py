#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import traceback
from typing import Any, Dict, List

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
from ..types.item_catalog_ref import (
    ItemCatalogRefListType,
    ItemCatalogRefType,
)
from ..utils.normalization import normalize_to_json


class SystemNodeIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "system_node_index"

    partition_key = UnicodeAttribute(hash_key=True)
    system_node_key = UnicodeAttribute(range_key=True)


class ItemLookupIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "item_lookup_index"

    partition_key = UnicodeAttribute(hash_key=True)
    item_lookup_key = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ItemCatalogRefModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-item_catalog_refs"

    partition_key = UnicodeAttribute(hash_key=True)
    catalog_ref_uuid = UnicodeAttribute(range_key=True)
    system_code = UnicodeAttribute()
    namespace = UnicodeAttribute(default="DEFAULT")
    node_id = UnicodeAttribute()
    system_node_key = UnicodeAttribute()
    extra = MapAttribute(null=True)
    item_uuid = UnicodeAttribute()
    item_lookup_key = UnicodeAttribute()
    provider_item_uuid = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    system_node_index = SystemNodeIndex()
    item_lookup_index = ItemLookupIndex()
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
                    entity_keys["catalog_ref_uuid"] = getattr(
                        entity, "catalog_ref_uuid", None
                    )
                if not entity_keys.get("catalog_ref_uuid"):
                    entity_keys["catalog_ref_uuid"] = kwargs.get("catalog_ref_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="item_catalog_ref",
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
    cache_name=Config.get_cache_name("models", "item_catalog_ref"),
    cache_enabled=Config.is_cache_enabled,
)
def get_item_catalog_ref(partition_key: str, catalog_ref_uuid: str) -> ItemCatalogRefModel:
    return ItemCatalogRefModel.get(partition_key, catalog_ref_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_item_catalog_ref(partition_key: str, catalog_ref_uuid: str) -> ItemCatalogRefModel:
    return ItemCatalogRefModel.get(partition_key, catalog_ref_uuid)


def get_item_catalog_ref_count(partition_key: str, catalog_ref_uuid: str) -> int:
    return ItemCatalogRefModel.count(
        partition_key, ItemCatalogRefModel.catalog_ref_uuid == catalog_ref_uuid
    )


def get_item_catalog_ref_type(
    info: ResolveInfo, ref: ItemCatalogRefModel
) -> ItemCatalogRefType:
    _ = info
    ref_dict = ref.__dict__["attribute_values"].copy()
    return ItemCatalogRefType(**normalize_to_json(ref_dict))


def resolve_item_catalog_ref(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemCatalogRefType | None:
    partition_key = info.context.get("partition_key")
    count = get_item_catalog_ref_count(partition_key, kwargs["catalog_ref_uuid"])
    if count == 0:
        return None
    return get_item_catalog_ref_type(
        info,
        get_item_catalog_ref(partition_key, kwargs["catalog_ref_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "catalog_ref_uuid",
        "system_code",
        "namespace",
        "node_id",
        "item_uuid",
        "status",
        "updated_at",
    ],
    list_type_class=ItemCatalogRefListType,
    type_funct=get_item_catalog_ref_type,
)
def resolve_item_catalog_ref_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    system_code = kwargs.get("system_code")
    namespace = kwargs.get("namespace")
    item_uuid = kwargs.get("item_uuid")
    status = kwargs.get("status")

    args = []
    inquiry_funct = ItemCatalogRefModel.scan
    count_funct = ItemCatalogRefModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = ItemCatalogRefModel.updated_at_index.query
        count_funct = ItemCatalogRefModel.updated_at_index.count

    the_filters = None
    if system_code:
        the_filters &= ItemCatalogRefModel.system_code == system_code
    if namespace:
        the_filters &= ItemCatalogRefModel.namespace == namespace
    if item_uuid:
        the_filters &= ItemCatalogRefModel.item_uuid == item_uuid
    if status:
        the_filters &= ItemCatalogRefModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def find_item_catalog_refs(
    info: ResolveInfo,
    system_code: str,
    node_ids: List[str],
    namespace: str = "DEFAULT",
    status: str = "active",
) -> List[ItemCatalogRefType]:
    partition_key = info.context.get("partition_key")
    refs = []
    for node_id in node_ids:
        system_node_key = f"{system_code}#{namespace}#{node_id}"
        filters = (
            ItemCatalogRefModel.status == status if status is not None else None
        )
        matches = ItemCatalogRefModel.system_node_index.query(
            partition_key,
            ItemCatalogRefModel.system_node_key == system_node_key,
            filter_condition=filters,
        )
        refs.extend(get_item_catalog_ref_type(info, ref) for ref in matches)
    return refs


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "catalog_ref_uuid",
    },
    model_funct=_get_item_catalog_ref,
    count_funct=get_item_catalog_ref_count,
    type_funct=get_item_catalog_ref_type,
)
@purge_cache()
def insert_update_item_catalog_ref(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    if kwargs.get("entity") is None:
        partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
        catalog_ref_uuid = kwargs.get("catalog_ref_uuid")
        system_code = kwargs.get("system_code", "")
        namespace = kwargs.get("namespace", "DEFAULT")
        node_id = kwargs.get("node_id", "")
        item_uuid = kwargs.get("item_uuid", "")

        cols = {
            "updated_by": kwargs["updated_by"],
            "system_code": system_code,
            "namespace": namespace,
            "node_id": node_id,
            "system_node_key": f"{system_code}#{namespace}#{node_id}",
            "item_uuid": item_uuid,
            "item_lookup_key": item_uuid,
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_item_uuid",
            "extra",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        ItemCatalogRefModel(
            partition_key,
            catalog_ref_uuid,
            **cols,
        ).save()
        return

    ref = kwargs.get("entity")
    actions = [
        ItemCatalogRefModel.updated_by.set(kwargs["updated_by"]),
        ItemCatalogRefModel.updated_at.set(pendulum.now("UTC")),
    ]

    field_map = {
        "system_code": ItemCatalogRefModel.system_code,
        "namespace": ItemCatalogRefModel.namespace,
        "node_id": ItemCatalogRefModel.node_id,
        "item_uuid": ItemCatalogRefModel.item_uuid,
        "provider_item_uuid": ItemCatalogRefModel.provider_item_uuid,
        "extra": ItemCatalogRefModel.extra,
        "status": ItemCatalogRefModel.status,
    }

    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Recompute system_node_key if system_code, namespace, or node_id changed
    if any(k in kwargs for k in ("system_code", "namespace", "node_id")):
        sc = kwargs.get("system_code", getattr(ref, "system_code", ""))
        ns = kwargs.get("namespace", getattr(ref, "namespace", "DEFAULT"))
        nid = kwargs.get("node_id", getattr(ref, "node_id", ""))
        actions.append(ItemCatalogRefModel.system_node_key.set(f"{sc}#{ns}#{nid}"))

    if "item_uuid" in kwargs:
        actions.append(ItemCatalogRefModel.item_lookup_key.set(kwargs["item_uuid"]))

    ref.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "catalog_ref_uuid",
    },
    model_funct=get_item_catalog_ref,
)
@purge_cache()
def delete_item_catalog_ref(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
