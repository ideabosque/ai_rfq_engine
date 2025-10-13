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
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility
from tenacity import retry, stop_after_attempt, wait_exponential

from ..types.quote import QuoteListType, QuoteType
from .installment import resolve_installment_list
from .quote_item import resolve_quote_item_list
from .utils import _get_request


class ProviderCorpExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_corp_external_id-index"

    request_uuid = UnicodeAttribute(hash_key=True)
    provider_corp_external_id = UnicodeAttribute(range_key=True)


class ProviderCorpExternalIdQuoteUuidIndex(GlobalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_corp_external_id-quote_uuid-index"

    provider_corp_external_id = UnicodeAttribute(hash_key=True)
    quote_uuid = UnicodeAttribute(range_key=True)


class QuoteModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quotes"

    request_uuid = UnicodeAttribute(hash_key=True)
    quote_uuid = UnicodeAttribute(range_key=True)
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXX")
    sales_rep_email = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    shipping_method = UnicodeAttribute(null=True)
    shipping_amount = NumberAttribute(null=True)
    total_quote_amount = NumberAttribute()
    total_quote_discount = NumberAttribute(null=True)
    final_total_quote_amount = NumberAttribute()
    notes = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="initial")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_corp_external_id_index = ProviderCorpExternalIdIndex()
    provider_corp_external_id_quote_uuid_index = ProviderCorpExternalIdQuoteUuidIndex()


def create_quote_table(logger: logging.Logger) -> bool:
    """Create the Quote table if it doesn't exist."""
    if not QuoteModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        QuoteModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Quote table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_quote(request_uuid: str, quote_uuid: str) -> QuoteModel:
    return QuoteModel.get(request_uuid, quote_uuid)


def get_quote_count(request_uuid: str, quote_uuid: str) -> int:
    return QuoteModel.count(request_uuid, QuoteModel.quote_uuid == quote_uuid)


def get_quote_type(info: ResolveInfo, quote: QuoteModel) -> QuoteType:
    try:
        request = _get_request(info.context["endpoint_id"], quote.request_uuid)
        quote = quote.__dict__["attribute_values"]
        quote["request"] = request
        quote.pop("endpoint_id")
        quote.pop("request_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return QuoteType(**Utility.json_normalize(quote))


def resolve_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
    return get_quote_type(
        info,
        get_quote(kwargs["request_uuid"], kwargs["quote_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "request_uuid",
        "quote_uuid",
        "provider_corp_external_id",
    ],
    list_type_class=QuoteListType,
    type_funct=get_quote_type,
)
def resolve_quote_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    request_uuid = kwargs.get("request_uuid")
    provider_corp_external_id = kwargs.get("provider_corp_external_id")
    shipping_methods = kwargs.get("shipping_methods")
    max_shipping_amount = kwargs.get("max_shipping_amount")
    min_shipping_amount = kwargs.get("min_shipping_amount")
    max_total_quote_amount = kwargs.get("max_total_quote_amount")
    min_total_quote_amount = kwargs.get("min_total_quote_amount")
    max_total_quote_discount = kwargs.get("max_total_quote_discount")
    min_total_quote_discount = kwargs.get("min_total_quote_discount")
    max_final_total_quote_amount = kwargs.get("max_final_total_quote_amount")
    min_final_total_quote_amount = kwargs.get("min_final_total_quote_amount")
    statuses = kwargs.get("statuses")

    args = []
    inquiry_funct = QuoteModel.scan
    count_funct = QuoteModel.count
    if request_uuid:
        args = [request_uuid, None]
        inquiry_funct = QuoteModel.query
        if provider_corp_external_id:
            inquiry_funct = QuoteModel.provider_corp_external_id_index.query
            args[1] = QuoteModel.provider_corp_external_id == provider_corp_external_id
            count_funct = QuoteModel.provider_corp_external_id_index.count
    if provider_corp_external_id and not request_uuid:
        args = [provider_corp_external_id, None]
        inquiry_funct = QuoteModel.provider_corp_external_id_quote_uuid_index.query
        count_funct = QuoteModel.provider_corp_external_id_quote_uuid_index.count

    the_filters = None
    if shipping_methods:
        the_filters &= QuoteModel.shipping_method.exists()
        the_filters &= QuoteModel.shipping_method.is_in(*shipping_methods)
    if max_shipping_amount and min_shipping_amount:
        the_filters &= QuoteModel.shipping_amount.exists()
        the_filters &= QuoteModel.shipping_amount.between(
            min_shipping_amount, max_shipping_amount
        )
    if max_total_quote_amount and min_total_quote_amount:
        the_filters &= QuoteModel.total_quote_amount.exists()
        the_filters &= QuoteModel.total_quote_amount.between(
            min_total_quote_amount, max_total_quote_amount
        )
    if max_total_quote_discount and min_total_quote_discount:
        the_filters &= QuoteModel.total_quote_discount.exists()
        the_filters &= QuoteModel.total_quote_discount.between(
            min_total_quote_discount, max_total_quote_discount
        )
    if max_final_total_quote_amount and min_final_total_quote_amount:
        the_filters &= QuoteModel.final_total_quote_amount.exists()
        the_filters &= QuoteModel.final_total_quote_amount.between(
            min_final_total_quote_amount, max_final_total_quote_amount
        )
    if statuses:
        the_filters &= QuoteModel.status.is_in(*statuses)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "quote_uuid",
    },
    model_funct=get_quote,
    count_funct=get_quote_count,
    type_funct=get_quote_type,
)
def insert_update_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_uuid = kwargs.get("request_uuid")
    quote_uuid = kwargs.get("quote_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_corp_external_id",
            "sales_rep_email",
            "shipping_method",
            "shipping_amount",
            "total_quote_amount",
            "total_quote_discount",
            "final_total_quote_amount",
            "notes",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        QuoteModel(
            request_uuid,
            quote_uuid,
            **cols,
        ).save()
        return

    quote = kwargs.get("entity")
    actions = [
        QuoteModel.updated_by.set(kwargs["updated_by"]),
        QuoteModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to QuoteModel attributes
    field_map = {
        "provider_corp_external_id": QuoteModel.provider_corp_external_id,
        "sales_rep_email": QuoteModel.sales_rep_email,
        "shipping_method": QuoteModel.shipping_method,
        "shipping_amount": QuoteModel.shipping_amount,
        "total_quote_amount": QuoteModel.total_quote_amount,
        "total_quote_discount": QuoteModel.total_quote_discount,
        "final_total_quote_amount": QuoteModel.final_total_quote_amount,
        "notes": QuoteModel.notes,
        "status": QuoteModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the quote
    quote.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "quote_uuid",
    },
    model_funct=get_quote,
)
def delete_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    quote_item_list = resolve_quote_item_list(
        info, **{"quote_uuid": kwargs.get("entity").quote_uuid}
    )
    if quote_item_list.total > 0:
        return False

    installment_list = resolve_installment_list(
        info, **{"quote_uuid": kwargs.get("entity").quote_uuid}
    )
    if installment_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True
