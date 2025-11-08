#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class QuoteType(ObjectType):
    request = JSON()
    quote_uuid = String()
    provider_corp_external_id = String()
    sales_rep_email = String()
    shipping_method = String()
    shipping_amount = Float()
    total_quote_amount = Float()
    total_quote_discount = Float()
    final_total_quote_amount = Float()
    quote_items = List(JSON)
    negotiation_rounds = Float()
    notes = String()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)
