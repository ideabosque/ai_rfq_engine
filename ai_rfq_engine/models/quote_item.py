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
from silvaengine_utility import Utility, convert_decimal_to_number, method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.quote_item import QuoteItemListType, QuoteItemType
from .installment import resolve_installment_list


def get_price_per_uom(
    info: ResolveInfo,
    item_uuid: str,
    qty: float,
    segment_uuid: str,
    provider_item_uuid: str,
    batch_no: str = None,
) -> float | None:
    """
    Get the price per UOM based on item price tiers for the given quantity.

    Uses resolve_item_price_tier_list to retrieve tiers with calculated batch prices.

    Parameters:
    - item_uuid: Required - The item to get pricing for
    - qty: Required - The quantity to match against tier ranges
    - segment_uuid: Required - The segment to filter tiers
    - provider_item_uuid: Required - The provider item to filter tiers
    - batch_no: Optional - Specific batch to use for pricing

    If the tier has:
    - price_per_uom: Returns that direct price
    - margin_per_uom with batches: Returns price from matching batch

    Returns the calculated price_per_uom, or None if no tier matches.
    """
    from .item_price_tier import resolve_item_price_tier_list

    # Build query parameters with required filters and quantity matching
    query_params = {
        "item_uuid": item_uuid,
        "segment_uuid": segment_uuid,
        "provider_item_uuid": provider_item_uuid,
        "quantity_value": qty,  # Use new efficient tier matching
        "status": "active",
    }

    # Retrieve price tiers - now filtered by quantity_value at the database level
    price_tier_list = resolve_item_price_tier_list(info, **query_params)

    if price_tier_list.total == 0:
        return None

    # Get the first matching tier (database already filtered by quantity)
    tier = price_tier_list.item_price_tier_list[0]

    # If tier has direct price_per_uom, use it
    if tier.price_per_uom is not None:
        return tier.price_per_uom

    # If tier has margin_per_uom with batches, find the matching batch price
    if hasattr(tier, "provider_item_batches") and tier.provider_item_batches:
        # If batch_no is specified, find that specific batch
        if batch_no:
            for batch in tier.provider_item_batches:
                if batch["batch_no"] == batch_no:
                    return batch["price_per_uom"]

        # Otherwise, return the first available batch price
        return tier.provider_item_batches[0]["price_per_uom"]

    return None


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


