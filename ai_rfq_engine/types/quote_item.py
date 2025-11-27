#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.batch_loaders import get_loaders


class QuoteItemType(ObjectType):
    quote_uuid = String()
    quote_item_uuid = String()
    provider_item_uuid = String()
    item_uuid = String()
    segment_uuid = String()
    batch_no = String()
    qty = String()
    price_per_uom = String()
    subtotal = String()
    subtotal_discount = String()
    final_subtotal = String()
    guardrail_price_per_uom = String()
    slow_move_item = Boolean()

    # Keep as JSON (MapAttribute)
    request_data = JSON()

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    item = Field(lambda: "ai_rfq_engine.types.item.ItemType")
    provider_item = Field(lambda: "ai_rfq_engine.types.provider_item.ProviderItemType")
    segment = Field(lambda: "ai_rfq_engine.types.segment.SegmentType")

    # ------- Nested resolvers -------

    def resolve_item(parent, info):
        """Resolve nested Item for this quote item using DataLoader."""
        from .item import ItemType

        # Check if already embedded
        existing = getattr(parent, "item", None)
        if isinstance(existing, dict):
            return ItemType(**existing)
        if isinstance(existing, ItemType):
            return existing

        # Fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        item_uuid = getattr(parent, "item_uuid", None)
        if not endpoint_id or not item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.item_loader.load((endpoint_id, item_uuid)).then(
            lambda item_dict: ItemType(**item_dict) if item_dict else None
        )

    def resolve_provider_item(parent, info):
        """Resolve nested ProviderItem for this quote item using DataLoader."""
        from .provider_item import ProviderItemType

        # Check if already embedded
        existing = getattr(parent, "provider_item", None)
        if isinstance(existing, dict):
            return ProviderItemType(**existing)
        if isinstance(existing, ProviderItemType):
            return existing

        # Fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not endpoint_id or not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_loader.load(
            (endpoint_id, provider_item_uuid)
        ).then(lambda pi_dict: ProviderItemType(**pi_dict) if pi_dict else None)

    def resolve_segment(parent, info):
        """Resolve nested Segment for this quote item using DataLoader."""
        from .segment import SegmentType

        # Check if already embedded
        existing = getattr(parent, "segment", None)
        if isinstance(existing, dict):
            return SegmentType(**existing)
        if isinstance(existing, SegmentType):
            return existing

        # Fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        segment_uuid = getattr(parent, "segment_uuid", None)
        if not endpoint_id or not segment_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.segment_loader.load((endpoint_id, segment_uuid)).then(
            lambda segment_dict: SegmentType(**segment_dict) if segment_dict else None
        )


class QuoteItemListType(ListObjectType):
    quote_item_list = List(QuoteItemType)
