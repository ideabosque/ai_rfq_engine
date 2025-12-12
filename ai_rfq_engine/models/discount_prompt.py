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
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from tenacity import retry, stop_after_attempt, wait_exponential

from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility, method_cache

from ..handlers.config import Config
from ..types.discount_prompt import DiscountPromptListType, DiscountPromptType


# Status constants for DiscountPrompt
class DiscountPromptStatus:
    IN_REVIEW = "in_review"
    ACTIVE = "active"
    INACTIVE = "inactive"


# Scope constants for DiscountPrompt
class DiscountPromptScope:
    GLOBAL = "global"
    SEGMENT = "segment"
    ITEM = "item"
    PROVIDER_ITEM = "provider_item"


def validate_and_normalize_discount_rules(discount_rules):
    """
    Validates and normalizes discount rules to ensure:
    1. Rules are sorted by greater_than (low to high)
    2. First tier starts at 0
    3. Tiers are ordered from low to high (greater_than < less_than, except last tier)
    4. Last tier has no less_than (open-ended upper bound)
    5. Each tier's less_than equals the next tier's greater_than (no gaps/overlaps)
    6. max_discount_percentage INCREASES as tiers increase (higher subtotals get higher discounts)

    Args:
        discount_rules: List of discount rule dictionaries

    Returns:
        List of normalized and sorted discount rules

    Raises:
        ValueError: If validation fails
    """
    if not discount_rules or len(discount_rules) == 0:
        return []

    # Normalize to float values first
    normalized_rules = []
    for rule in discount_rules:
        normalized_rule = {
            "greater_than": float(rule.get("greater_than", 0)),
            "max_discount_percentage": float(rule.get("max_discount_percentage", 0)),
        }
        # less_than is optional (last tier won't have it)
        if "less_than" in rule and rule.get("less_than") is not None:
            normalized_rule["less_than"] = float(rule["less_than"])

        normalized_rules.append(normalized_rule)

    # Sort by greater_than to ensure proper tier ordering
    sorted_rules = sorted(normalized_rules, key=lambda x: x["greater_than"])

    # Validate first tier starts at 0
    if sorted_rules[0]["greater_than"] != 0:
        raise ValueError(
            f"First tier must start at 0, but starts at {sorted_rules[0]['greater_than']}"
        )

    # Validate each rule
    for i, rule in enumerate(sorted_rules):
        greater_than = rule["greater_than"]
        less_than = rule.get("less_than")
        max_discount_percentage = rule["max_discount_percentage"]
        is_last_tier = i == len(sorted_rules) - 1

        # Validate current rule bounds
        if greater_than < 0:
            raise ValueError(f"Rule {i}: greater_than ({greater_than}) must be >= 0")

        # Last tier should NOT have less_than
        if is_last_tier:
            if less_than is not None:
                raise ValueError(
                    f"Rule {i}: Last tier should not have less_than (should be open-ended)"
                )
        else:
            # Non-last tiers MUST have less_than
            if less_than is None:
                raise ValueError(f"Rule {i}: Non-last tier must have less_than value")
            if less_than <= greater_than:
                raise ValueError(
                    f"Rule {i}: less_than ({less_than}) must be greater than greater_than ({greater_than})"
                )

        if max_discount_percentage < 0 or max_discount_percentage > 100:
            raise ValueError(
                f"Rule {i}: max_discount_percentage ({max_discount_percentage}) must be between 0 and 100"
            )

        # Validate tier ordering with next rule
        if i < len(sorted_rules) - 1:
            next_rule = sorted_rules[i + 1]
            next_greater_than = next_rule["greater_than"]
            next_max_discount = next_rule["max_discount_percentage"]

            # Check that current less_than equals next greater_than (no gaps/overlaps)
            if less_than != next_greater_than:
                raise ValueError(
                    f"Rule {i}: less_than ({less_than}) must equal next rule's greater_than ({next_greater_than})"
                )

            # Check that max_discount_percentage INCREASES (higher tiers get better discounts)
            if max_discount_percentage >= next_max_discount:
                raise ValueError(
                    f"Rule {i}: max_discount_percentage ({max_discount_percentage}) must be less than "
                    f"next tier's max_discount_percentage ({next_max_discount}). "
                    f"Discount percentages should INCREASE as tiers increase (higher purchases = better discounts)."
                )

    return sorted_rules


# Legacy function for backward compatibility - now just calls the validate function
discount_rules_fn = lambda discount_rules: validate_and_normalize_discount_rules(
    discount_rules
)


class ScopeIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "segment_uuid-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    scope = UnicodeAttribute(range_key=True)


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


class DiscountPromptModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-discount_prompts"

    endpoint_id = UnicodeAttribute(hash_key=True)
    discount_prompt_uuid = UnicodeAttribute(range_key=True)
    scope = UnicodeAttribute()
    tags = ListAttribute()
    discount_prompt = UnicodeAttribute()
    conditions = ListAttribute()
    discount_rules = ListAttribute(of=MapAttribute)
    priority = NumberAttribute(default=0)
    status = UnicodeAttribute(default=DiscountPromptStatus.IN_REVIEW)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    scope_index = ScopeIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Use cascading cache purging for discount_prompts
                from ..models.cache import purge_entity_cascading_cache

                endpoint_id = args[0].context.get("endpoint_id") or kwargs.get(
                    "endpoint_id"
                )
                context_keys = {"endpoint_id": endpoint_id} if endpoint_id else None
                entity_keys = {}
                if kwargs.get("endpoint_id"):
                    entity_keys["endpoint_id"] = kwargs.get("endpoint_id")
                if kwargs.get("discount_prompt_uuid"):
                    entity_keys["discount_prompt_uuid"] = kwargs.get(
                        "discount_prompt_uuid"
                    )

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="discount_prompt",
                    context_keys=context_keys,
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


def create_discount_prompt_table(logger: logging.Logger) -> bool:
    """Create the DiscountPrompt table if it doesn't exist."""
    if not DiscountPromptModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        DiscountPromptModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The DiscountPrompt table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_prompt"),
)
def get_discount_prompts_by_segment(endpoint_id: str, segment_uuid: str) -> Any:
    """
    Get all ACTIVE discount prompts with scope='segment' for a segment.

    Note: Returns only SEGMENT-scoped prompts. GLOBAL scope is loaded separately
    by the batch loader to avoid duplication.
    """
    prompts = []
    for prompt in DiscountPromptModel.scope_index.query(
        endpoint_id,
        DiscountPromptModel.scope == DiscountPromptScope.SEGMENT,
        filter_condition=(
            (DiscountPromptModel.status == DiscountPromptStatus.ACTIVE)
            & DiscountPromptModel.tags.contains(segment_uuid)
        ),
    ):
        prompts.append(prompt)
    return prompts


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_prompt"),
)
def get_discount_prompts_by_item(endpoint_id: str, item_uuid: str) -> Any:
    """
    Get all ACTIVE discount prompts with scope='item' for an item.

    Note: Returns only ITEM-scoped prompts. GLOBAL and SEGMENT scopes are loaded
    separately by the batch loader to avoid duplication.
    """
    prompts = []
    for prompt in DiscountPromptModel.scope_index.query(
        endpoint_id,
        DiscountPromptModel.scope == DiscountPromptScope.ITEM,
        filter_condition=(
            (DiscountPromptModel.status == DiscountPromptStatus.ACTIVE)
            & DiscountPromptModel.tags.contains(item_uuid)
        ),
    ):
        prompts.append(prompt)
    return prompts


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_prompt"),
)
def get_discount_prompts_by_provider_item(
    endpoint_id: str, provider_item_uuid: str
) -> Any:
    """
    Get all ACTIVE discount prompts with scope='provider_item'.

    Note: Returns only PROVIDER_ITEM-scoped prompts. GLOBAL, SEGMENT, and ITEM scopes
    are loaded separately by the batch loader to avoid duplication.
    """
    prompts = []
    for prompt in DiscountPromptModel.scope_index.query(
        endpoint_id,
        DiscountPromptModel.scope == DiscountPromptScope.PROVIDER_ITEM,
        filter_condition=(
            (DiscountPromptModel.status == DiscountPromptStatus.ACTIVE)
            & DiscountPromptModel.tags.contains(provider_item_uuid)
        ),
    ):
        prompts.append(prompt)
    return prompts


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_prompt"),
)
def get_global_discount_prompts(endpoint_id: str) -> Any:
    """Get all ACTIVE global discount prompts for an endpoint."""
    prompts = []
    for prompt in DiscountPromptModel.scope_index.query(
        endpoint_id,
        DiscountPromptModel.scope == DiscountPromptScope.GLOBAL,
        filter_condition=(DiscountPromptModel.status == DiscountPromptStatus.ACTIVE),
    ):
        prompts.append(prompt)
    return prompts


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "discount_prompt"),
)
def get_discount_prompt(
    endpoint_id: str, discount_prompt_uuid: str
) -> DiscountPromptModel:
    return DiscountPromptModel.get(endpoint_id, discount_prompt_uuid)


def get_discount_prompt_count(endpoint_id: str, discount_prompt_uuid: str) -> int:
    return DiscountPromptModel.count(
        endpoint_id, DiscountPromptModel.discount_prompt_uuid == discount_prompt_uuid
    )


