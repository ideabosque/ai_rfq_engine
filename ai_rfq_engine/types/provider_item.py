#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.utils import _get_item
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

    # ------- Nested resolvers -------

    def resolve_item(parent, info):
        """
        Resolve nested Item for this provider_item.

        Works in two cases:
        1) ProviderItem came from get_provider_item_type -> has item_uuid
        2) ProviderItem came from _get_provider_item -> already has item dict
        """
        # Case 2: already embedded (e.g., via _get_provider_item)
        existing = getattr(parent, "item", None)
        if isinstance(existing, dict):
            return ItemType(**existing)
        if isinstance(existing, ItemType):
            return existing

        # Case 1: need to fetch by endpoint_id + item_uuid
        endpoint_id = getattr(parent, "endpoint_id", None)
        item_uuid = getattr(parent, "item_uuid", None)
        if not endpoint_id or not item_uuid:
            return None

        item_dict = _get_item(endpoint_id, item_uuid)
        if not item_dict:
            return None
        return ItemType(**item_dict)


class ProviderItemListType(ListObjectType):
    provider_item_list = List(ProviderItemType)
