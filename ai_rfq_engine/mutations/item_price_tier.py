# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String
from silvaengine_utility import SafeFloat as Float

from ..models.item_price_tier import (
    delete_item_price_tier,
    insert_update_item_price_tier,
)
from ..types.item_price_tier import ItemPriceTierType


class InsertUpdateItemPriceTier(Mutation):
    item_price_tier = Field(ItemPriceTierType)

    class Arguments:
        item_uuid = String(required=True)
        item_price_tier_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        segment_uuid = String(required=False)
        quantity_greater_then = Float(required=False)
        margin_per_uom = Float(required=False)
        price_per_uom = Float(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateItemPriceTier":
        try:
            item_price_tier = insert_update_item_price_tier(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateItemPriceTier(item_price_tier=item_price_tier)


class DeleteItemPriceTier(Mutation):
    ok = Boolean()

    class Arguments:
        item_uuid = String(required=True)
        item_price_tier_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteItemPriceTier":
        try:
            ok = delete_item_price_tier(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteItemPriceTier(ok=ok)
