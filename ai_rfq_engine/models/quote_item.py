#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
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
from silvaengine_utility import convert_decimal_to_number, method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.quote_item import QuoteItemListType, QuoteItemType
from ..utils.normalization import normalize_to_json
from .installment import resolve_installment_list


def _build_cancellation_snapshot(
    partition_key: str,
    provider_item_uuid: str,
    batch_no: str | None,
) -> dict | None:
    """
    Build a point-in-time snapshot of the cancellation policy attached to a
    provider-item batch.

    Returns ``None`` when no batch is pinned, when the batch has no
    ``cancellation_policy_uuid``, or when the referenced policy cannot be
    loaded (procurement default — no policy term to display).

    The snapshot is immutable on the quote item; if the supplier later changes
    the policy, the customer still sees the terms they were quoted.
    """
    if not batch_no or not provider_item_uuid:
        return None
    try:
        from .provider_item_batches import get_provider_item_batch

        batch = get_provider_item_batch(provider_item_uuid, batch_no)
    except Exception:
        return None
    policy_uuid = getattr(batch, "cancellation_policy_uuid", None)
    if not policy_uuid or not partition_key:
        return None
    try:
        from .cancellation_policy import (
            get_cancellation_policy,
            get_cancellation_policy_count,
        )

        if get_cancellation_policy_count(partition_key, policy_uuid) == 0:
            return None
        policy = get_cancellation_policy(partition_key, policy_uuid)
    except Exception:
        return None

    tiers = getattr(policy, "tiers", None)
    if hasattr(tiers, "as_dict"):
        try:
            tiers = tiers.as_dict()
        except Exception:
            tiers = None
    return {
        "policy_uuid": getattr(policy, "policy_uuid", policy_uuid),
        "label": getattr(policy, "label", None),
        "description": getattr(policy, "description", None),
        "tiers": tiers,
        "notes_template_uuid": getattr(policy, "notes_template_uuid", None),
        "snapshotted_at": pendulum.now("UTC").to_iso8601_string(),
    }


def _enforce_availability(
    info: ResolveInfo,
    *,
    provider_item: Any,
    provider_item_uuid: str,
    batch_no: str | None,
    qty: float,
    pax_breakdown: dict | None,
    service_start_at: Any = None,
    service_end_at: Any = None,
) -> dict | None:
    """
    Check configured reservable capacity before persisting a quote item.

    The provider item owns whether availability is disabled, read-only checked,
    or protected by a temporary hold. A pinned batch provides its service
    window when the caller does not supply one explicitly.
    """
    availability_mode = getattr(provider_item, "availability_mode", None) or "none"
    if availability_mode == "none":
        return None
    if availability_mode not in {"check_only", "require_hold"}:
        raise ValueError(f"Unsupported availability_mode: {availability_mode}")
    availability_system_code = getattr(
        provider_item, "availability_system_code", None
    )
    if not availability_system_code:
        raise ValueError(
            "Provider item availability is enabled but availability_system_code is missing"
        )

    if batch_no and (service_start_at is None or service_end_at is None):
        from .provider_item_batches import get_provider_item_batch

        batch = get_provider_item_batch(provider_item_uuid, batch_no)
        service_start_at = service_start_at or getattr(batch, "service_start_at", None)
        service_end_at = service_end_at or getattr(batch, "service_end_at", None)

    if service_start_at is None or service_end_at is None:
        raise ValueError(
            "service_start_at and service_end_at are required for availability checks"
        )
    if service_end_at <= service_start_at:
        raise ValueError("service_end_at must be later than service_start_at")

    from ..handlers.availability import dispatch_acquire_hold, dispatch_check

    dispatch = (
        dispatch_acquire_hold
        if availability_mode == "require_hold"
        else dispatch_check
    )
    result = dispatch(
        info,
        system_code=availability_system_code,
        namespace=getattr(provider_item, "availability_namespace", None) or "DEFAULT",
        provider_corp_external_id=getattr(provider_item, "provider_corp_external_id", None),
        provider_item_uuid=provider_item_uuid,
        batch_no=batch_no,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        pax_breakdown=pax_breakdown,
        qty=float(qty),
    )
    if not result.get("available"):
        raise ValueError(
            "Requested provider item is not available for the service window"
        )
    if availability_mode == "require_hold" and (
        not result.get("hold_token") or not result.get("expires_at")
    ):
        raise ValueError("Availability handler did not return the required temporary hold")
    return result


