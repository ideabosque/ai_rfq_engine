#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class DiscountRuleType(ObjectType):
    provider_item = JSON()
    discount_rule_uuid = String()
    segment = JSON()
    subtotal_greater_than = Float()
    subtotal_less_than = Float()
    max_discount_percentage = Float()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class DiscountRuleListType(ListObjectType):
    discount_rule_list = List(DiscountRuleType)
