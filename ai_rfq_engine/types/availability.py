#!/usr/bin/python
# -*- coding: utf-8 -*-
"""GraphQL output type for availability and temporary-hold checks."""
from __future__ import annotations

__author__ = "bibow"

from graphene import Boolean, DateTime, Int, ObjectType, String
from silvaengine_utility import JSONCamelCase


class AvailabilityResultType(ObjectType):
    operation = String()
    provider_item_uuid = String()
    batch_no = String()
    service_start_at = DateTime()
    service_end_at = DateTime()
    available = Boolean()
    hold_token = String()
    expires_at = DateTime()
    payload = JSONCamelCase()
    fetched_at = DateTime()
    ttl_seconds = Int()
    error_code = String()
    error_message = String()
