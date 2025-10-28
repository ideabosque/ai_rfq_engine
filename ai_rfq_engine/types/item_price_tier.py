#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class ItemPriceTierType(ObjectType):
    provider_item = JSON()
    item_price_tier_uuid = String()
    segment = JSON()
    quantity_greater_then = Float()
    quantity_less_then = Float()
    margin_per_uom = Float()
    price_per_uom = Float()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ItemPriceTierListType(ListObjectType):
    item_price_tier_list = List(ItemPriceTierType)
