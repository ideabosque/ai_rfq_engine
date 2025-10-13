#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, Int, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class InstallmentType(ObjectType):
    quote = JSON()
    installment_uuid = String()
    endpoint_id = String()
    priority = Int()
    salesorder_no = String()
    scheduled_date = DateTime()
    installment_ratio = Float()
    installment_amount = Float()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class InstallmentListType(ListObjectType):
    installment_list = List(InstallmentType)
