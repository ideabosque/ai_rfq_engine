#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from tenacity import retry, stop_after_attempt, wait_exponential

from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility

from ..types.item import ItemListType, ItemType
from .provider_item import resolve_provider_item_list
from .request import resolve_request_list


class ItemTypeIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_type-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
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

    endpoint_id = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-items"

    endpoint_id = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)
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
def get_item(endpoint_id: str, item_uuid: str) -> ItemModel:
    return ItemModel.get(endpoint_id, item_uuid)


def get_item_count(endpoint_id: str, item_uuid: str) -> int:
    return ItemModel.count(endpoint_id, ItemModel.item_uuid == item_uuid)


def get_item_type(info: ResolveInfo, item: ItemModel) -> ItemType:
    try:
        item = item.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return ItemType(**Utility.json_loads(Utility.json_dumps(item)))


def resolve_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
    return get_item_type(
        info,
        get_item(info.context["endpoint_id"], kwargs["item_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["endpoint_id", "item_uuid", "item_type", "updated_at"],
    list_type_class=ItemListType,
    type_funct=get_item_type,
)
def resolve_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    endpoint_id = info.context["endpoint_id"]
    item_type = kwargs.get("item_type")
    item_name = kwargs.get("item_name")
    item_description = kwargs.get("item_description")
    uoms = kwargs.get("uoms")

    args = []
    inquiry_funct = ItemModel.scan
    count_funct = ItemModel.count
    if endpoint_id:
        args = [endpoint_id, None]
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
        "hash_key": "endpoint_id",
        "range_key": "item_uuid",
    },
    model_funct=get_item,
    count_funct=get_item_count,
    type_funct=get_item_type,
)
def insert_update_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id")
    item_uuid = kwargs.get("item_uuid")
    if kwargs.get("entity") is None:
        cols = {
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
            endpoint_id,
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
        "hash_key": "endpoint_id",
        "range_key": "item_uuid",
    },
    model_funct=get_item,
)
def delete_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    provider_item_list = resolve_provider_item_list(
        info,
        **{
            "endpoint_id": kwargs.get("entity").endpoint_id,
            "item_uuid": kwargs.get("entity").item_uuid,
        },
    )
    if provider_item_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True
