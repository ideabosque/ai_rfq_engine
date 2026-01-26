#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import SafeFloat as Float

from ..models.batch_loaders import get_loaders


class ProviderItemBatchType(ObjectType):
    provider_item_uuid = String()  # keep raw id
    batch_no = String()
    item_uuid = String()  # keep raw id
    partition_key = String()
    partition_key = String()
    cost_per_uom = Float()
    freight_cost_per_uom = Float()
    additional_cost_per_uom = Float()
    total_cost_per_uom = Float()
    guardrail_margin_per_uom = Float()
    guardrail_price_per_uom = Float()
    in_stock = Boolean()
    slow_move_item = Boolean()
    expired_at = DateTime()
    produced_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    item = Field(lambda: ItemType)
    provider_item = Field(lambda: ProviderItemType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_item(parent, info):
        """Resolve nested Item for this batch using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "item", None)
        if isinstance(existing, dict):
            return ItemType(**existing)
        if isinstance(existing, ItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = info.context.get("partition_key")
        item_uuid = getattr(parent, "item_uuid", None)
        if not partition_key or not item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.item_loader.load((partition_key, item_uuid)).then(
            lambda item_dict: ItemType(**item_dict) if item_dict else None
        )

    def resolve_provider_item(parent, info):
        """Resolve nested ProviderItem for this batch using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "provider_item", None)
        if isinstance(existing, dict):
            return ProviderItemType(**existing)
        if isinstance(existing, ProviderItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = info.context.get("partition_key")
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not partition_key or not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_loader.load(
            (partition_key, provider_item_uuid)
        ).then(lambda pi_dict: ProviderItemType(**pi_dict) if pi_dict else None)


class ProviderItemBatchListType(ListObjectType):
    provider_item_batch_list = List(ProviderItemBatchType)


# Bottom imports - imported after class definitions to avoid circular imports
from .item import ItemType
from .provider_item import ProviderItemType
