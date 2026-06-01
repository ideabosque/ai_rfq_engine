# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String
from silvaengine_utility import JSONCamelCase

from ..models.bundle import delete_bundle, insert_update_bundle
from ..types.bundle import BundleType


class InsertUpdateBundle(Mutation):
    bundle = Field(BundleType)

    class Arguments:
        bundle_uuid = String(required=False)
        bundle_code = String(required=False)
        bundle_name = String(required=False)
        bundle_type = String(required=False)
        description = String(required=False)
        extra = JSONCamelCase(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateBundle":
        try:
            bundle = insert_update_bundle(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e
        return InsertUpdateBundle(bundle=bundle)


class DeleteBundle(Mutation):
    ok = Boolean()

    class Arguments:
        bundle_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteBundle":
        try:
            ok = delete_bundle(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e
        return DeleteBundle(ok=ok)
