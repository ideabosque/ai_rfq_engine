#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, Int, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType


class InstallmentType(ObjectType):
    quote_uuid = String()
    installment_uuid = String()
    endpoint_id = String()
    request_uuid = String()
    priority = Int()
    salesorder_no = String()
    scheduled_date = DateTime()
    quote_item_uuids = List(String)
    installment_ratio = Float()
    installment_amount = Float()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class InstallmentListType(ListObjectType):
    installment_list = List(InstallmentType)
