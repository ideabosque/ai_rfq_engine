#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class QuoteItemType(ObjectType):
    quote = JSON()
    quote_item_uuid = String()
    provider_item_uuid = String()
    item_uuid = String()
    endpoint_id = String()
    request_data = JSON()
    price_per_uom = Float()
    qty = Float()
    subtotal = Float()
    discount_percentage = Float()
    final_subtotal = Float()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class QuoteItemListType(ListObjectType):
    quote_item_list = List(QuoteItemType)
