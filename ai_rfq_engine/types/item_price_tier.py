#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType


class ItemPriceTierType(ObjectType):
    item_uuid = String()
    item_price_tier_uuid = String()
    provider_item_uuid = String()
    segment_uuid = String()
    endpoint_id = String()
    quantity_greater_then = Float()
    quantity_less_then = Float()
    price = Float()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ItemPriceTierListType(ListObjectType):
    item_price_tier_list = List(ItemPriceTierType)
