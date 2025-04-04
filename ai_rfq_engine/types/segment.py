#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType


class SegmentType(ObjectType):
    endpoint_id = String()
    segment_uuid = String()
    provider_corporation_uuid = String()
    segment_name = String()
    segment_description = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class SegmentListType(ListObjectType):
    segment_list = List(SegmentType)