def get_discount_prompt_type(
    info: ResolveInfo, discount_prompt: DiscountPromptModel
) -> DiscountPromptType:
    """
    Convert DiscountPromptModel to a dictionary type.
    """
    try:
        prompt_dict = discount_prompt.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return DiscountPromptType(**Utility.json_normalize(prompt_dict))


def resolve_discount_prompt(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountPromptType | None:
    count = get_discount_prompt_count(
        info.context["endpoint_id"], kwargs["discount_prompt_uuid"]
    )
    if count == 0:
        return None

    return get_discount_prompt_type(
        info,
        get_discount_prompt(
            info.context["endpoint_id"], kwargs["discount_prompt_uuid"]
        ),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "endpoint_id",
        "discount_prompt_uuid",
        "scope",
        "updated_at",
    ],
    list_type_class=DiscountPromptListType,
    type_funct=get_discount_prompt_type,
)
def resolve_discount_prompt_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    endpoint_id = info.context["endpoint_id"]
    scope = kwargs.get("scope")
    tags = kwargs.get("tags")
    status = kwargs.get("status")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = DiscountPromptModel.scan
    count_funct = DiscountPromptModel.count
    range_key_condition = None

    if endpoint_id:
        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = DiscountPromptModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = DiscountPromptModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = DiscountPromptModel.updated_at < updated_at_lt

        args = [endpoint_id, range_key_condition]
        inquiry_funct = DiscountPromptModel.updated_at_index.query
        count_funct = DiscountPromptModel.updated_at_index.count

        if scope and args[1] is None:
            count_funct = DiscountPromptModel.scope_index.count
            args[1] = DiscountPromptModel.scope == scope
            inquiry_funct = DiscountPromptModel.scope_index.query

    the_filters = None  # We can add filters for the query
    if (
        scope
        and args[1] is not None
        and inquiry_funct != DiscountPromptModel.scope_index.query
    ):
        the_filters &= DiscountPromptModel.scope == scope

    if tags:
        for tag in tags:
            the_filters &= DiscountPromptModel.tags.contains(tag)

    if status:
        the_filters &= DiscountPromptModel.status == status

    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "discount_prompt_uuid",
    },
    model_funct=get_discount_prompt,
    count_funct=get_discount_prompt_count,
    type_funct=get_discount_prompt_type,
)
def insert_update_discount_prompt(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id")
    discount_prompt_uuid = kwargs.get("discount_prompt_uuid")

    if kwargs.get("entity") is None:
        cols = {
            "conditions": [],
            "discount_rules": [],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
            "status": kwargs.get(
                "status", DiscountPromptStatus.IN_REVIEW
            ),  # Default status
            "priority": kwargs.get("priority", 0),  # Default priority
        }
        for key in [
            "scope",
            "tags",
            "discount_prompt",
            "conditions",
            "discount_rules",
        ]:
            if key in kwargs:
                if key == "discount_rules" and kwargs[key]:
                    cols[key] = discount_rules_fn(kwargs[key])
                else:
                    cols[key] = kwargs[key]

        DiscountPromptModel(
            endpoint_id,
            discount_prompt_uuid,
            **cols,
        ).save()
        return

    discount_prompt = kwargs.get("entity")
    actions = [
        DiscountPromptModel.updated_by.set(kwargs["updated_by"]),
        DiscountPromptModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Special handling for discount_rules - merge existing with new
    if "discount_rules" in kwargs and kwargs["discount_rules"]:
        # Get existing rules from the entity
        existing_rules = []
        try:
            existing_rules = (
                list(discount_prompt.discount_rules)
                if discount_prompt.discount_rules
                else []
            )
        except Exception:
            existing_rules = []

        # Convert existing rules to dict format for merging
        existing_rules_dict = {
            rule.get("greater_than", 0): rule for rule in existing_rules
        }

        # Merge new rules with existing ones (new rules override existing ones with same greater_than)
        for new_rule in kwargs["discount_rules"]:
            greater_than_key = new_rule.get("greater_than", 0)
            existing_rules_dict[greater_than_key] = new_rule

        # Get merged list and validate/normalize
        merged_rules = list(existing_rules_dict.values())
        validated_rules = discount_rules_fn(merged_rules)
        actions.append(DiscountPromptModel.discount_rules.set(validated_rules))

    # Map of kwargs keys to DiscountPromptModel attributes (excluding discount_rules, handled above)
    field_map = {
        "scope": DiscountPromptModel.scope,
        "tags": DiscountPromptModel.tags,
        "discount_prompt": DiscountPromptModel.discount_prompt,
        "conditions": DiscountPromptModel.conditions,
        "priority": DiscountPromptModel.priority,
        "status": DiscountPromptModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the discount prompt
    discount_prompt.update(actions=actions)
    return


@purge_cache()
@delete_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "discount_prompt_uuid",
    },
    model_funct=get_discount_prompt,
)
def delete_discount_prompt(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
