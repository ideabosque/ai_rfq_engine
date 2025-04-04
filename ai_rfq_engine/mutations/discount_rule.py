# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, Mutation, String

from ..models.discount_rule import delete_discount_rule, insert_update_discount_rule
from ..types.discount_rule import DiscountRuleType


class InsertUpdateDiscountRule(Mutation):
    discount_rule = Field(DiscountRuleType)

    class Arguments:
        item_uuid = String(required=True)
        discount_rule_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        segment_uuid = String(required=False)
        subtotal_greater_than = Float(required=False)
        subtotal_less_than = Float(required=False)
        max_discount_percentage = Float(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDiscountRule":
        try:
            discount_rule = insert_update_discount_rule(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDiscountRule(discount_rule=discount_rule)


class DeleteDiscountRule(Mutation):
    ok = Boolean()

    class Arguments:
        item_uuid = String(required=True)
        discount_rule_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteDiscountRule":
        try:
            ok = delete_discount_rule(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDiscountRule(ok=ok)
