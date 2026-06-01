#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSONCamelCase
from silvaengine_utility import SafeFloat as Float


class BundleComponentType(ObjectType):
    partition_key = String()
    bundle_component_uuid = String()
    bundle_uuid = String()
    item_uuid = String()
    provider_item_uuid = String()
    component_role = String()
    required = Boolean()
    default_qty = Float()
    sort_order = Float()
    extra = JSONCamelCase()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class BundleComponentListType(ListObjectType):
    bundle_component_list = List(BundleComponentType)
