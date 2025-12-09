#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Int, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class DiscountPromptType(ObjectType):
    endpoint_id = String()
    discount_prompt_uuid = String()
    scope = String()  # global, segment, item, or provider_item
    tags = List(String)  # Flexible tagging for matching
    discount_prompt = String()  # AI prompt text
    conditions = List(String)  # List of conditional criteria (stored as JSON)
    discount_rules = List(JSON)  # Embedded discount rule tiers
    priority = Int()  # Priority for conflict resolution
    status = String()  # in_review, active, inactive

    # Audit fields
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class DiscountPromptListType(ListObjectType):
    discount_prompt_list = List(DiscountPromptType)
