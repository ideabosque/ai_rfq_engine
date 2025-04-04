#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType


class SegmentContactType(ObjectType):
    segment_uuid = String()
    contact_uuid = String()
    consumer_corporation_uuid = String()
    endpoint_id = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class SegmentContactListType(ListObjectType):
    segment_contact_list = List(SegmentContactType)
