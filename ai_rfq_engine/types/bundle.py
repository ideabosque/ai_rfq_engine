#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSONCamelCase


class BundleType(ObjectType):
    partition_key = String()
    bundle_uuid = String()
    bundle_code = String()
    bundle_name = String()
    bundle_type = String()
    description = String()
    extra = JSONCamelCase()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()
    components = List(lambda: BundleComponentType)

    def resolve_components(parent, info):
        from ..models.bundle_component import resolve_bundle_component_list

        bundle_uuid = getattr(parent, "bundle_uuid", None)
        if not bundle_uuid:
            return []
        result = resolve_bundle_component_list(info, bundle_uuid=bundle_uuid)
        return result.bundle_component_list if result else []


class BundleListType(ListObjectType):
    bundle_list = List(BundleType)


from .bundle_component import BundleComponentType
