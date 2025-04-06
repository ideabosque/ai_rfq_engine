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
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility
from tenacity import retry, stop_after_attempt, wait_exponential

from ..types.discount_rule import DiscountRuleListType, DiscountRuleType
from .utils import _get_provider_item, _get_segment


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


class DiscountRuleModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-discount_rules"

    item_uuid = UnicodeAttribute(hash_key=True)
    discount_rule_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    segment_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    subtotal_greater_than = NumberAttribute()
    subtotal_less_than = NumberAttribute()
    max_discount_percentage = NumberAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_item_uuid_index = ProviderItemUuidIndex()
    segment_uuid_index = SegmentUuidIndex()


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
def get_discount_rule(item_uuid: str, discount_rule_uuid: str) -> DiscountRuleModel:
    return DiscountRuleModel.get(item_uuid, discount_rule_uuid)


def get_discount_rule_count(item_uuid: str, discount_rule_uuid: str) -> int:
    return DiscountRuleModel.count(
        item_uuid, DiscountRuleModel.discount_rule_uuid == discount_rule_uuid
    )


def get_discount_rule_type(
    info: ResolveInfo, discount_rule: DiscountRuleModel
) -> DiscountRuleType:
    try:
        provider_item = _get_provider_item(
            discount_rule.item_uuid, discount_rule.provider_item_uuid
        )
        segment = _get_segment(info.context["endpoint_id"], discount_rule.segment_uuid)
        discount_rule = discount_rule.__dict__["attribute_values"]
        discount_rule.update(
            {
                "provider_item": provider_item,
                "segment": segment,
            }
        )
        discount_rule.pop("endpoint_id")
        discount_rule.pop("provider_item_uuid")
        discount_rule.pop("segment_uuid")
        discount_rule.pop("item_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return DiscountRuleType(**Utility.json_loads(Utility.json_dumps(discount_rule)))


def resolve_discount_rule(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountRuleType:
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
    ],
    list_type_class=DiscountRuleListType,
    type_funct=get_discount_rule_type,
)
def resolve_discount_rule_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    item_uuid = kwargs.get("item_uuid")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    segment_uuid = kwargs.get("segment_uuid")
    endpoint_id = info.context["endpoint_id"]
    max_subtotal_greater_than = kwargs.get("max_subtotal_greater_than")
    min_subtotal_greater_than = kwargs.get("min_subtotal_greater_than")
    max_subtotal_less_than = kwargs.get("max_subtotal_less_than")
    min_subtotal_less_than = kwargs.get("min_subtotal_less_than")
    max_discount_percentage = kwargs.get("max_discount_percentage")
    min_discount_percentage = kwargs.get("min_discount_percentage")

    args = []
    inquiry_funct = DiscountRuleModel.scan
    count_funct = DiscountRuleModel.count
    if item_uuid:
        args = [item_uuid, None]
        inquiry_funct = DiscountRuleModel.query
        if provider_item_uuid:
            count_funct = DiscountRuleModel.provider_item_uuid_index.count
            args[1] = DiscountRuleModel.provider_item_uuid == provider_item_uuid
            inquiry_funct = DiscountRuleModel.provider_item_uuid_index.query
        elif segment_uuid:
            count_funct = DiscountRuleModel.segment_uuid_index.count
            args[1] = DiscountRuleModel.segment_uuid == segment_uuid
            inquiry_funct = DiscountRuleModel.segment_uuid_index.query

    the_filters = None  # We can add filters for the query
    if endpoint_id:
        the_filters &= DiscountRuleModel.endpoint_id == endpoint_id
    if max_subtotal_greater_than and min_subtotal_greater_than:
        the_filters &= DiscountRuleModel.subtotal_greater_than.between(
            min_subtotal_greater_than, max_subtotal_greater_than
        )
    if max_subtotal_less_than and min_subtotal_less_than:
        the_filters &= DiscountRuleModel.subtotal_less_than.between(
            min_subtotal_less_than, max_subtotal_less_than
        )
    if max_discount_percentage and min_discount_percentage:
        the_filters &= DiscountRuleModel.max_discount_percentage.between(
            min_discount_percentage, max_discount_percentage
        )
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "item_uuid",
        "range_key": "discount_rule_uuid",
    },
    model_funct=get_discount_rule,
    count_funct=get_discount_rule_count,
    type_funct=get_discount_rule_type,
)
def insert_update_discount_rule(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    item_uuid = kwargs.get("item_uuid")
    discount_rule_uuid = kwargs.get("discount_rule_uuid")
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
            "subtotal_greater_than",
            "subtotal_less_than",
            "max_discount_percentage",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        DiscountRuleModel(
            item_uuid,
            discount_rule_uuid,
            **cols,
        ).save()
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
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the discount rule
    discount_rule.update(actions=actions)
    return


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
