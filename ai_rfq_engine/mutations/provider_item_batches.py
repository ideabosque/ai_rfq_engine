# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Float, Mutation, String

from ..models.provider_item_batches import (
    delete_provider_item_batch,
    insert_update_provider_item_batch,
)
from ..types.provider_item_batches import ProviderItemBatchType


class InsertUpdateProviderItemBatch(Mutation):
    provider_item_batch = Field(ProviderItemBatchType)

    class Arguments:
        provider_item_uuid = String(required=False)
        batch_no = String(required=False)
        item_uuid = String(required=False)
        expired_at = DateTime(required=False)
        produced_at = DateTime(required=False)
        cost_per_uom = Float(required=False)
        freight_cost_per_uom = Float(required=False)
        additional_cost_per_uom = Float(required=False)
        guardrail_margin_per_uom = Float(required=False)
        in_stock = Boolean(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateProviderItemBatch":
        try:
            provider_item_batch = insert_update_provider_item_batch(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateProviderItemBatch(provider_item_batch=provider_item_batch)


class DeleteProviderItemBatch(Mutation):
    ok = Boolean()

    class Arguments:
        provider_item_uuid = String(required=True)
        batch_no = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteProviderItemBatch":
        try:
            ok = delete_provider_item_batch(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteProviderItemBatch(ok=ok)
