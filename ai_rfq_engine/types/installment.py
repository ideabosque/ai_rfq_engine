#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, Int, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders


class InstallmentType(ObjectType):
    quote_uuid = String()  # keep raw id
    installment_uuid = String()
    request_uuid = String()  # keep raw id for convenience
    priority = Int()
    partition_key = String()
    installment_amount = String()
    installment_ratio = String()
    salesorder_no = String()
    scheduled_date = DateTime()
    payment_method = String()
    status = String()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # Nested resolver: strongly-typed nested relationship
    quote = Field(lambda: QuoteType)

    # ------- Nested resolvers -------

    def resolve_quote(parent, info):
        """Resolve nested Quote for this installment using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "quote", None)
        if isinstance(existing, dict):
            return QuoteType(**existing)
        if isinstance(existing, QuoteType):
            return existing

        # Case 1: need to fetch using DataLoader
        request_uuid = getattr(parent, "request_uuid", None)
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not request_uuid or not quote_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.quote_loader.load((request_uuid, quote_uuid)).then(
            lambda quote_dict: QuoteType(**quote_dict) if quote_dict else None
        )


class InstallmentListType(ListObjectType):
    installment_list = List(InstallmentType)


# Bottom imports - imported after class definitions to avoid circular imports
from .quote import QuoteType
