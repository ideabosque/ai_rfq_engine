# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, Mutation, String

from silvaengine_utility import JSON

from ..models.quote import delete_quote, insert_update_quote
from ..types.quote import QuoteType


class InsertUpdateQuote(Mutation):
    quote = Field(QuoteType)

    class Arguments:
        request_uuid = String(required=True)
        quote_uuid = String(required=False)
        provider_corporate_uuid = String(required=False)
        contact_uuid = String(required=False)
        billing_address = JSON(required=False)
        shipping_address = JSON(required=False)
        shipping_method = String(required=False)
        shipping_amount = Float(required=False)
        total_amount = Float(required=False)
        total_discount_percentage = Float(required=False)
        final_total_amount = Float(required=False)
        notes = String(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateQuote":
        try:
            quote = insert_update_quote(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateQuote(quote=quote)


class DeleteQuote(Mutation):
    ok = Boolean()

    class Arguments:
        request_uuid = String(required=True)
        quote_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteQuote":
        try:
            ok = delete_quote(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteQuote(ok=ok)
