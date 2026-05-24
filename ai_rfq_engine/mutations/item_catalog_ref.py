# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from silvaengine_utility import JSONCamelCase

from ..models.item_catalog_ref import (
    delete_item_catalog_ref,
    insert_update_item_catalog_ref,
)
from ..types.item_catalog_ref import ItemCatalogRefType


class InsertUpdateItemCatalogRef(Mutation):
    item_catalog_ref = Field(ItemCatalogRefType)

    class Arguments:
        catalog_ref_uuid = String(required=False)
        system_code = String(required=False)
        namespace = String(required=False)
        node_id = String(required=False)
        item_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        extra = JSONCamelCase(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateItemCatalogRef":
        try:
            item_catalog_ref = insert_update_item_catalog_ref(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateItemCatalogRef(item_catalog_ref=item_catalog_ref)


class DeleteItemCatalogRef(Mutation):
    ok = Boolean()

    class Arguments:
        catalog_ref_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteItemCatalogRef":
        try:
            ok = delete_item_catalog_ref(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteItemCatalogRef(ok=ok)