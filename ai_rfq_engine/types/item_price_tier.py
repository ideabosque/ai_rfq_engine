#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders
from .provider_item import ProviderItemType
from .provider_item_batches import ProviderItemBatchType
from .segment import SegmentType


class ItemPriceTierType(ObjectType):
    endpoint_id = String()
    item_uuid = String()
    item_price_tier_uuid = String()
    provider_item_uuid = String()  # keep raw id
    segment_uuid = String()  # keep raw id
    quantity_greater_then = String()
    quantity_less_then = String()
    margin_per_uom = String()
    price_per_uom = String()
    status = String()

    # Nested resolvers: strongly-typed nested relationships
    provider_item = Field(lambda: ProviderItemType)
    segment = Field(lambda: SegmentType)
    provider_item_batches = List(lambda: ProviderItemBatchType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_provider_item(parent, info):
        """Resolve nested ProviderItem for this price tier using DataLoader."""
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
        """Resolve nested Segment for this price tier using DataLoader."""
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

    def resolve_provider_item_batches(parent, info):
        """
        Resolve provider_item_batches dynamically.
        This is lazily loaded only when requested and only if margin_per_uom is set.
        """
        # Case 2: already embedded (from get_item_price_tier_type)
        existing = getattr(parent, "provider_item_batches", None)
        if isinstance(existing, list) and len(existing) > 0:
            # Convert dicts to types if needed
            if isinstance(existing[0], dict):
                return [ProviderItemBatchType(**batch) for batch in existing]
            return existing

        # Case 1: need to fetch (only if margin_per_uom is set)
        margin_per_uom = getattr(parent, "margin_per_uom", None)
        if not margin_per_uom:
            return []

        # Fetch batches from database
        from ..models.provider_item_batches import ProviderItemBatchModel

        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not provider_item_uuid:
            return []

        try:
            batches = ProviderItemBatchModel.query(provider_item_uuid)
            result = []
            for batch in batches:
                batch_dict = batch.__dict__["attribute_values"]
                # Calculate price_per_uom for this batch
                total_cost = float(batch_dict.get("total_cost_per_uom", 0))
                margin = float(margin_per_uom)
                price_per_uom = total_cost * (1 + margin)
                batch_dict["price_per_uom"] = str(price_per_uom)
                batch_dict.pop("endpoint_id", None)
                valid_fields = ProviderItemBatchType._meta.fields.keys()
                filtered_batch_dict = {k: v for k, v in batch_dict.items() if k in valid_fields}
                result.append(ProviderItemBatchType(**filtered_batch_dict))
            return result
        except Exception:
            return []


class ItemPriceTierListType(ListObjectType):
    item_price_tier_list = List(ItemPriceTierType)
