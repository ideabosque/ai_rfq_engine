#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class QuoteItemType(ObjectType):
    quote_uuid = String()
    quote_item_uuid = String()
    provider_item_uuid = String()
    item_uuid = String()
    segment_uuid = String()
    batch_no = String()
    qty = String()
    price_per_uom = String()
    subtotal = String()
    subtotal_discount = String()
    final_subtotal = String()
    guardrail_price_per_uom = String()
    slow_move_item = Boolean()

    # Keep as JSON (MapAttribute)
    request_data = JSON()

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class QuoteItemListType(ListObjectType):
    quote_item_list = List(QuoteItemType)
