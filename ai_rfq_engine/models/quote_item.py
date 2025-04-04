#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import (
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.indexes import AllProjection, GlobalSecondaryIndex, LocalSecondaryIndex
from tenacity import retry, stop_after_attempt, wait_exponential

from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility

from ..types.quote_item import QuoteItemListType, QuoteItemType


class ProviderItemUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_item_uuid-index"

    quote_uuid = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)


class ItemUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_uuid-index"

    quote_uuid = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)


class QuoteItemModel(BaseModel):
    class Meta:
        table_name = "are-quote_items"

    quote_uuid = UnicodeAttribute(hash_key=True)
    quote_item_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    item_uuid = UnicodeAttribute()
    request_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    request_data = MapAttribute()
    price_per_uom = NumberAttribute()
    qty = NumberAttribute()
    subtotal = NumberAttribute()
    discount_percentage = NumberAttribute(null=True)
    final_subtotal = NumberAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
    item_uuid_index = ItemUuidIndex()


def create_quote_item_table(logger: logging.Logger) -> bool:
    """Create the QuoteItem table if it doesn't exist."""
    if not QuoteItemModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        QuoteItemModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The QuoteItem table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_quote_item(quote_uuid: str, quote_item_uuid: str) -> QuoteItemModel:
    return QuoteItemModel.get(quote_uuid, quote_item_uuid)


def get_quote_item_count(quote_uuid: str, quote_item_uuid: str) -> int:
    return QuoteItemModel.count(
        quote_uuid, QuoteItemModel.quote_item_uuid == quote_item_uuid
    )


def get_quote_item_type(info: ResolveInfo, quote_item: QuoteItemModel) -> QuoteItemType:
    try:
        quote_item = quote_item.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return QuoteItemType(**Utility.json_loads(Utility.json_dumps(quote_item)))


def resolve_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteItemType:
    return get_quote_item_type(
        info,
        get_quote_item(kwargs["quote_uuid"], kwargs["quote_item_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "quote_uuid",
        "quote_item_uuid",
        "provider_item_uuid",
        "item_uuid",
    ],
    list_type_class=QuoteItemListType,
    type_funct=get_quote_item_type,
)
def resolve_quote_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    quote_uuid = kwargs.get("quote_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    item_uuid = kwargs.get("item_uuid")
    request_uuid = kwargs.get("request_uuid")
    max_price_per_uom = kwargs.get("max_price_per_uom")
    min_price_per_uom = kwargs.get("min_price_per_uom")
    max_qty = kwargs.get("max_qty")
    min_qty = kwargs.get("min_qty")
    max_subtotal = kwargs.get("max_subtotal")
    min_subtotal = kwargs.get("min_subtotal")
    max_discount_percentage = kwargs.get("max_discount_percentage")
    min_discount_percentage = kwargs.get("min_discount_percentage")
    max_final_subtotal = kwargs.get("max_final_subtotal")
    min_final_subtotal = kwargs.get("min_final_subtotal")

    args = []
    inquiry_funct = QuoteItemModel.scan
    count_funct = QuoteItemModel.count
    if quote_uuid:
        args = [quote_uuid, None]
        inquiry_funct = QuoteItemModel.query
        if provider_item_uuid:
            inquiry_funct = QuoteItemModel.provider_item_uuid_index.query
            args[1] = QuoteItemModel.provider_item_uuid_index == provider_item_uuid
            count_funct = QuoteItemModel.provider_item_uuid_index.count
        elif item_uuid:
            inquiry_funct = QuoteItemModel.item_uuid_index.query
            args[1] = QuoteItemModel.item_uuid_index == item_uuid
            count_funct = QuoteItemModel.item_uuid_index.count

    the_filters = None
    if request_uuid:
        the_filters &= QuoteItemModel.request_uuid == request_uuid
    if max_price_per_uom and min_price_per_uom:
        the_filters &= QuoteItemModel.price_per_uom.exists()
        the_filters &= QuoteItemModel.price_per_uom.between(
            min_price_per_uom, max_price_per_uom
        )
    if max_qty and min_qty:
        the_filters &= QuoteItemModel.qty.exists()
        the_filters &= QuoteItemModel.qty.between(min_qty, max_qty)
    if max_subtotal and min_subtotal:
        the_filters &= QuoteItemModel.subtotal.exists()
        the_filters &= QuoteItemModel.subtotal.between(min_subtotal, max_subtotal)
    if max_discount_percentage and min_discount_percentage:
        the_filters &= QuoteItemModel.discount_percentage.exists()
        the_filters &= QuoteItemModel.discount_percentage.between(
            min_discount_percentage, max_discount_percentage
        )
    if max_final_subtotal and min_final_subtotal:
        the_filters &= QuoteItemModel.final_subtotal.exists()
        the_filters &= QuoteItemModel.final_subtotal.between(
            min_final_subtotal, max_final_subtotal
        )
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=get_quote_item,
    count_funct=get_quote_item_count,
    type_funct=get_quote_item_type,
)
def insert_update_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    quote_uuid = kwargs.get("quote_uuid")
    quote_item_uuid = kwargs.get("quote_item_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_item_uuid",
            "item_uuid",
            "request_uuid",
            "request_data",
            "price_per_uom",
            "qty",
            "subtotal",
            "discount_percentage",
            "final_subtotal",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        QuoteItemModel(
            quote_uuid,
            quote_item_uuid,
            **cols,
        ).save()
        return

    quote_item = kwargs.get("entity")
    actions = [
        QuoteItemModel.updated_by.set(kwargs["updated_by"]),
        QuoteItemModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to QuoteItemModel attributes
    field_map = {
        "provider_item_uuid": QuoteItemModel.provider_item_uuid,
        "item_uuid": QuoteItemModel.item_uuid,
        "request_uuid": QuoteItemModel.request_uuid,
        "request_data": QuoteItemModel.request_data,
        "price_per_uom": QuoteItemModel.price_per_uom,
        "qty": QuoteItemModel.qty,
        "subtotal": QuoteItemModel.subtotal,
        "discount_percentage": QuoteItemModel.discount_percentage,
        "final_subtotal": QuoteItemModel.final_subtotal,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the quote item
    quote_item.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=get_quote_item,
)
def delete_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
