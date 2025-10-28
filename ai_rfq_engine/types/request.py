#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class RequestType(ObjectType):
    endpoint_id = String()
    request_uuid = String()
    email = String()
    request_title = String()
    request_description = String()
    billing_address = JSON()
    shipping_address = JSON()
    items = List(JSON)
    total_amount = Float()
    total_discount = Float()
    final_total_amount = Float()
    notes = String()
    status = String()
    expired_at = DateTime()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class RequestListType(ListObjectType):
    request_list = List(RequestType)
