#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class SegmentContactType(ObjectType):
    segment = JSON()
    email = String()
    contact_uuid = String()
    consumer_corp_external_id = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class SegmentContactListType(ListObjectType):
    segment_contact_list = List(SegmentContactType)
