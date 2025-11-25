#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType

from ..models.utils import _get_request
from .request import RequestType


class FileType(ObjectType):
    request_uuid = String()  # keep raw id
    file_name = String()
    email = String()
    file_content = String()
    file_size = String()
    file_type = String()

    # Nested resolver: strongly-typed nested relationship
    request = Field(lambda: RequestType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_request(parent, info):
        """
        Resolve nested Request for this file.
        """
        # Case 2: already embedded
        existing = getattr(parent, "request", None)
        if isinstance(existing, dict):
            return RequestType(**existing)
        if isinstance(existing, RequestType):
            return existing

        # Case 1: need to fetch
        endpoint_id = info.context.get("endpoint_id")
        request_uuid = getattr(parent, "request_uuid", None)
        if not endpoint_id or not request_uuid:
            return None

        request_dict = _get_request(endpoint_id, request_uuid)
        if not request_dict:
            return None
        return RequestType(**request_dict)


class FileListType(ListObjectType):
    file_list = List(FileType)
