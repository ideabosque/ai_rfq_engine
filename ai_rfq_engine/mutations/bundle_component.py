# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String
from silvaengine_utility import JSONCamelCase
from silvaengine_utility import SafeFloat as Float

from ..models.bundle_component import (
    delete_bundle_component,
    insert_update_bundle_component,
)
from ..types.bundle_component import BundleComponentType


class InsertUpdateBundleComponent(Mutation):
    bundle_component = Field(BundleComponentType)

    class Arguments:
        bundle_component_uuid = String(required=False)
        bundle_uuid = String(required=False)
        item_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        component_role = String(required=False)
        required = Boolean(required=False)
        default_qty = Float(required=False)
        sort_order = Float(required=False)
        extra = JSONCamelCase(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateBundleComponent":
        try:
            bundle_component = insert_update_bundle_component(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e
        return InsertUpdateBundleComponent(bundle_component=bundle_component)


class DeleteBundleComponent(Mutation):
    ok = Boolean()

    class Arguments:
        bundle_component_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteBundleComponent":
        try:
            ok = delete_bundle_component(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e
        return DeleteBundleComponent(ok=ok)
