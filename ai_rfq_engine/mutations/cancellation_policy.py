# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from silvaengine_utility import JSONCamelCase

from ..models.cancellation_policy import (
    delete_cancellation_policy,
    insert_update_cancellation_policy,
)
from ..types.cancellation_policy import CancellationPolicyType


class InsertUpdateCancellationPolicy(Mutation):
    cancellation_policy = Field(CancellationPolicyType)

    class Arguments:
        policy_uuid = String(required=False)
        provider_item_uuid = String(required=False)
        label = String(required=False)
        description = String(required=False)
        tiers = JSONCamelCase(required=False)
        notes_template_uuid = String(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateCancellationPolicy":
        try:
            cancellation_policy = insert_update_cancellation_policy(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateCancellationPolicy(cancellation_policy=cancellation_policy)


class DeleteCancellationPolicy(Mutation):
    ok = Boolean()

    class Arguments:
        policy_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteCancellationPolicy":
        try:
            ok = delete_cancellation_policy(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteCancellationPolicy(ok=ok)