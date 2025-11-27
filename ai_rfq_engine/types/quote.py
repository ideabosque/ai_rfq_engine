#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.batch_loaders import get_loaders
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

    # Nested resolvers: strongly-typed nested relationships
    quote_items = List(lambda: "ai_rfq_engine.types.quote_item.QuoteItemType")
    installments = List(lambda: "ai_rfq_engine.types.installment.InstallmentType")

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
        if isinstance(existing, list) and existing:
            from .quote_item import QuoteItemType

            return [
                QuoteItemType(**qi) if isinstance(qi, dict) else qi for qi in existing
            ]

        # Fetch quote items for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        from .quote_item import QuoteItemType

        loaders = get_loaders(info.context)
        return loaders.quote_item_list_loader.load(quote_uuid).then(
            lambda q_items: [
                QuoteItemType(**qi) if isinstance(qi, dict) else qi for qi in q_items
            ]
        )

    def resolve_installments(parent, info):
        """Resolve nested Installments for this quote."""
        # Check if already embedded
        existing = getattr(parent, "installments", None)
        if isinstance(existing, list) and existing:
            from .installment import InstallmentType

            return [
                InstallmentType(**inst) if isinstance(inst, dict) else inst
                for inst in existing
            ]

        # Fetch installments for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        from .installment import InstallmentType

        loaders = get_loaders(info.context)
        return loaders.installment_list_loader.load(quote_uuid).then(
            lambda insts: [
                InstallmentType(**inst) if isinstance(inst, dict) else inst
                for inst in insts
            ]
        )


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)
