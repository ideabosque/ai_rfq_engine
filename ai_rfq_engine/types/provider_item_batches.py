#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, Field, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders


class ProviderItemBatchType(ObjectType):
    provider_item_uuid = String()  # keep raw id
    batch_no = String()
    item_uuid = String()  # keep raw id
    cost_per_uom = String()
    freight_cost_per_uom = String()
    additional_cost_per_uom = String()
    total_cost_per_uom = String()
    guardrail_margin_per_uom = String()
    guardrail_price_per_uom = String()
    in_stock = Boolean()
    slow_move_item = Boolean()

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
        endpoint_id = info.context.get("endpoint_id")
        item_uuid = getattr(parent, "item_uuid", None)
        if not endpoint_id or not item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.item_loader.load((endpoint_id, item_uuid)).then(
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
        endpoint_id = info.context.get("endpoint_id")
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not endpoint_id or not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_loader.load(
            (endpoint_id, provider_item_uuid)
        ).then(lambda pi_dict: ProviderItemType(**pi_dict) if pi_dict else None)


class ProviderItemBatchListType(ListObjectType):
    provider_item_batch_list = List(ProviderItemBatchType)


# Bottom imports - imported after class definitions to avoid circular imports
from .item import ItemType
from .provider_item import ProviderItemType
