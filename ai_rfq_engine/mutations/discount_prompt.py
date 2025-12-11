# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Int, List, Mutation, String
from silvaengine_utility import JSON

from ..models.discount_prompt import (
    delete_discount_prompt,
    insert_update_discount_prompt,
)
from ..types.discount_prompt import DiscountPromptType


class InsertUpdateDiscountPrompt(Mutation):
    discount_prompt = Field(DiscountPromptType)

    class Arguments:
        discount_prompt_uuid = String(required=False)
        scope = String(required=False)  # global, segment, item, or provider_item
        tags = List(String, required=False)  # List of tags for filtering
        discount_prompt = String(required=False)  # AI prompt text
        conditions = List(String, required=False)  # List of conditional criteria
        discount_rules = List(JSON, required=False)  # List of discount rule tiers
        priority = Int(required=False)  # Priority for conflict resolution
        status = String(required=False)  # in_review, active, inactive
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateDiscountPrompt":
        try:
            discount_prompt = insert_update_discount_prompt(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateDiscountPrompt(discount_prompt=discount_prompt)


class DeleteDiscountPrompt(Mutation):
    ok = Boolean()

    class Arguments:
        discount_prompt_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteDiscountPrompt":
        try:
            ok = delete_discount_prompt(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteDiscountPrompt(ok=ok)
