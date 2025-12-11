# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from ..models.item import delete_item, insert_update_item
from ..types.item import ItemType


class InsertUpdateItem(Mutation):
    item = Field(ItemType)

    class Arguments:
        item_uuid = String(required=False)
        item_type = String(required=False)
        item_name = String(required=False)
        item_description = String(required=False)
        uom = String(required=False)
        item_external_id = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateItem":
        try:
            item = insert_update_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateItem(item=item)


class DeleteItem(Mutation):
    ok = Boolean()

    class Arguments:
        item_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteItem":
        try:
            ok = delete_item(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteItem(ok=ok)
