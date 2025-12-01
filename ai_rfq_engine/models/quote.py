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
from pynamodb.attributes import NumberAttribute, UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.indexes import AllProjection, GlobalSecondaryIndex, LocalSecondaryIndex
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility, method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.quote import QuoteListType, QuoteType


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


class UpdatedAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    request_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class QuoteModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quotes"

    request_uuid = UnicodeAttribute(hash_key=True)
    quote_uuid = UnicodeAttribute(range_key=True)
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
    sales_rep_email = UnicodeAttribute(null=True)
    endpoint_id = UnicodeAttribute()
    shipping_method = UnicodeAttribute(null=True)
    shipping_amount = NumberAttribute(default=0)
    total_quote_amount = NumberAttribute(default=0)
    total_quote_discount = NumberAttribute(default=0)
    final_total_quote_amount = NumberAttribute(default=0)
    rounds = NumberAttribute(default=0)
    notes = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="initial")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_corp_external_id_index = ProviderCorpExternalIdIndex()
    provider_corp_external_id_quote_uuid_index = ProviderCorpExternalIdQuoteUuidIndex()
    updated_at_index = UpdatedAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Use cascading cache purging for quotes
                from ..models.cache import purge_entity_cascading_cache

                entity_keys = {}
                if kwargs.get("request_uuid"):
                    entity_keys["request_uuid"] = kwargs.get("request_uuid")
                if kwargs.get("quote_uuid"):
                    entity_keys["quote_uuid"] = kwargs.get("quote_uuid")

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="quote",
                    context_keys=None,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                ## Original function.
                result = original_function(*args, **kwargs)

                return result
            except Exception as e:
                log = traceback.format_exc()
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


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
@method_cache(
    ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name("models", "quote")
)
def get_quote(request_uuid: str, quote_uuid: str) -> QuoteModel:
    return QuoteModel.get(request_uuid, quote_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_quote(request_uuid: str, quote_uuid: str) -> QuoteModel:
    return QuoteModel.get(request_uuid, quote_uuid)


def get_quote_count(request_uuid: str, quote_uuid: str) -> int:
    return QuoteModel.count(request_uuid, QuoteModel.quote_uuid == quote_uuid)


def _get_next_round_number(request_uuid: str, provider_corp_external_id: str) -> int:
    """
    Get the next round number for a quote based on existing quotes
    with the same request_uuid and provider_corp_external_id.

    Args:
        request_uuid: The request UUID
        provider_corp_external_id: The provider corporation external ID

    Returns:
        The next round number (max existing rounds + 1, or 0 if no existing quotes)
    """
    max_rounds = -1

    if request_uuid and provider_corp_external_id:
        # Query existing quotes with the same request_uuid and provider_corp_external_id
        existing_quotes = QuoteModel.provider_corp_external_id_index.query(
            request_uuid,
            QuoteModel.provider_corp_external_id == provider_corp_external_id,
        )

        # Find the maximum rounds value
        for quote in existing_quotes:
            if quote.rounds is not None and quote.rounds > max_rounds:
                max_rounds = quote.rounds

    return max_rounds + 1


def update_quote_totals(info: ResolveInfo, request_uuid: str, quote_uuid: str) -> None:
    """
    Calculate and update quote totals based on related quote items.
    Updates: total_quote_amount, total_quote_discount, final_total_quote_amount
    final_total_quote_amount includes shipping_amount if present.
    """
    # Import here to avoid circular dependency
    from .quote_item import resolve_quote_item_list

    # Get the quote to access shipping_amount
    quote = get_quote(request_uuid, quote_uuid)

    # Query all quote items for this quote using resolver
    quote_item_list = resolve_quote_item_list(info, **{"quote_uuid": quote_uuid})

    # Calculate totals from the quote item list
    total_quote_amount = sum(item.subtotal for item in quote_item_list.quote_item_list)
    total_quote_discount = sum(
        item.subtotal_discount if item.subtotal_discount is not None else 0
        for item in quote_item_list.quote_item_list
    )
    items_final_total = sum(
        item.final_subtotal for item in quote_item_list.quote_item_list
    )

    # Add shipping amount to final total
    shipping_amount = quote.shipping_amount if quote.shipping_amount is not None else 0
    final_total_quote_amount = items_final_total + shipping_amount
    actions = [
        QuoteModel.total_quote_amount.set(float(total_quote_amount)),
        QuoteModel.total_quote_discount.set(
            float(total_quote_discount) if total_quote_discount > 0 else None
        ),
        QuoteModel.final_total_quote_amount.set(float(final_total_quote_amount)),
        QuoteModel.updated_at.set(pendulum.now("UTC")),
    ]
    quote.update(actions=actions)


def get_quote_type(info: ResolveInfo, quote: QuoteModel) -> QuoteType:
    """
    Nested resolver approach: return minimal quote data.
    - Do NOT embed 'request'.
    'request' is resolved lazily by QuoteType.resolve_request.
    - 'quote_items' ARE still embedded for now (List(JSON)).
    """
    try:
        # Import here to avoid circular dependency
        from .quote_item import resolve_quote_item_list

        quote_dict: Dict = quote.__dict__["attribute_values"]

        # Get quote items for this quote (still eager for now)
        quote_item_list = resolve_quote_item_list(
            info, **{"quote_uuid": quote.quote_uuid}
        )
        quote_items = [
            Utility.json_normalize(
                {
                    k: getattr(item, k, None)
                    for k in [
                        "quote_item_uuid",
                        "provider_item_uuid",
                        "item_uuid",
                        "batch_no",
                        "request_data",
                        "slow_move_item",
                        "guardrail_price_per_uom",
                        "price_per_uom",
                        "qty",
                        "subtotal",
                        "subtotal_discount",
                        "final_subtotal",
                    ]
                }
            )
            for item in quote_item_list.quote_item_list
        ]

        quote_dict["quote_items"] = quote_items
        quote_dict.pop("endpoint_id")
        quote_dict.pop("request_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return QuoteType(**Utility.json_normalize(quote_dict))


def resolve_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType | None:
    count = get_quote_count(kwargs["request_uuid"], kwargs["quote_uuid"])
    if count == 0:
        return None

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
        "updated_at",
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
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = QuoteModel.scan
    count_funct = QuoteModel.count
    if request_uuid:
        range_key_condition = None

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = QuoteModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = QuoteModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = QuoteModel.updated_at < updated_at_lt

        args = [request_uuid, range_key_condition]
        inquiry_funct = QuoteModel.updated_at_index.query
        count_funct = QuoteModel.updated_at_index.count
        if provider_corp_external_id and args[1] is None:
            inquiry_funct = QuoteModel.provider_corp_external_id_index.query
            args[1] = QuoteModel.provider_corp_external_id == provider_corp_external_id
            count_funct = QuoteModel.provider_corp_external_id_index.count
    if provider_corp_external_id and not request_uuid:
        args = [provider_corp_external_id, None]
        inquiry_funct = QuoteModel.provider_corp_external_id_quote_uuid_index.query
        count_funct = QuoteModel.provider_corp_external_id_quote_uuid_index.count

    the_filters = None
    if (
        provider_corp_external_id
        and request_uuid
        and args[1] is not None
        and args[1]
        != (QuoteModel.provider_corp_external_id == provider_corp_external_id)
    ):
        the_filters &= QuoteModel.provider_corp_external_id == provider_corp_external_id
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


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "quote_uuid",
    },
    model_funct=_get_quote,
    count_funct=get_quote_count,
    type_funct=get_quote_type,
)
def insert_update_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_uuid = kwargs.get("request_uuid")
    quote_uuid = kwargs.get("quote_uuid")
    if kwargs.get("entity") is None:
        # Calculate the next round number
        provider_corp_external_id = kwargs.get("provider_corp_external_id")
        kwargs["rounds"] = _get_next_round_number(
            request_uuid, provider_corp_external_id
        )

        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_corp_external_id",
            "sales_rep_email",
            "rounds",
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
        "notes": QuoteModel.notes,
        "status": QuoteModel.status,
    }

    # Track if shipping_amount was updated
    shipping_amount_updated = False

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))
            if key == "shipping_amount":
                shipping_amount_updated = True

    # Update the quote
    quote.update(actions=actions)

    # If shipping_amount was updated, recalculate final_total_quote_amount
    if shipping_amount_updated:
        update_quote_totals(info, request_uuid, quote_uuid)

    return


@purge_cache()
@delete_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "quote_uuid",
    },
    model_funct=get_quote,
)
def delete_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    # Import here to avoid circular dependency
    from .installment import resolve_installment_list
    from .quote_item import resolve_quote_item_list

    # Check if there are any quote items
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
