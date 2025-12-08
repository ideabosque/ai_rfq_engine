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
from ..types.discount_rule import DiscountRuleListType, DiscountRuleType


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


class DiscountRuleModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-discount_rules"

    item_uuid = UnicodeAttribute(hash_key=True)
    discount_rule_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    segment_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    subtotal_greater_than = NumberAttribute()
    subtotal_less_than = NumberAttribute(null=True)
    max_discount_percentage = NumberAttribute()
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
                # Use cascading cache purging for discount_rules
                from ..models.cache import purge_entity_cascading_cache

                context_keys = None
                entity_keys = {}
                if kwargs.get("item_uuid"):
                    entity_keys["item_uuid"] = kwargs.get("item_uuid")
                if kwargs.get("discount_rule_uuid"):
                    entity_keys["discount_rule_uuid"] = kwargs.get("discount_rule_uuid")

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="discount_rule",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                if kwargs.get("item_uuid"):
                    result = purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="discount_rule",
                        context_keys=context_keys,
                        entity_keys={"item_uuid": kwargs.get("item_uuid")},
                        cascade_depth=3,
                        custom_getter="get_discount_rules_by_item",
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


def create_discount_rule_table(logger: logging.Logger) -> bool:
    """Create the DiscountRule table if it doesn't exist."""
    if not DiscountRuleModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        DiscountRuleModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The DiscountRule table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_rule"),
)
def get_discount_rule(item_uuid: str, discount_rule_uuid: str) -> DiscountRuleModel:
    return DiscountRuleModel.get(item_uuid, discount_rule_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_discount_rule(item_uuid: str, discount_rule_uuid: str) -> DiscountRuleModel:
    return DiscountRuleModel.get(item_uuid, discount_rule_uuid)


def get_discount_rule_count(item_uuid: str, discount_rule_uuid: str) -> int:
    return DiscountRuleModel.count(
        item_uuid, DiscountRuleModel.discount_rule_uuid == discount_rule_uuid
    )


def get_discount_rule_type(
    info: ResolveInfo, discount_rule: DiscountRuleModel
) -> DiscountRuleType:
    """
    Nested resolver approach: return minimal discount_rule data.
    - Do NOT embed 'provider_item' or 'segment'.
    Those are resolved lazily by DiscountRuleType resolvers.
    """
    try:
        rule_dict = discount_rule.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return DiscountRuleType(**Utility.json_normalize(rule_dict))


def resolve_discount_rule(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountRuleType | None:
    count = get_discount_rule_count(kwargs["item_uuid"], kwargs["discount_rule_uuid"])
    if count == 0:
        return None

    return get_discount_rule_type(
        info,
        get_discount_rule(kwargs["item_uuid"], kwargs["discount_rule_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "item_uuid",
        "discount_rule_uuid",
        "provider_item_uuid",
        "segment_uuid",
        "updated_at",
    ],
    list_type_class=DiscountRuleListType,
    type_funct=get_discount_rule_type,
)
def resolve_discount_rule_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    item_uuid = kwargs.get("item_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")
    endpoint_id = info.context["endpoint_id"]
    subtotal_value = kwargs.get("subtotal_value")
    max_discount_percentage = kwargs.get("max_discount_percentage")
    min_discount_percentage = kwargs.get("min_discount_percentage")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")
    status = kwargs.get("status")
    is_it_last_rule = kwargs.get("is_it_last_rule", False)

    args = []
    inquiry_funct = DiscountRuleModel.scan
    count_funct = DiscountRuleModel.count
    range_key_condition = None
    if item_uuid:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = DiscountRuleModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = DiscountRuleModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = DiscountRuleModel.updated_at < updated_at_lt

        args = [item_uuid, range_key_condition]
        inquiry_funct = DiscountRuleModel.updated_at_index.query
        count_funct = DiscountRuleModel.updated_at_index.count
        if provider_item_uuid and args[1] is None:
            count_funct = DiscountRuleModel.provider_item_uuid_index.count
            args[1] = DiscountRuleModel.provider_item_uuid == provider_item_uuid
            inquiry_funct = DiscountRuleModel.provider_item_uuid_index.query
        elif segment_uuid and args[1] is None:
            count_funct = DiscountRuleModel.segment_uuid_index.count
            args[1] = DiscountRuleModel.segment_uuid == segment_uuid
            inquiry_funct = DiscountRuleModel.segment_uuid_index.query

    the_filters = None  # We can add filters for the query
    if endpoint_id:
        the_filters &= DiscountRuleModel.endpoint_id == endpoint_id
    if (
        provider_item_uuid
        and args[1] is not None
        and inquiry_funct != DiscountRuleModel.provider_item_uuid_index.query
    ):
        the_filters &= DiscountRuleModel.provider_item_uuid == provider_item_uuid
    if (
        segment_uuid
        and args[1] is not None
        and inquiry_funct != DiscountRuleModel.segment_uuid_index.query
    ):
        the_filters &= DiscountRuleModel.segment_uuid == segment_uuid

    # Find the discount tier that matches a specific subtotal value
    # A tier matches when: subtotal_greater_than <= subtotal_value < subtotal_less_than
    if subtotal_value is not None:
        the_filters &= DiscountRuleModel.subtotal_greater_than <= subtotal_value
        # Handle cases where subtotal_less_than might be null (no upper limit)
        the_filters &= (DiscountRuleModel.subtotal_less_than.does_not_exist()) | (
            DiscountRuleModel.subtotal_less_than > subtotal_value
        )
    if max_discount_percentage and min_discount_percentage:
        the_filters &= DiscountRuleModel.max_discount_percentage.between(
            min_discount_percentage, max_discount_percentage
        )
    if status:
        the_filters &= DiscountRuleModel.status == status

    # Filter for rules where subtotal_less_than is None or doesn't exist
    if is_it_last_rule:
        the_filters &= DiscountRuleModel.subtotal_less_than.does_not_exist()

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


def _get_previous_rule(
    info: ResolveInfo,
    **kwargs: Dict[str, Any],
) -> DiscountRuleType | None:
    """
    Gets and validates the previous discount rule.

    Checks:
    1. subtotal_greater_than is provided and >= 0
    2. provider_item_uuid and segment_uuid are provided
    3. If a previous rule exists (subtotal_less_than = None), the new rule's
       subtotal_greater_than must be greater than the previous rule's subtotal_greater_than
       to maintain proper tier ordering

    Args:
        info (ResolveInfo): GraphQL resolve info containing context
        **kwargs: Keyword arguments containing:
            item_uuid (str): The item UUID
            subtotal_greater_than (float): The new rule's lower bound
            provider_item_uuid (str): Provider item UUID
            segment_uuid (str): Segment UUID

    Returns:
        DiscountRuleType: The previous rule object if valid, None if no previous rule exists

    Raises:
        ValueError: If validation fails due to missing required fields or invalid tier ordering
    """

    item_uuid = kwargs.get("item_uuid")
    subtotal_greater_than = float(kwargs.get("subtotal_greater_than", 0))
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")

    # Validate required fields
    if subtotal_greater_than is None:
        raise ValueError("subtotal_greater_than is required for new discount rule")

    if subtotal_greater_than <= 0:
        raise ValueError("subtotal_greater_than must be greater than 0")

    if not provider_item_uuid:
        raise ValueError("provider_item_uuid is required for new discount rule")

    if not segment_uuid:
        raise ValueError("segment_uuid is required for new discount rule")

    # Use resolve_discount_rule_list to find the current last rule
    discount_rule_list = resolve_discount_rule_list(
        info,
        **{
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "segment_uuid": segment_uuid,
            "is_it_last_rule": True,
        },
    )

    # Check if there's a previous rule and validate ordering
    if discount_rule_list.total == 0:
        return None
    else:
        rule = discount_rule_list.discount_rule_list[0]
        if subtotal_greater_than > rule.subtotal_greater_than:
            return rule
        raise ValueError(
            f"New rule's subtotal_greater_than ({subtotal_greater_than}) must be greater than "
            f"the previous rule's subtotal_greater_than ({rule.subtotal_greater_than})"
        )


def _update_previous_rule(
    info: ResolveInfo,
    item_uuid: str,
    previous_rule: "DiscountRuleType",
    subtotal_less_than: float,
    updated_by: str,
) -> None:
    """
    Updates the previous rule's subtotal_less_than using insert_update_discount_rule.

    Args:
        info: GraphQL resolve info
        item_uuid: The item UUID
        previous_rule: The previous rule object to update
        subtotal_less_than: The new upper bound for the previous rule
        updated_by: User making the update
    """
    if previous_rule is None:
        return

    # Use insert_update_discount_rule to update the previous rule
    insert_update_discount_rule(
        info,
        **{
            "item_uuid": item_uuid,
            "discount_rule_uuid": previous_rule.discount_rule_uuid,
            "subtotal_less_than": subtotal_less_than,
            "updated_by": updated_by,
        },
    )


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "discount_rule_uuid",
    },
    model_funct=_get_discount_rule,
    count_funct=get_discount_rule_count,
    type_funct=get_discount_rule_type,
)
def insert_update_discount_rule(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    item_uuid = kwargs.get("item_uuid")
    discount_rule_uuid = kwargs.get("discount_rule_uuid")
    if kwargs.get("entity") is None:
        # Get the previous rule for validation, if any
        previous_rule = _get_previous_rule(info, **kwargs)

        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
            "subtotal_less_than": None,  # Always set to None for new rules
        }
        for key in [
            "provider_item_uuid",
            "segment_uuid",
            "subtotal_greater_than",
            "max_discount_percentage",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        # Save the new rule first
        DiscountRuleModel(
            item_uuid,
            discount_rule_uuid,
            **cols,
        ).save()

        # Update the previous rule's subtotal_less_than if there is one
        if previous_rule is not None:
            _update_previous_rule(
                info=info,
                item_uuid=item_uuid,
                previous_rule=previous_rule,
                subtotal_less_than=kwargs["subtotal_greater_than"],
                updated_by=kwargs["updated_by"],
            )

        return

    discount_rule = kwargs.get("entity")
    actions = [
        DiscountRuleModel.updated_by.set(kwargs["updated_by"]),
        DiscountRuleModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to DiscountRuleModel attributes
    field_map = {
        "provider_item_uuid": DiscountRuleModel.provider_item_uuid,
        "segment_uuid": DiscountRuleModel.segment_uuid,
        "subtotal_greater_than": DiscountRuleModel.subtotal_greater_than,
        "subtotal_less_than": DiscountRuleModel.subtotal_less_than,
        "max_discount_percentage": DiscountRuleModel.max_discount_percentage,
        "status": DiscountRuleModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the discount rule
    discount_rule.update(actions=actions)
    return


@purge_cache()
@delete_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "discount_rule_uuid",
    },
    model_funct=get_discount_rule,
)
def delete_discount_rule(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_rule"),
)
def get_discount_rules_by_item(item_uuid: str) -> Any:
    discount_rules = []
    for rule in DiscountRuleModel.query(item_uuid):
        discount_rules.append(rule)
    return discount_rules