def _release_availability_hold(info: ResolveInfo, quote_item: Any) -> None:
    hold_token = getattr(quote_item, "hold_token", None)
    if not hold_token:
        return
    from .provider_item import get_provider_item

    provider_item = get_provider_item(
        getattr(quote_item, "partition_key", info.context.get("partition_key")),
        quote_item.provider_item_uuid,
    )
    if (getattr(provider_item, "availability_mode", None) or "none") != "require_hold":
        return
    from ..handlers.availability import dispatch_release_hold

    dispatch_release_hold(
        info,
        system_code=provider_item.availability_system_code,
        namespace=getattr(provider_item, "availability_namespace", None) or "DEFAULT",
        provider_corp_external_id=getattr(provider_item, "provider_corp_external_id", None),
        provider_item_uuid=quote_item.provider_item_uuid,
        batch_no=getattr(quote_item, "batch_no", None),
        hold_token=hold_token,
    )


def _get_occupancy_pricing_tier(
    info: ResolveInfo,
    *,
    item_uuid: str,
    qty: float,
    segment_uuid: str,
    provider_item_uuid: str,
) -> Any:
    """
    Look up the single base tier used for G2 occupancy-mode pricing.

    Mirrors ``get_price_per_uom``'s tier-selection rules (segment + provider +
    quantity-band match, no ``pax_type``) but returns the matched tier itself
    so callers can read ``base_occupancy`` and ``extra_pax_surcharges`` in
    addition to ``price_per_uom``. Returns ``None`` when no tier matches.
    """
    from .item_price_tier import resolve_item_price_tier_list

    price_tier_list = resolve_item_price_tier_list(
        info,
        item_uuid=item_uuid,
        segment_uuid=segment_uuid,
        provider_item_uuid=provider_item_uuid,
        quantity_value=qty,
        status="active",
        legacy_pax_only=True,
    )
    if price_tier_list.total == 0:
        return None
    return price_tier_list.item_price_tier_list[0]


def _coerce_occupancy_map(value: Any) -> Dict[str, float]:
    """
    Normalise a ``MapAttribute`` (or plain dict) into ``{pax_type: float}``.
    Returns an empty dict for ``None`` / unrecognised shapes so the caller
    can treat absent surcharges as zero without special-casing.
    """
    if value is None:
        return {}
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        try:
            value = as_dict()
        except Exception:
            return {}
    if not isinstance(value, dict):
        return {}
    out: Dict[str, float] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return out


