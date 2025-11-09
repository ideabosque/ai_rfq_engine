# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Float, List, Mutation, String
from silvaengine_utility import JSON

from ..models.request import delete_request, insert_update_request
from ..types.request import RequestType


class InsertUpdateRequest(Mutation):
    request = Field(RequestType)

    class Arguments:
        request_uuid = String(required=False)
        email = String(required=False)
        request_title = String(required=False)
        request_description = String(required=False)
        billing_address = JSON(required=False)
        shipping_address = JSON(required=False)
        items = List(JSON, required=False)
        notes = String(required=False)
        status = String(required=False)
        expired_at = DateTime(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateRequest":
        try:
            request = insert_update_request(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateRequest(request=request)


class DeleteRequest(Mutation):
    ok = Boolean()

    class Arguments:
        request_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteRequest":
        try:
            ok = delete_request(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteRequest(ok=ok)
