#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType

from ..models.utils import _get_provider_item, _get_segment
from .provider_item import ProviderItemType
from .segment import SegmentType


class DiscountRuleType(ObjectType):
    endpoint_id = String()
    item_uuid = String()
    discount_rule_uuid = String()
    provider_item_uuid = String()  # keep raw id
    segment_uuid = String()  # keep raw id
    subtotal_greater_than = String()
    subtotal_less_than = String()
    max_discount_percentage = String()
    status = String()

    # Nested resolvers: strongly-typed nested relationships
    provider_item = Field(lambda: ProviderItemType)
    segment = Field(lambda: SegmentType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_provider_item(parent, info):
        """Resolve nested ProviderItem for this rule."""
        # Case 2: already embedded
        existing = getattr(parent, "provider_item", None)
        if isinstance(existing, dict):
            return ProviderItemType(**existing)
        if isinstance(existing, ProviderItemType):
            return existing

        # Case 1: need to fetch
        endpoint_id = getattr(parent, "endpoint_id", None)
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not endpoint_id or not provider_item_uuid:
            return None

        pi_dict = _get_provider_item(endpoint_id, provider_item_uuid)
        if not pi_dict:
            return None
        return ProviderItemType(**pi_dict)

    def resolve_segment(parent, info):
        """Resolve nested Segment for this rule."""
        # Case 2: already embedded
        existing = getattr(parent, "segment", None)
        if isinstance(existing, dict):
            return SegmentType(**existing)
        if isinstance(existing, SegmentType):
            return existing

        # Case 1: need to fetch
        endpoint_id = getattr(parent, "endpoint_id", None)
        segment_uuid = getattr(parent, "segment_uuid", None)
        if not endpoint_id or not segment_uuid:
            return None

        segment_dict = _get_segment(endpoint_id, segment_uuid)
        if not segment_dict:
            return None
        return SegmentType(**segment_dict)


class DiscountRuleListType(ListObjectType):
    discount_rule_list = List(DiscountRuleType)
