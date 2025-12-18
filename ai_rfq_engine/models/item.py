#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
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
from silvaengine_utility.serializer import Serializer
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.item import ItemListType, ItemType
from .provider_item import resolve_provider_item_list


class ItemTypeIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_type-index"

    partition_key = UnicodeAttribute(hash_key=True)
    item_type = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-items"

    partition_key = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)
    endpoint_id = UnicodeAttribute()
    part_id = UnicodeAttribute()
    item_type = UnicodeAttribute()
    item_name = UnicodeAttribute()
    item_description = UnicodeAttribute(null=True)
    uom = UnicodeAttribute()
    item_external_id = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    item_type_index = ItemTypeIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Execute original function first
                result = original_function(*args, **kwargs)

                # Then purge cache after successful operation
                from ..models.cache import purge_entity_cascading_cache

                # Get entity keys from entity parameter (for updates)
                entity_keys = {}
                entity = kwargs.get("entity")
                if entity:
                    entity_keys["item_uuid"] = getattr(entity, "item_uuid", None)

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("item_uuid"):
                    entity_keys["item_uuid"] = kwargs.get("item_uuid")

                # Get partition_key from context or kwargs
                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="item",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                return result
            except Exception as e:
                log = traceback.format_exc()
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


def create_item_table(logger: logging.Logger) -> bool:
    """Create the Item table if it doesn't exist."""
    if not ItemModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        ItemModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Item table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name("models", "item")
)
def get_item(partition_key: str, item_uuid: str) -> ItemModel:
    return ItemModel.get(partition_key, item_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_item(partition_key: str, item_uuid: str) -> ItemModel:
    return ItemModel.get(partition_key, item_uuid)


def get_item_count(partition_key: str, item_uuid: str) -> int:
    return ItemModel.count(partition_key, ItemModel.item_uuid == item_uuid)


def get_item_type(info: ResolveInfo, item: ItemModel) -> ItemType:
    try:
        item = item.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return ItemType(**Serializer.json_normalize(item))


def resolve_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType | None:
    partition_key = info.context.get("partition_key")

    if "item_external_id" in kwargs:
        # Get item by external id
        results = ItemModel.query(
            partition_key,
            None,
            ItemModel.item_external_id == kwargs["item_external_id"],
        )
        try:
            item = results.next()
            return get_item_type(info, item)
        except Exception:
            return None

    # Validate item_uuid is provided
    if "item_uuid" not in kwargs:
        return None

    count = get_item_count(partition_key, kwargs["item_uuid"])
    if count == 0:
        return None

    return get_item_type(
        info,
        get_item(partition_key, kwargs["item_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["partition_key", "item_uuid", "item_type", "updated_at"],
    list_type_class=ItemListType,
    type_funct=get_item_type,
)
def resolve_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    item_type = kwargs.get("item_type")
    item_name = kwargs.get("item_name")
    item_description = kwargs.get("item_description")
    uoms = kwargs.get("uoms")

    args = []
    inquiry_funct = ItemModel.scan
    count_funct = ItemModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = ItemModel.updated_at_index.query
        count_funct = ItemModel.updated_at_index.count
        if item_type:
            count_funct = ItemModel.item_type_index.count
            args[1] = ItemModel.item_type == item_type
            inquiry_funct = ItemModel.item_type_index.query

    the_filters = None  # We can add filters for the query
    if item_name:
        the_filters &= ItemModel.item_name.contains(item_name)
    if item_description:
        the_filters &= ItemModel.item_description.contains(item_description)
    if uoms:
        the_filters &= ItemModel.uom.is_in(*uoms)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "item_uuid",
    },
    model_funct=_get_item,
    count_funct=get_item_count,
    type_funct=get_item_type,
)
@purge_cache()
def insert_update_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = info.context.get("partition_key")
    item_uuid = kwargs.get("item_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "part_id": info.context.get("part_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "item_type",
            "item_name",
            "item_description",
            "uom",
            "item_external_id",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        ItemModel(
            partition_key,
            item_uuid,
            **cols,
        ).save()
        return

    item = kwargs.get("entity")
    actions = [
        ItemModel.updated_by.set(kwargs["updated_by"]),
        ItemModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to ItemModel attributes
    field_map = {
        "item_type": ItemModel.item_type,
        "item_name": ItemModel.item_name,
        "item_description": ItemModel.item_description,
        "uom": ItemModel.uom,
        "item_external_id": ItemModel.item_external_id,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the item
    item.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "item_uuid",
    },
    model_funct=get_item,
)
@purge_cache()
def delete_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    provider_item_list = resolve_provider_item_list(
        info,
        **{
            "item_uuid": kwargs.get("entity").item_uuid,
        },
    )
    if provider_item_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True
