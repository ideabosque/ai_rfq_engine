#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class QuoteType(ObjectType):
    request_uuid = String()
    quote_uuid = String()
    provider_corp_external_Id = String()
    contact_uuid = String()
    endpoint_id = String()
    billing_address = JSON()
    shipping_address = JSON()
    shipping_method = String()
    shipping_amount = Float()
    total_amount = Float()
    total_discount_percentage = Float()
    final_total_amount = Float()
    notes = String()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)
