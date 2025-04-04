# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, Mutation, String

from silvaengine_utility import JSON

from ..models.quote_item import delete_quote_item, insert_update_quote_item
from ..types.quote_item import QuoteItemType


class InsertUpdateQuoteItem(Mutation):
    quote_item = Field(QuoteItemType)

    class Arguments:
        quote_uuid = String(required=True)
        quote_item_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        item_uuid = String(required=False)
        request_uuid = String(required=False)
        request_data = JSON(required=False)
        price_per_uom = Float(required=False)
        qty = Float(required=False)
        subtotal = Float(required=False)
        discount_percentage = Float(required=False)
        final_subtotal = Float(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateQuoteItem":
        try:
            quote_item = insert_update_quote_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateQuoteItem(quote_item=quote_item)


class DeleteQuoteItem(Mutation):
    ok = Boolean()

    class Arguments:
        quote_uuid = String(required=True)
        quote_item_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteQuoteItem":
        try:
            ok = delete_quote_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteQuoteItem(ok=ok)
