#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSONCamelCase


class ItemCatalogRefType(ObjectType):
    partition_key = String()
    catalog_ref_uuid = String()
    namespace = String()
    node_id = String()
    namespace_node_key = String()
    extra = JSONCamelCase()
    item_uuid = String()
    item_lookup_key = String()
    provider_item_uuid = String()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ItemCatalogRefListType(ListObjectType):
    item_catalog_ref_list = List(ItemCatalogRefType)
