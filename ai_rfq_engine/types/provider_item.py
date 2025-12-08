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
    # external_id = String()
    base_price_per_uom = String()
    item_spec = JSON()  # Keep as JSON since it's a MapAttribute

    # Nested resolver: strongly-typed nested relationship
    item_uuid = String()  # keep raw id
    item = Field(lambda: ItemType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

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


class ProviderItemListType(ListObjectType):
    provider_item_list = List(ProviderItemType)
