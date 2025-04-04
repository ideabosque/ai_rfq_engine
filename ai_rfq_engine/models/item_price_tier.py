#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import NumberAttribute, UnicodeAttribute, UTCDateTimeAttribute
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

from ..types.item_price_tier import ItemPriceTierListType, ItemPriceTierType


class ProviderItemUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_item_uuid-index"

    item_uuid = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)


class SegmentUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "segment_uuid-index"

    item_uuid = UnicodeAttribute(hash_key=True)
    segment_uuid = UnicodeAttribute(range_key=True)


class ItemPriceTierModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-item_price_tiers"

    item_uuid = UnicodeAttribute(hash_key=True)
    item_price_tier_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    segment_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    quantity_greater_then = NumberAttribute()
    quantity_less_then = NumberAttribute()
    price = NumberAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
    segment_uuid_index = SegmentUuidIndex()


def create_item_price_tier_table(logger: logging.Logger) -> bool:
    """Create the ItemPriceTier table if it doesn't exist."""
    if not ItemPriceTierModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        ItemPriceTierModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The ItemPriceTier table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_item_price_tier(
    item_uuid: str, item_price_tier_uuid: str
) -> ItemPriceTierModel:
    return ItemPriceTierModel.get(item_uuid, item_price_tier_uuid)


def get_item_price_tier_count(item_uuid: str, item_price_tier_uuid: str) -> int:
    return ItemPriceTierModel.count(
        item_uuid, ItemPriceTierModel.item_price_tier_uuid == item_price_tier_uuid
    )


def get_item_price_tier_type(
    info: ResolveInfo, item_price_tier: ItemPriceTierModel
) -> ItemPriceTierType:
    try:
        item_price_tier = item_price_tier.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return ItemPriceTierType(**Utility.json_loads(Utility.json_dumps(item_price_tier)))


def resolve_item_price_tier(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierType:
    return get_item_price_tier_type(
        info,
        get_item_price_tier(kwargs["item_uuid"], kwargs["item_price_tier_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "item_uuid",
        "item_price_tier_uuid",
        "provider_item_uuid",
        "segment_uuid",
    ],
    list_type_class=ItemPriceTierListType,
    type_funct=get_item_price_tier_type,
)
def resolve_item_price_tier_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    item_uuid = kwargs.get("item_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")
    endpoint_id = info.context["endpoint_id"]
    max_quantity_greater_then = kwargs.get("max_quantity_greater_then")
    min_quantity_greater_then = kwargs.get("min_quantity_greater_then")
    max_quantity_less_then = kwargs.get("max_quantity_less_then")
    min_quantity_less_then = kwargs.get("min_quantity_less_then")
    max_price = kwargs.get("max_price")
    min_price = kwargs.get("min_price")

    args = []
    inquiry_funct = ItemPriceTierModel.scan
    count_funct = ItemPriceTierModel.count
    if item_uuid:
        args = [item_uuid, None]
        inquiry_funct = ItemPriceTierModel.query
        if provider_item_uuid:
            count_funct = ItemPriceTierModel.provider_item_uuid_index.count
            args[1] = ItemPriceTierModel.provider_item_uuid == provider_item_uuid
            inquiry_funct = ItemPriceTierModel.provider_item_uuid_index.query
        elif segment_uuid:
            count_funct = ItemPriceTierModel.segment_uuid_index.count
            args[1] = ItemPriceTierModel.segment_uuid == segment_uuid
            inquiry_funct = ItemPriceTierModel.segment_uuid_index.query

    the_filters = None  # We can add filters for the query
    if endpoint_id:
        the_filters &= ItemPriceTierModel.endpoint_id == endpoint_id
    if max_quantity_greater_then and min_quantity_greater_then:
        the_filters &= ItemPriceTierModel.quantity_greater_then.between(
            min_quantity_greater_then, max_quantity_greater_then
        )
    if max_quantity_less_then and min_quantity_less_then:
        the_filters &= ItemPriceTierModel.quantity_less_then.between(
            min_quantity_less_then, max_quantity_less_then
        )
    if max_price and min_price:
        the_filters &= ItemPriceTierModel.price.between(min_price, max_price)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "item_price_tier_uuid",
    },
    model_funct=get_item_price_tier,
    count_funct=get_item_price_tier_count,
    type_funct=get_item_price_tier_type,
)
def insert_update_item_price_tier(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    item_uuid = kwargs.get("item_uuid")
    item_price_tier_uuid = kwargs.get("item_price_tier_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_item_uuid",
            "segment_uuid",
            "quantity_greater_then",
            "quantity_less_then",
            "price",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        ItemPriceTierModel(
            item_uuid,
            item_price_tier_uuid,
            **cols,
        ).save()
        return

    item_price_tier = kwargs.get("entity")
    actions = [
        ItemPriceTierModel.updated_by.set(kwargs["updated_by"]),
        ItemPriceTierModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to ItemPriceTierModel attributes
    field_map = {
        "provider_item_uuid": ItemPriceTierModel.provider_item_uuid,
        "segment_uuid": ItemPriceTierModel.segment_uuid,
        "quantity_greater_then": ItemPriceTierModel.quantity_greater_then,
        "quantity_less_then": ItemPriceTierModel.quantity_less_then,
        "price": ItemPriceTierModel.price,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the item price tier
    item_price_tier.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "item_price_tier_uuid",
    },
    model_funct=get_item_price_tier,
)
def delete_item_price_tier(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
