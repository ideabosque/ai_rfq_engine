#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType


class DiscountRuleType(ObjectType):
    item_uuid = String()
    discount_rule_uuid = String()
    provider_item_uuid = String()
    segment_uuid = String()
    endpoint_id = String()
    subtotal_greater_than = Float()
    subtotal_less_than = Float()
    max_discount_percentage = Float()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class DiscountRuleListType(ListObjectType):
    discount_rule_list = List(DiscountRuleType)
