#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders
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
        """Resolve nested ProviderItem for this rule using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "provider_item", None)
        if isinstance(existing, dict):
            return ProviderItemType(**existing)
        if isinstance(existing, ProviderItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        endpoint_id = getattr(parent, "endpoint_id", None)
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not endpoint_id or not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_loader.load((endpoint_id, provider_item_uuid)).then(
            lambda pi_dict: ProviderItemType(**pi_dict) if pi_dict else None
        )

    def resolve_segment(parent, info):
        """Resolve nested Segment for this rule using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "segment", None)
        if isinstance(existing, dict):
            return SegmentType(**existing)
        if isinstance(existing, SegmentType):
            return existing

        # Case 1: need to fetch using DataLoader
        endpoint_id = getattr(parent, "endpoint_id", None)
        segment_uuid = getattr(parent, "segment_uuid", None)
        if not endpoint_id or not segment_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.segment_loader.load((endpoint_id, segment_uuid)).then(
            lambda segment_dict: SegmentType(**segment_dict) if segment_dict else None
        )


class DiscountRuleListType(ListObjectType):
    discount_rule_list = List(DiscountRuleType)
