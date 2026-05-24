#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSONCamelCase


class CancellationPolicyType(ObjectType):
    partition_key = String()
    policy_uuid = String()
    provider_item_uuid = String()
    label = String()
    description = String()
    tiers = JSONCamelCase()
    notes_template_uuid = String()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class CancellationPolicyListType(ListObjectType):
    cancellation_policy_list = List(CancellationPolicyType)