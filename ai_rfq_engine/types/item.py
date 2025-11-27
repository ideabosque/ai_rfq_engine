#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders
from .discount_rule import DiscountRuleType
from .item_price_tier import ItemPriceTierType
from .provider_item import ProviderItemType


class ItemType(ObjectType):
    endpoint_id = String()
    item_uuid = String()
    item_type = String()
    item_name = String()
    item_description = String()
    uom = String()
    item_external_id = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    provider_items = List(lambda: "ai_rfq_engine.types.provider_item.ProviderItemType")
    price_tiers = List(lambda: "ai_rfq_engine.types.item_price_tier.ItemPriceTierType")
    discount_rules = List(lambda: "ai_rfq_engine.types.discount_rule.DiscountRuleType")

    # ------- Nested resolvers -------

    def resolve_provider_items(parent, info):
        """Resolve nested ProviderItems for this item."""
        # Check if already embedded
        existing = getattr(parent, "provider_items", None)
        if isinstance(existing, list) and existing:
            return [
                ProviderItemType(**pi) if isinstance(pi, dict) else pi
                for pi in existing
            ]

        # Fetch provider items for this item
        endpoint_id = info.context.get("endpoint_id")
        item_uuid = getattr(parent, "item_uuid", None)
        if not endpoint_id or not item_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.provider_items_by_item_loader.load(
            (endpoint_id, item_uuid)
        ).then(
            lambda pis: [
                ProviderItemType(**pi) if isinstance(pi, dict) else pi for pi in pis
            ]
        )

    def resolve_price_tiers(parent, info):
        """Resolve nested ItemPriceTiers for this item."""
        # Check if already embedded
        existing = getattr(parent, "price_tiers", None)
        if isinstance(existing, list) and existing:
            return [
                ItemPriceTierType(**tier) if isinstance(tier, dict) else tier
                for tier in existing
            ]

        # Fetch price tiers for this item
        item_uuid = getattr(parent, "item_uuid", None)
        if not item_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.item_price_tier_by_item_loader.load(item_uuid).then(
            lambda tiers: [
                ItemPriceTierType(**tier) if isinstance(tier, dict) else tier
                for tier in tiers
            ]
        )

    def resolve_discount_rules(parent, info):
        """Resolve nested DiscountRules for this item."""
        # Check if already embedded
        existing = getattr(parent, "discount_rules", None)
        if isinstance(existing, list) and existing:
            return [
                DiscountRuleType(**rule) if isinstance(rule, dict) else rule
                for rule in existing
            ]

        # Fetch discount rules for this item
        item_uuid = getattr(parent, "item_uuid", None)
        if not item_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.discount_rule_by_item_loader.load(item_uuid).then(
            lambda rules: [
                DiscountRuleType(**rule) if isinstance(rule, dict) else rule
                for rule in rules
            ]
        )


class ItemListType(ListObjectType):
    item_list = List(ItemType)
