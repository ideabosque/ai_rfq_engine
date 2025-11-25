#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_utility import JSON

from silvaengine_dynamodb_base import ListObjectType

from ..models.utils import _get_request
from .request import RequestType


class QuoteType(ObjectType):
    request_uuid = String()  # keep raw id
    quote_uuid = String()
    provider_corp_external_id = String()
    sales_rep_email = String()
    quote_description = String()
    payment_terms = String()
    shipping_method = String()
    shipping_amount = String()
    total_quote_amount = String()
    total_quote_discount = String()
    final_total_quote_amount = String()
    notes = String()
    status = String()
    expired_at = DateTime()

    # Nested resolvers: strongly-typed nested relationship
    request = Field(lambda: RequestType)

    # Keep as JSON for now (will migrate in Phase 2.5)
    quote_items = List(JSON)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_request(parent, info):
        """Resolve nested Request for this quote."""
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


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)
