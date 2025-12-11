#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class FileType(ObjectType):
    request = JSON()
    file_name = String()
    email = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class FileListType(ListObjectType):
    file_list = List(FileType)
