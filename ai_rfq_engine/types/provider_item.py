#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"


from graphene import DateTime, Float, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class ProviderItemType(ObjectType):
    endpoint_id = String()
    provider_item_uuid = String()
    item_uuid = String()
    provider_corp_external_Id = String()
    external_id = String()
    base_price_per_uom = Float()
    item_spec = JSON()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ProviderItemListType(ListObjectType):
    provider_item_list = List(ProviderItemType)
