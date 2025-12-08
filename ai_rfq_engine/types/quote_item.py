#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, List, ObjectType, String, Field
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON
from ..models.batch_loaders import get_loaders
from ..utils.normalization import normalize_to_json
from .request import RequestType

class QuoteItemType(ObjectType):
    quote_uuid = String()
    quote_item_uuid = String()
    provider_item_uuid = String()
    item_uuid = String()
    # segment_uuid = String()
    endpoint_id = String()
    batch_no = String()
    qty = String()
    price_per_uom = String()
    subtotal = String()
    subtotal_discount = String()
    final_subtotal = String()
    guardrail_price_per_uom = String()
    slow_move_item = Boolean()

    # Keep as JSON (MapAttribute)
    request_uuid = String()
    request = Field(lambda: RequestType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_request(parent, info):
        """Resolve nested Request for this quote using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "request", None)
        if isinstance(existing, dict):
            return RequestType(**existing)
        if isinstance(existing, RequestType):
            return existing

        # Case 1: need to fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        request_uuid = getattr(parent, "request_uuid", None)
        if not endpoint_id or not request_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.request_loader.load((endpoint_id, request_uuid)).then(
            lambda request_dict: RequestType(**request_dict) if request_dict else None
        )
    
class QuoteItemListType(ListObjectType):
    quote_item_list = List(QuoteItemType)
