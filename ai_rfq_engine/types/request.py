#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class RequestType(ObjectType):
    endpoint_id = String()
    request_uuid = String()
    contact_uuid = String()
    request_title = String()
    request_description = String()
    items = List(JSON)
    status = String()
    expired_at = DateTime()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class RequestListType(ListObjectType):
    request_list = List(RequestType)
