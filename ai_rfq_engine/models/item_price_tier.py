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
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
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
from ..types.item_price_tier import ItemPriceTierListType, ItemPriceTierType


def _get_provider_item(endpoint_id: str, provider_item_uuid: str) -> Dict[str, Any]:
    """Helper to get provider_item data for eager loading."""
    from .provider_item import get_provider_item, get_provider_item_count

    count = get_provider_item_count(endpoint_id, provider_item_uuid)
    if count == 0:
        return {}

    provider_item = get_provider_item(endpoint_id, provider_item_uuid)
    return {
        "endpoint_id": provider_item.endpoint_id,
        "provider_item_uuid": provider_item.provider_item_uuid,
        "provider_corp_external_id": provider_item.provider_corp_external_id,
        "provider_item_external_id": getattr(provider_item, "provider_item_external_id", None),
        "base_price_per_uom": provider_item.base_price_per_uom,
        "item_uuid": provider_item.item_uuid,
    }


def _get_segment(endpoint_id: str, segment_uuid: str) -> Dict[str, Any]:
    """Helper to get segment data for eager loading."""
    from .segment import get_segment, get_segment_count

    count = get_segment_count(endpoint_id, segment_uuid)
    if count == 0:
        return {}

    segment = get_segment(endpoint_id, segment_uuid)
    return {
        "endpoint_id": segment.endpoint_id,
        "segment_uuid": segment.segment_uuid,
        "provider_corp_external_id": segment.provider_corp_external_id,
        "segment_name": segment.segment_name,
        "segment_description": segment.segment_description,
    }


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


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    item_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ItemPriceTierModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-item_price_tiers"

    item_uuid = UnicodeAttribute(hash_key=True)
    item_price_tier_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    segment_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    quantity_greater_then = NumberAttribute()
    quantity_less_then = NumberAttribute(null=True)
    margin_per_uom = NumberAttribute(null=True)
    price_per_uom = NumberAttribute(null=True)
    status = UnicodeAttribute(default="in_review")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
    segment_uuid_index = SegmentUuidIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Use cascading cache purging for item_price_tiers
                from ..models.cache import purge_entity_cascading_cache

                context_keys = None
                entity_keys = {}
                if kwargs.get("item_uuid"):
                    entity_keys["item_uuid"] = kwargs.get("item_uuid")
                if kwargs.get("item_price_tier_uuid"):
                    entity_keys["item_price_tier_uuid"] = kwargs.get(
                        "item_price_tier_uuid"
                    )

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="item_price_tier",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                if kwargs.get("item_uuid"):
                   result = purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="item_price_tier",
                        context_keys=context_keys,
                        entity_keys={"item_uuid": kwargs.get("item_uuid")},
                        cascade_depth=3,
                        custom_options={"custom_getter": "get_item_price_tiers_by_item", "custom_cache_keys": ["key:item_uuid"]}
                    )

                if kwargs.get("item_uuid") and kwargs.get("item_price_tier_uuid"):
                   result = purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="item_price_tier",
                        context_keys=context_keys,
                        entity_keys={"item_uuid": kwargs.get("item_uuid"), "item_price_tier_uuid": kwargs.get("item_price_tier_uuid")},
                        cascade_depth=3,
                        custom_options={"custom_getter": "get_item_price_tiers_by_provider_item", "custom_cache_keys": ["key:item_uuid", "key:item_price_tier_uuid"]}
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
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "item_price_tier"),
)
def get_item_price_tier(
    item_uuid: str, item_price_tier_uuid: str
) -> ItemPriceTierModel:
    return ItemPriceTierModel.get(item_uuid, item_price_tier_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_item_price_tier(
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
    """
    Convert ItemPriceTierModel to ItemPriceTierType.
    Nested relationships are lazily loaded via nested resolvers.
    """
    try:
        tier_dict: Dict = item_price_tier.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return ItemPriceTierType(**Utility.json_normalize(tier_dict))


def resolve_item_price_tier(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierType | None:
    count = get_item_price_tier_count(
        kwargs["item_uuid"], kwargs["item_price_tier_uuid"]
    )
    if count == 0:
        return None

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
        "updated_at",
    ],
    list_type_class=ItemPriceTierListType,
    type_funct=get_item_price_tier_type,
)
def resolve_item_price_tier_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    """
    Internal helper that builds the query for item price tiers.
    Used by resolve_item_price_tier_list and private functions.
    """
    item_uuid = kwargs.get("item_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")
    endpoint_id = info.context["endpoint_id"]
    quantity_value = kwargs.get("quantity_value")
    max_price = kwargs.get("max_price")
    min_price = kwargs.get("min_price")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")
    status = kwargs.get("status")
    is_it_last_tier = kwargs.get("is_it_last_tier", False)

    args = []
    inquiry_funct = ItemPriceTierModel.scan
    count_funct = ItemPriceTierModel.count
    range_key_condition = None
    if item_uuid:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = ItemPriceTierModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = ItemPriceTierModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = ItemPriceTierModel.updated_at < updated_at_lt

        args = [item_uuid, range_key_condition]
        inquiry_funct = ItemPriceTierModel.updated_at_index.query
        count_funct = ItemPriceTierModel.updated_at_index.count
        if provider_item_uuid and args[1] is None:
            count_funct = ItemPriceTierModel.provider_item_uuid_index.count
            args[1] = ItemPriceTierModel.provider_item_uuid == provider_item_uuid
            inquiry_funct = ItemPriceTierModel.provider_item_uuid_index.query
        elif segment_uuid and args[1] is None:
            count_funct = ItemPriceTierModel.segment_uuid_index.count
            args[1] = ItemPriceTierModel.segment_uuid == segment_uuid
            inquiry_funct = ItemPriceTierModel.segment_uuid_index.query

    the_filters = None  # We can add filters for the query
    if endpoint_id:
        the_filters &= ItemPriceTierModel.endpoint_id == endpoint_id
    if (
        provider_item_uuid
        and args[1] is not None
        and inquiry_funct != ItemPriceTierModel.provider_item_uuid_index.query
    ):
        the_filters &= ItemPriceTierModel.provider_item_uuid == provider_item_uuid
    if (
        segment_uuid
        and args[1] is not None
        and inquiry_funct != ItemPriceTierModel.segment_uuid_index.query
    ):
        the_filters &= ItemPriceTierModel.segment_uuid == segment_uuid

    # Find the price tier that matches a specific quantity value
    # A tier matches when: quantity_greater_then <= quantity_value < quantity_less_then
    if quantity_value is not None:
        the_filters &= ItemPriceTierModel.quantity_greater_then <= quantity_value
        # Handle cases where quantity_less_then might be null (no upper limit)
        the_filters &= (ItemPriceTierModel.quantity_less_then.does_not_exist()) | (
            ItemPriceTierModel.quantity_less_then > quantity_value
        )
    if max_price and min_price:
        the_filters &= ItemPriceTierModel.price_per_uom.between(min_price, max_price)
    if status:
        the_filters &= ItemPriceTierModel.status == status

    # Filter for tiers where quantity_less_then is None or doesn't exist
    if is_it_last_tier:
        the_filters &= ItemPriceTierModel.quantity_less_then.does_not_exist()

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def _get_previous_tier(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    """
    Retrieves and validates the previous tier for a new tier insertion.

    Checks:
    1. quantity_greater_then is provided and >= 0
    2. provider_item_uuid and segment_uuid are provided
    3. If a previous tier exists (quantity_less_then = None), the new tier's
       quantity_greater_then must be greater than the previous tier's quantity_greater_then

    Args:
        info: GraphQL resolve info
        kwargs: Dictionary containing:
            - item_uuid: The item UUID
            - quantity_greater_then: The new tier's lower bound
            - provider_item_uuid: Provider item UUID
            - segment_uuid: Segment UUID

    Returns:
        The previous tier if one exists and validation passes, None otherwise

    Raises:
        ValueError: If validation fails for any of the checks
    """

    item_uuid = kwargs.get("item_uuid")
    quantity_greater_then = float(kwargs.get("quantity_greater_then", 0))
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")

    # Validate required fields
    if quantity_greater_then is None:
        raise ValueError("quantity_greater_then is required for new price tier")

    if quantity_greater_then < 0:
        raise ValueError("quantity_greater_then must be >= 0")

    if not provider_item_uuid:
        raise ValueError("provider_item_uuid is required for new price tier")

    if not segment_uuid:
        raise ValueError("segment_uuid is required for new price tier")

    # Use the same query logic as resolve_item_price_tier_list to find the current last tier
    item_price_tier_list = resolve_item_price_tier_list(
        info,
        **{
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "segment_uuid": segment_uuid,
            "is_it_last_tier": True,
        },
    )

    # Check if there's a previous tier and validate ordering
    if item_price_tier_list.total == 0:
        return None
    else:
        tier = item_price_tier_list.item_price_tier_list[0]
        if quantity_greater_then > tier.quantity_greater_then:
            return tier
        raise ValueError(
            f"New tier's quantity_greater_then ({quantity_greater_then}) must be greater than "
            f"the previous tier's quantity_greater_then ({tier.quantity_greater_then})"
        )


def _update_previous_tier(
    info: ResolveInfo,
    item_uuid: str,
    previous_tier: "ItemPriceTierType",
    quantity_less_then: float,
    updated_by: str,
) -> None:
    """
    Updates the previous tier's quantity_less_then using insert_update_item_price_tier.

    Args:
        info: GraphQL resolve info
        item_uuid: The item UUID
        previous_tier: The previous tier object to update
        quantity_less_then: The new upper bound for the previous tier
        updated_by: User making the update
    """
    if previous_tier is None:
        return

    # Use insert_update_item_price_tier to update the previous tier
    insert_update_item_price_tier(
        info,
        **{
            "item_uuid": item_uuid,
            "item_price_tier_uuid": previous_tier.item_price_tier_uuid,
            "quantity_less_then": quantity_less_then,
            "updated_by": updated_by,
        },
    )


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "item_price_tier_uuid",
    },
    model_funct=_get_item_price_tier,
    count_funct=get_item_price_tier_count,
    type_funct=get_item_price_tier_type,
)
def insert_update_item_price_tier(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    item_uuid = kwargs.get("item_uuid")
    item_price_tier_uuid = kwargs.get("item_price_tier_uuid")
    if kwargs.get("entity") is None:
        # get the previous tier for validation, if any
        previous_tier = _get_previous_tier(info, **kwargs)

        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
            "quantity_less_then": None,  # Always set to None for new tiers
        }
        for key in [
            "provider_item_uuid",
            "segment_uuid",
            "quantity_greater_then",
            "margin_per_uom",
            "price_per_uom",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        # Save the new tier first
        ItemPriceTierModel(
            item_uuid,
            item_price_tier_uuid,
            **cols,
        ).save()

        # Update the previous tier's quantity_less_then if there is one
        if previous_tier is not None:
            _update_previous_tier(
                info=info,
                item_uuid=item_uuid,
                previous_tier=previous_tier,
                quantity_less_then=kwargs["quantity_greater_then"],
                updated_by=kwargs["updated_by"],
            )

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
        "margin_per_uom": ItemPriceTierModel.margin_per_uom,
        "price_per_uom": ItemPriceTierModel.price_per_uom,
        "status": ItemPriceTierModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the item price tier
    item_price_tier.update(actions=actions)
    return


@purge_cache()
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

@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "item_price_tier"),
)
def get_item_price_tiers_by_item(
    item_uuid: str
) -> Any:
    return ItemPriceTierModel.query(item_uuid)

@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "item_price_tier"),
)
def get_item_price_tiers_by_provider_item(
    item_uuid: str, provider_item_uuid: str, segment_uuid: str = None
) -> Any:
    """
    Get item price tiers by provider_item_uuid with optional segment filtering.

    Args:
        item_uuid: The item UUID (hash key)
        provider_item_uuid: The provider item UUID to filter by
        segment_uuid: Optional segment UUID to filter results

    Returns:
        List of ItemPriceTierModel instances matching the criteria
    """
    item_price_tiers = []

    # Build the range key condition
    range_key_condition = ItemPriceTierModel.provider_item_uuid == provider_item_uuid

    # Build filter condition for segment if provided
    filter_condition = None
    if segment_uuid:
        filter_condition = ItemPriceTierModel.segment_uuid == segment_uuid

    for item_price_tier in ItemPriceTierModel.provider_item_uuid_index.query(
        item_uuid, range_key_condition, filter_condition=filter_condition
    ):
        item_price_tiers.append(item_price_tier)
    return item_price_tiers
