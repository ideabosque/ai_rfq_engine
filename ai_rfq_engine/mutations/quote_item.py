# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Mutation, String

from silvaengine_utility import JSONCamelCase
from silvaengine_utility import SafeFloat as Float

from ..models.quote_item import delete_quote_item, insert_update_quote_item
from ..types.quote_item import QuoteItemType


class InsertUpdateQuoteItem(Mutation):
    quote_item = Field(QuoteItemType)

    class Arguments:
        quote_uuid = String(required=True)
        quote_item_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        item_uuid = String(required=False)
        segment_uuid = String(required=False)
        batch_no = String(required=False)
        request_uuid = String(required=False)
        request_data = JSONCamelCase(required=False)
        pax_breakdown = JSONCamelCase(required=False)
        bundle_uuid = String(required=False)
        bundle_label = String(required=False)
        bundle_component_uuid = String(required=False)
        qty = Float(required=False)
        subtotal_discount = Float(required=False)
        currency = String(required=False)
        subtotal_native = Float(required=False)
        notes = String(required=False)
        service_start_at = DateTime(required=False)
        service_end_at = DateTime(required=False)
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
