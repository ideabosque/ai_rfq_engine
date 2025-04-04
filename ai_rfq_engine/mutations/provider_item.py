# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, Mutation, String

from silvaengine_utility import JSON

from ..models.provider_item import delete_provider_item, insert_update_provider_item
from ..types.provider_item import ProviderItemType


class InsertUpdateProviderItem(Mutation):
    provider_item = Field(ProviderItemType)

    class Arguments:
        provider_item_uuid = String(required=False)
        item_uuid = String(required=False)
        provider_corporation_uuid = String(required=False)
        external_id = String(required=False)
        base_price_per_uom = Float(required=False)
        item_spec = JSON(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateProviderItem":
        try:
            provider_item = insert_update_provider_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateProviderItem(provider_item=provider_item)


class DeleteProviderItem(Mutation):
    ok = Boolean()

    class Arguments:
        provider_item_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteProviderItem":
        try:
            ok = delete_provider_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteProviderItem(ok=ok)