def get_price_per_uom(
    info: ResolveInfo,
    item_uuid: str,
    qty: float,
    segment_uuid: str,
    provider_item_uuid: str,
    batch_no: str = None,
    pax_type: str = None,
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
        "legacy_pax_only": pax_type is None,
    }
    if pax_type is not None:
        query_params["pax_type"] = pax_type

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
    provider_item_batches = []

    if getattr(tier, "margin_per_uom", None) is not None:
        from .provider_item_batches import get_provider_item_batches_by_provider_item

        for batch in get_provider_item_batches_by_provider_item(provider_item_uuid):

            # Slow-moving items use a fixed guardrail price to ensure minimum margins,
            # while regular items calculate price from cost plus the tier's margin percentage.
            if (
                hasattr(batch, "slow_move_item")
                and hasattr(batch, "guardrail_price_per_uom")
                and batch.slow_move_item is True
            ):
                price = batch.guardrail_price_per_uom
            else:
                cost = batch.total_cost_per_uom or 0
                price = cost * (1 + float(tier.margin_per_uom))

            provider_item_batches.append(
                {"batch_no": batch.batch_no, "price_per_uom": price}
            )

    if provider_item_batches:
        # If batch_no is specified, find that specific batch
        if batch_no:
            for batch in provider_item_batches:
                if batch["batch_no"] == batch_no:
                    return batch["price_per_uom"]

        # Otherwise, return the first available batch price
        return provider_item_batches[0]["price_per_uom"]

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
    partition_key = UnicodeAttribute()
    request_data = MapAttribute(null=True)
    price_per_uom = NumberAttribute()
    qty = NumberAttribute()
    pax_breakdown = MapAttribute(null=True)
    bundle_uuid = UnicodeAttribute(null=True)
    bundle_label = UnicodeAttribute(null=True)
    subtotal = NumberAttribute()
    subtotal_discount = NumberAttribute(null=True)
    final_subtotal = NumberAttribute()
    currency = UnicodeAttribute(null=True)
    subtotal_native = NumberAttribute(null=True)
    notes = UnicodeAttribute(null=True)
    hold_token = UnicodeAttribute(null=True)
    hold_expires_at = UTCDateTimeAttribute(null=True)
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
                # Execute original function first
                result = original_function(*args, **kwargs)

                # Then purge cache after successful operation
                from ..models.cache import purge_entity_cascading_cache

                # Get entity keys from entity parameter (for updates)
                entity_keys = {}
                entity = kwargs.get("entity")
                if entity:
                    entity_keys["quote_uuid"] = getattr(entity, "quote_uuid", None)
                    entity_keys["quote_item_uuid"] = getattr(
                        entity, "quote_item_uuid", None
                    )

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("quote_uuid"):
                    entity_keys["quote_uuid"] = kwargs.get("quote_uuid")
                if not entity_keys.get("quote_item_uuid"):
                    entity_keys["quote_item_uuid"] = kwargs.get("quote_item_uuid")

                context_keys = None

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="quote_item",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                if kwargs.get("quote_uuid"):
                    purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="quote_item",
                        context_keys=context_keys,
                        entity_keys={"quote_uuid": kwargs.get("quote_uuid")},
                        cascade_depth=3,
                        custom_options={
                            "custom_getter": "get_quote_items_by_quote",
                            "custom_cache_keys": ["key:quote_uuid"],
                        },
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
    cache_name=Config.get_cache_name("models", "quote_item"),
    cache_enabled=Config.is_cache_enabled,
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
    """
    Nested resolver approach: return minimal quote_item data.
    Those are resolved lazily by QuoteItemType resolvers.
    """
    _ = info  # Keep for signature compatibility with decorators
    quote_item_dict = quote_item.__dict__["attribute_values"].copy()
    return QuoteItemType(**normalize_to_json(quote_item_dict))


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
    bundle_uuid = kwargs.get("bundle_uuid")

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
    if bundle_uuid:
        the_filters &= QuoteItemModel.bundle_uuid == bundle_uuid
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=_get_quote_item,
    count_funct=get_quote_item_count,
    type_funct=get_quote_item_type,
)
@purge_cache()
def insert_update_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    quote_uuid = kwargs.get("quote_uuid")
    quote_item_uuid = kwargs.get("quote_item_uuid")
    request_uuid = kwargs.get("request_uuid")

    # request_uuid is required for new quote items to update quote totals
    if kwargs.get("entity") is None and not request_uuid:
        raise ValueError("request_uuid is required when creating a new quote item")

    if kwargs.get("entity") is None:
        cols = {
            "partition_key": info.context.get("partition_key"),
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

        from .item import get_item

        item = get_item(info.context.get("partition_key"), item_uuid)
        pricing_mode = getattr(item, "pricing_mode", None) or "unit"
        pax_breakdown = kwargs.get("pax_breakdown")

        if pricing_mode == "per_pax_type":
            if not isinstance(pax_breakdown, dict) or not pax_breakdown:
                raise ValueError(
                    "pax_breakdown is required for per_pax_type pricing"
                )

            pax_total = 0.0
            subtotal = 0.0
            for pax_type, pax_qty in pax_breakdown.items():
                pax_qty = float(pax_qty)
                if pax_qty <= 0:
                    raise ValueError(
                        f"pax_breakdown quantities must be greater than 0, got {pax_type}={pax_qty}"
                    )
                pax_price = get_price_per_uom(
                    info,
                    item_uuid,
                    pax_qty,
                    segment_uuid,
                    provider_item_uuid,
                    batch_no,
                    pax_type=pax_type,
                )
                if pax_price is None:
                    raise ValueError(
                        f"No price tier found for item_uuid={item_uuid}, pax_type={pax_type}, "
                        f"qty={pax_qty}, segment_uuid={segment_uuid}, "
                        f"provider_item_uuid={provider_item_uuid}"
                    )
                pax_total += pax_qty
                subtotal += float(pax_price) * pax_qty

            if float(qty) != pax_total:
                raise ValueError(
                    "qty must equal the total pax_breakdown quantity for per_pax_type pricing"
                )
            price_per_uom = subtotal / pax_total
        elif pricing_mode == "unit":
            price_per_uom = get_price_per_uom(
                info, item_uuid, qty, segment_uuid, provider_item_uuid, batch_no
            )
            if price_per_uom is None:
                raise ValueError(
                    f"No price tier found for item_uuid={item_uuid}, qty={qty}, "
                    f"segment_uuid={segment_uuid}, provider_item_uuid={provider_item_uuid}"
                )
            subtotal = float(price_per_uom) * float(qty)
        elif pricing_mode == "occupancy":
            # Lodging-style: one base tier covers up to ``base_occupancy``
            # guests per pax_type; each guest beyond that adds a surcharge.
            # ``qty`` is the number of UOM units (room-nights, table-seatings,
            # etc.); ``pax_breakdown`` is who's staying / attending.
            if not isinstance(pax_breakdown, dict) or not pax_breakdown:
                raise ValueError(
                    "pax_breakdown is required for occupancy pricing"
                )
            tier = _get_occupancy_pricing_tier(
                info,
                item_uuid=item_uuid,
                qty=qty,
                segment_uuid=segment_uuid,
                provider_item_uuid=provider_item_uuid,
            )
            if tier is None or tier.price_per_uom is None:
                raise ValueError(
                    f"No occupancy base tier found for item_uuid={item_uuid}, "
                    f"qty={qty}, segment_uuid={segment_uuid}, "
                    f"provider_item_uuid={provider_item_uuid}"
                )
            base_rate = float(tier.price_per_uom)
            base_occupancy = _coerce_occupancy_map(
                getattr(tier, "base_occupancy", None)
            )
            extra_surcharges = _coerce_occupancy_map(
                getattr(tier, "extra_pax_surcharges", None)
            )

            per_uom_surcharge = 0.0
            for pt, raw_count in pax_breakdown.items():
                try:
                    count = float(raw_count)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"pax_breakdown counts must be numeric, got {pt}={raw_count!r}"
                    )
                if count < 0:
                    raise ValueError(
                        f"pax_breakdown counts must be non-negative, got {pt}={count}"
                    )
                included = base_occupancy.get(pt, 0.0)
                extras = max(0.0, count - included)
                if extras and pt not in extra_surcharges:
                    raise ValueError(
                        f"Occupancy tier missing extra_pax_surcharges entry for "
                        f"over-base pax_type={pt!r}"
                    )
                per_uom_surcharge += extras * extra_surcharges.get(pt, 0.0)

            price_per_uom = base_rate + per_uom_surcharge
            subtotal = price_per_uom * float(qty)
        else:
            raise ValueError(f"Unsupported pricing_mode: {pricing_mode}")

        # Set all required fields
        cols["item_uuid"] = item_uuid
        cols["provider_item_uuid"] = provider_item_uuid
        cols["qty"] = qty
        cols["request_uuid"] = request_uuid
        cols["price_per_uom"] = price_per_uom

        for optional_key in ["batch_no", "request_data", "pax_breakdown", "bundle_uuid", "bundle_label", "currency", "subtotal_native", "subtotal_discount", "notes"]:
            if optional_key in kwargs:
                cols[optional_key] = kwargs[optional_key]

        from .quote import get_quote as _get_parent_quote

        try:
            quote_model = _get_parent_quote(request_uuid, quote_uuid)
        except Exception:
            quote_model = None

        from .provider_item import get_provider_item

        provider_item = get_provider_item(
            info.context.get("partition_key"), provider_item_uuid
        )
        availability = _enforce_availability(
            info,
            provider_item=provider_item,
            provider_item_uuid=provider_item_uuid,
            batch_no=batch_no,
            qty=qty,
            pax_breakdown=pax_breakdown,
            service_start_at=kwargs.get("service_start_at"),
            service_end_at=kwargs.get("service_end_at"),
        )
        if availability is not None:
            cols["hold_token"] = availability.get("hold_token")
            expires_at = availability.get("expires_at")
            cols["hold_expires_at"] = (
                pendulum.parse(expires_at) if isinstance(expires_at, str) else expires_at
            )

        # G5: apply Quote-locked FX rate. ``subtotal`` from tier pricing is in the
        # native (supplier) currency. If the parent Quote was created with a
        # ``fx_rate`` and a ``display_currency`` that differs from the native
        # currency, convert. Otherwise display == native (procurement default).
        subtotal_native_amount = subtotal

        # Default the native currency from the parent Quote when the caller
        # didn't provide one explicitly. Keeps existing procurement callers
        # (no currency configured anywhere) working unchanged.
        if "currency" not in cols and quote_model is not None:
            quote_native_currency = getattr(quote_model, "currency", None)
            if quote_native_currency:
                cols["currency"] = quote_native_currency

        native_currency = cols.get("currency")
        subtotal_display = subtotal_native_amount

        if quote_model is not None:
            fx_rate = getattr(quote_model, "fx_rate", None)
            display_currency = getattr(quote_model, "display_currency", None)
            # FX applies only when all three are known and the currencies differ.
            # Same-currency quotes (USD display + USD supplier) and unconfigured
            # quotes (no fx_rate) both fall through to subtotal_display == native.
            if (
                fx_rate is not None
                and display_currency
                and native_currency
                and display_currency != native_currency
            ):
                subtotal_display = subtotal_native_amount * float(fx_rate)

        if "subtotal_native" not in cols:
            cols["subtotal_native"] = subtotal_native_amount

        # G6: snapshot the cancellation policy onto request_data so the quote
        # carries the exact terms the customer was shown, even if the supplier
        # later changes the policy. Skipped when no batch is pinned to the
        # line, or when the batch has no cancellation_policy_uuid set
        # (existing procurement behavior).
        snapshot = _build_cancellation_snapshot(
            info.context.get("partition_key"),
            provider_item_uuid,
            cols.get("batch_no"),
        )
        if snapshot is not None:
            request_data = cols.get("request_data") or {}
            if isinstance(request_data, dict):
                # Preserve any caller-provided keys; never clobber existing data.
                request_data.setdefault("cancellation_policy_snapshot", snapshot)
                cols["request_data"] = request_data

        # Auto-calculate subtotal and final_subtotal (both in DISPLAY currency)
        subtotal_discount = cols.get("subtotal_discount", 0)
        final_subtotal = subtotal_display - subtotal_discount
        cols["subtotal"] = subtotal_display
        cols["final_subtotal"] = final_subtotal

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

        if "notes" in kwargs:
            actions.append(QuoteItemModel.notes.set(kwargs["notes"]))

        if "bundle_uuid" in kwargs:
            actions.append(
                QuoteItemModel.bundle_uuid.set(
                    None if kwargs["bundle_uuid"] == "null" else kwargs["bundle_uuid"]
                )
            )

        if "bundle_label" in kwargs:
            actions.append(
                QuoteItemModel.bundle_label.set(
                    None if kwargs["bundle_label"] == "null" else kwargs["bundle_label"]
                )
            )

        if "currency" in kwargs:
            actions.append(
                QuoteItemModel.currency.set(
                    None if kwargs["currency"] == "null" else kwargs["currency"]
                )
            )

        if "pax_breakdown" in kwargs:
            raise ValueError(
                "pax_breakdown cannot be updated on an existing quote item without repricing"
            )

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

        if "subtotal_native" in kwargs:
            actions.append(
                QuoteItemModel.subtotal_native.set(
                    None if kwargs["subtotal_native"] == "null" else kwargs["subtotal_native"]
                )
            )

        # Update the quote item
        quote_item.update(actions=actions)

        # Update quote totals only if discount changed (which affects totals)
        if "subtotal_discount" in kwargs:
            if not request_uuid:
                raise ValueError("request_uuid is required to update quote totals")

            from .quote import update_quote_totals

            update_quote_totals(info, request_uuid, quote_uuid)

    return


@delete_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "quote_item_uuid",
    },
    model_funct=get_quote_item,
)
@purge_cache()
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

    _release_availability_hold(info, kwargs.get("entity"))
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
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "quote_item"),
    cache_enabled=Config.is_cache_enabled,
)
def get_quote_items_by_quote(quote_uuid: str) -> Any:
    quote_items = []
    for quote_item in QuoteItemModel.query(quote_uuid):
        quote_items.append(quote_item)
    return quote_items
