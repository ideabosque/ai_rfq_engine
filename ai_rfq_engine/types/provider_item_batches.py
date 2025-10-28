#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class ProviderItemBatchType(ObjectType):
    provider_item = JSON()
    batch_no = String()
    item = JSON()
    expired_at = DateTime()
    produced_at = DateTime()
    cost_per_uom = Float()
    freight_cost_per_uom = Float()
    additional_cost_per_uom = Float()
    total_cost_per_uom = Float()
    guardrail_margin_per_uom = Float()
    guardrail_price_per_uom = Float()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ProviderItemBatchListType(ListObjectType):
    provider_item_batch_list = List(ProviderItemBatchType)
