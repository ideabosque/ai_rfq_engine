#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType


class FxRateType(ObjectType):
    partition_key = String()
    fx_rate_uuid = String()
    source_currency = String()
    target_currency = String()
    rate = Float()
    currency_pair_date = String()
    rate_date = DateTime()
    provider = String()
    notes = String()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class FxRateListType(ListObjectType):
    fx_rate_list = List(FxRateType)