#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, Int, List, ObjectType, String

from silvaengine_dynamodb_base import ListObjectType

from ..models.utils import _get_quote
from .quote import QuoteType


class InstallmentType(ObjectType):
    quote_uuid = String()  # keep raw id
    installment_uuid = String()
    request_uuid = String()  # keep raw id for convenience
    priority = Int()
    installment_amount = String()
    installment_ratio = String()
    scheduled_date = DateTime()
    payment_method = String()
    payment_status = String()

    # Nested resolver: strongly-typed nested relationship
    quote = Field(lambda: QuoteType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_quote(parent, info):
        """Resolve nested Quote for this installment."""
        # Case 2: already embedded
        existing = getattr(parent, "quote", None)
        if isinstance(existing, dict):
            return QuoteType(**existing)
        if isinstance(existing, QuoteType):
            return existing

        # Case 1: need to fetch
        request_uuid = getattr(parent, "request_uuid", None)
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not request_uuid or not quote_uuid:
            return None

        quote_dict = _get_quote(request_uuid, quote_uuid)
        if not quote_dict:
            return None
        return QuoteType(**quote_dict)


class InstallmentListType(ListObjectType):
    installment_list = List(InstallmentType)
