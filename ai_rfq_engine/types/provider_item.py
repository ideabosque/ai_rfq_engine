#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"


from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.batch_loaders import get_loaders
from .item import ItemType


class ProviderItemType(ObjectType):
    endpoint_id = String()
    provider_item_uuid = String()
    provider_corp_external_id = String()
    external_id = String()
    base_price_per_uom = String()
    item_spec = JSON()  # Keep as JSON since it's a MapAttribute

    # Nested resolver: strongly-typed nested relationship
    item_uuid = String()  # keep raw id
    item = Field(lambda: ItemType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    batches = List(
        lambda: "ai_rfq_engine.types.provider_item_batches.ProviderItemBatchType"
    )
    price_tiers = List(lambda: "ai_rfq_engine.types.item_price_tier.ItemPriceTierType")

    # ------- Nested resolvers -------

    def resolve_item(parent, info):
        """Resolve nested Item for this provider_item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "item", None)
        if isinstance(existing, dict):
            return ItemType(**existing)
        if isinstance(existing, ItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        item_uuid = getattr(parent, "item_uuid", None)
        if not endpoint_id or not item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.item_loader.load((endpoint_id, item_uuid)).then(
            lambda item_dict: ItemType(**item_dict) if item_dict else None
        )

    def resolve_batches(parent, info):
        """Resolve nested ProviderItemBatches for this provider item."""
        # Case 2: already embedded
        existing = getattr(parent, "batches", None)
        if isinstance(existing, list) and existing:
            from .provider_item_batches import ProviderItemBatchType

            converted = []
            for batch in existing:
                if isinstance(batch, dict):
                    converted.append(ProviderItemBatchType(**batch))
                elif isinstance(batch, ProviderItemBatchType):
                    converted.append(batch)
            if converted:
                return converted

        # Case 1: need to fetch on demand
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not provider_item_uuid:
            return []

        from .provider_item_batches import ProviderItemBatchType

        loaders = get_loaders(info.context)
        return loaders.provider_item_batch_list_loader.load(
            provider_item_uuid
        ).then(
            lambda batch_list: [
                ProviderItemBatchType(**batch) if isinstance(batch, dict) else batch
                for batch in batch_list
            ]
        )

    def resolve_price_tiers(parent, info):
        """Resolve nested ItemPriceTiers for this provider item."""
        # Case 2: already embedded
        existing = getattr(parent, "price_tiers", None)
        if isinstance(existing, list) and existing:
            from .item_price_tier import ItemPriceTierType

            converted = []
            for tier in existing:
                if isinstance(tier, dict):
                    converted.append(ItemPriceTierType(**tier))
                elif isinstance(tier, ItemPriceTierType):
                    converted.append(tier)
            if converted:
                return converted

        # Case 1: need to fetch on demand
        item_uuid = getattr(parent, "item_uuid", None)
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not item_uuid or not provider_item_uuid:
            return []

        from .item_price_tier import ItemPriceTierType

        loaders = get_loaders(info.context)
        return loaders.item_price_tier_by_provider_item_loader.load(
            (item_uuid, provider_item_uuid)
        ).then(
            lambda tiers: [
                ItemPriceTierType(**tier) if isinstance(tier, dict) else tier
                for tier in tiers
            ]
        )


class ProviderItemListType(ListObjectType):
    provider_item_list = List(ProviderItemType)
