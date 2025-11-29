#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType


class ItemType(ObjectType):
    endpoint_id = String()
    item_uuid = String()
    item_type = String()
    item_name = String()
    item_description = String()
    uom = String()
    item_external_id = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ItemListType(ListObjectType):
    item_list = List(ItemType)
