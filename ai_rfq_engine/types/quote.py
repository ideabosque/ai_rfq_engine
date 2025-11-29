#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON
from silvaengine_utility import Utility

from ..models.batch_loaders import get_loaders
from .request import RequestType


def _normalize_to_json(item):
    """Convert various object shapes to a JSON-serializable dict/primitive."""
    if isinstance(item, dict):
        return Utility.json_normalize(item)
    if hasattr(item, "attribute_values"):
        return Utility.json_normalize(item.attribute_values)
    if hasattr(item, "__dict__"):
        return Utility.json_normalize(
            {k: v for k, v in vars(item).items() if not k.startswith("_")}
        )
    return item


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

    # Nested resolvers: strongly-typed nested relationships
    quote_items = List(JSON)
    installments = List(JSON)

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

    def resolve_quote_items(parent, info):
        """Resolve nested QuoteItems for this quote."""
        # Check if already embedded
        existing = getattr(parent, "quote_items", None)
        if isinstance(existing, list):
            return [_normalize_to_json(qi) for qi in existing]

        # Fetch quote items for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.quote_item_list_loader.load(quote_uuid).then(
            lambda q_items: [_normalize_to_json(qi) for qi in (q_items or [])]
        )

    def resolve_installments(parent, info):
        """Resolve nested Installments for this quote."""
        # Check if already embedded
        existing = getattr(parent, "installments", None)
        if isinstance(existing, list):
            return [_normalize_to_json(inst) for inst in existing]

        # Fetch installments for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.installment_list_loader.load(quote_uuid).then(
            lambda insts: [_normalize_to_json(inst) for inst in (insts or [])]
        )


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)