class ItemUuidProviderItemUuidIndex(GlobalSecondaryIndex):
    """
    This class represents a Global secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_uuid-provider_item_uuid-index"

    item_uuid = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    quote_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class QuoteItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quote_items"

    quote_uuid = UnicodeAttribute(hash_key=True)
    quote_item_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    item_uuid = UnicodeAttribute()
    batch_no = UnicodeAttribute(null=True)
    request_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    request_data = MapAttribute(null=True)
    price_per_uom = NumberAttribute()
    qty = NumberAttribute()
    subtotal = NumberAttribute()
    subtotal_discount = NumberAttribute(null=True)
    final_subtotal = NumberAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
    item_uuid_index = ItemUuidIndex()
    item_uuid_provider_item_uuid_index = ItemUuidProviderItemUuidIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Use cascading cache purging for quotes
                from ..models.cache import purge_entity_cascading_cache

                context_keys = None
                entity_keys = {}
                if kwargs.get("quote_uuid"):
                    entity_keys["quote_uuid"] = kwargs.get("quote_uuid")
                if kwargs.get("quote_item_uuid"):
                    entity_keys["quote_item_uuid"] = kwargs.get("quote_item_uuid")

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="quote",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                if kwargs.get("quote_uuid"):
                   result = purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="provider_item",
                        context_keys=context_keys,
                        entity_keys={"quote_uuid": kwargs.get("quote_uuid")},
                        cascade_depth=3,
                        custom_options={"custom_getter": "get_quote_items_by_quote", "custom_cache_keys": ["key:quote_uuid"]}
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
@method_cache(
    ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name("models", "quote_item")
)
def get_quote_item(quote_uuid: str, quote_item_uuid: str) -> QuoteItemModel:
    return QuoteItemModel.get(quote_uuid, quote_item_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_quote_item(quote_uuid: str, quote_item_uuid: str) -> QuoteItemModel:
    return QuoteItemModel.get(quote_uuid, quote_item_uuid)


def get_quote_item_count(quote_uuid: str, quote_item_uuid: str) -> int:
    return QuoteItemModel.count(
        quote_uuid, QuoteItemModel.quote_item_uuid == quote_item_uuid
    )


def get_quote_item_type(info: ResolveInfo, quote_item: QuoteItemModel) -> QuoteItemType:
    try:
        quote_item_dict: Dict = quote_item.__dict__["attribute_values"]

        # Get batch information if batch_no exists
        slow_move_item = False
        guardrail_price_per_uom = None

        if quote_item_dict.get("batch_no"):
            from .provider_item_batches import get_provider_item_batch

            try:
                batch = get_provider_item_batch(
                    quote_item_dict["provider_item_uuid"], quote_item_dict["batch_no"]
                )
                slow_move_item = (
                    batch.slow_move_item if batch.slow_move_item is not None else False
                )
                guardrail_price_per_uom = batch.guardrail_price_per_uom
            except Exception:
                # If batch not found, use default values
                pass
        else:
            # If no batch_no, get guardrail_price_per_uom from ProviderItemModel.base_price_per_uom
            from .provider_item import get_provider_item

            try:
                provider_item = get_provider_item(
                    quote_item_dict["endpoint_id"],
                    quote_item_dict["provider_item_uuid"],
                )
                guardrail_price_per_uom = provider_item.base_price_per_uom
            except Exception:
                # If provider item not found, use None
                pass

        quote_item_dict["slow_move_item"] = slow_move_item
        quote_item_dict["guardrail_price_per_uom"] = guardrail_price_per_uom
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return QuoteItemType(**Utility.json_normalize(quote_item_dict))


def resolve_quote_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemType | None:
    count = get_quote_item_count(kwargs["quote_uuid"], kwargs["quote_item_uuid"])
    if count == 0:
        return None

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
        "updated_at",
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
    max_subtotal_discount = kwargs.get("max_subtotal_discount")
    min_subtotal_discount = kwargs.get("min_subtotal_discount")
    max_final_subtotal = kwargs.get("max_final_subtotal")
    min_final_subtotal = kwargs.get("min_final_subtotal")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = QuoteItemModel.scan
    count_funct = QuoteItemModel.count
    range_key_condition = None
    if quote_uuid:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = QuoteItemModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = QuoteItemModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = QuoteItemModel.updated_at < updated_at_lt

        args = [quote_uuid, range_key_condition]
        inquiry_funct = QuoteItemModel.updated_at_index.query
        count_funct = QuoteItemModel.updated_at_index.count
        if provider_item_uuid and args[1] is None:
            inquiry_funct = QuoteItemModel.provider_item_uuid_index.query
            args[1] = QuoteItemModel.provider_item_uuid == provider_item_uuid
            count_funct = QuoteItemModel.provider_item_uuid_index.count
        elif item_uuid and args[1] is None:
            inquiry_funct = QuoteItemModel.item_uuid_index.query
            args[1] = QuoteItemModel.item_uuid == item_uuid
            count_funct = QuoteItemModel.item_uuid_index.count
    if item_uuid and not quote_uuid:
        args = [item_uuid, None]
        inquiry_funct = QuoteItemModel.item_uuid_provider_item_uuid_index.query
        count_funct = QuoteItemModel.item_uuid_provider_item_uuid_index.count

    the_filters = None
    if request_uuid:
        the_filters &= QuoteItemModel.request_uuid == request_uuid
    if (
        provider_item_uuid
        and args[1] is not None
        and args[1] != (QuoteItemModel.provider_item_uuid == provider_item_uuid)
    ):
        the_filters &= QuoteItemModel.provider_item_uuid == provider_item_uuid
    if (
        item_uuid
        and quote_uuid
        and args[1] is not None
        and args[1] != (QuoteItemModel.item_uuid == item_uuid)
    ):
        the_filters &= QuoteItemModel.item_uuid == item_uuid
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
    if max_subtotal_discount and min_subtotal_discount:
        the_filters &= QuoteItemModel.subtotal_discount.exists()
        the_filters &= QuoteItemModel.subtotal_discount.between(
            min_subtotal_discount, max_subtotal_discount
        )
    if max_final_subtotal and min_final_subtotal:
        the_filters &= QuoteItemModel.final_subtotal.exists()
        the_filters &= QuoteItemModel.final_subtotal.between(
            min_final_subtotal, max_final_subtotal
        )
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@purge_cache()
@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=_get_quote_item,
    count_funct=get_quote_item_count,
    type_funct=get_quote_item_type,
)
def insert_update_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    quote_uuid = kwargs.get("quote_uuid")
    quote_item_uuid = kwargs.get("quote_item_uuid")
    request_uuid = kwargs.get("request_uuid")

    # request_uuid is required for new quote items to update quote totals
    if kwargs.get("entity") is None and not request_uuid:
        raise ValueError("request_uuid is required when creating a new quote item")

    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }

        # Get required fields for tier pricing
        item_uuid = kwargs.get("item_uuid")
        qty = kwargs.get("qty")
        segment_uuid = kwargs.get("segment_uuid")  # Required for tier pricing
        provider_item_uuid = kwargs.get(
            "provider_item_uuid"
        )  # Required for tier pricing
        batch_no = kwargs.get("batch_no")  # Optional for specific batch selection

        # Validate required fields
        if not (item_uuid and qty and segment_uuid and provider_item_uuid):
            raise ValueError(
                "item_uuid, qty, segment_uuid, and provider_item_uuid are required for tier pricing"
            )

        # Validate qty is positive
        if float(qty) <= 0:
            raise ValueError(f"qty must be greater than 0, got: {qty}")

        # Calculate price_per_uom from tier pricing
        price_per_uom = get_price_per_uom(
            info, item_uuid, qty, segment_uuid, provider_item_uuid, batch_no
        )

        if price_per_uom is None:
            raise ValueError(
                f"No price tier found for item_uuid={item_uuid}, qty={qty}, "
                f"segment_uuid={segment_uuid}, provider_item_uuid={provider_item_uuid}"
            )

        # Set all required fields
        cols["item_uuid"] = item_uuid
        cols["provider_item_uuid"] = provider_item_uuid
        cols["qty"] = qty
        cols["request_uuid"] = request_uuid
        cols["price_per_uom"] = price_per_uom

        # Set optional fields
        if batch_no:
            cols["batch_no"] = batch_no
        if "request_data" in kwargs:
            cols["request_data"] = kwargs["request_data"]
        if "subtotal_discount" in kwargs:
            cols["subtotal_discount"] = kwargs["subtotal_discount"]

        # Auto-calculate subtotal and final_subtotal
        cols["subtotal"] = float(cols["price_per_uom"]) * float(cols["qty"])
        subtotal_discount = cols.get("subtotal_discount", 0)
        cols["final_subtotal"] = cols["subtotal"] - subtotal_discount

        QuoteItemModel(
            quote_uuid,
            quote_item_uuid,
            **convert_decimal_to_number(cols),
        ).save()

        # Update quote totals after inserting new quote item
        if not request_uuid:
            raise ValueError("request_uuid is required to update quote totals")

        from .quote import update_quote_totals

        update_quote_totals(info, request_uuid, quote_uuid)

    else:
        quote_item = kwargs.get("entity")
        request_uuid = quote_item.request_uuid

        actions = [
            QuoteItemModel.updated_by.set(kwargs["updated_by"]),
            QuoteItemModel.updated_at.set(pendulum.now("UTC")),
        ]

        # Only allow updating discount
        if "subtotal_discount" in kwargs:
            subtotal_discount = (
                None
                if kwargs["subtotal_discount"] == "null"
                else kwargs["subtotal_discount"]
            )
            actions.append(QuoteItemModel.subtotal_discount.set(subtotal_discount))

            # Recalculate final_subtotal when discount changes
            subtotal = quote_item.subtotal
            discount = subtotal_discount if subtotal_discount is not None else 0
            final_subtotal = subtotal - discount
            actions.append(QuoteItemModel.final_subtotal.set(final_subtotal))

        # Update the quote item
        quote_item.update(actions=actions)

        # Update quote totals only if discount changed (which affects totals)
        if "subtotal_discount" in kwargs:
            if not request_uuid:
                raise ValueError("request_uuid is required to update quote totals")

            from .quote import update_quote_totals

            update_quote_totals(info, request_uuid, quote_uuid)

    return


@purge_cache()
@purge_cache()
@delete_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=get_quote_item,
)
def delete_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    installment_list = resolve_installment_list(
        info,
        **{
            "quote_uuid": kwargs.get("entity").quote_uuid,
            "quote_item_uuid": kwargs.get("entity").quote_item_uuid,
        },
    )
    if installment_list.total > 0:
        return False

    # Store values needed for updating quote totals
    request_uuid = kwargs.get("entity").request_uuid
    quote_uuid = kwargs.get("entity").quote_uuid

    kwargs.get("entity").delete()

    # Update quote totals after deleting quote item
    from .quote import update_quote_totals

    update_quote_totals(info, request_uuid, quote_uuid)

    return True

@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name("models", "quote_item")
)
def get_quote_items_by_quote(quote_uuid: str) -> Any:
    quote_items = []
    for quote_item in QuoteItemModel.query(quote_uuid):
        quote_items.append(quote_item)
    return quote_items