# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Int, Mutation, String

from silvaengine_utility import JSONCamelCase

from ..models.external_system_config import (
    delete_external_system_config,
    insert_update_external_system_config,
)
from ..types.external_system_config import ExternalSystemConfigType


class InsertUpdateExternalSystemConfig(Mutation):
    external_system_config = Field(ExternalSystemConfigType)

    class Arguments:
        config_uuid = String(required=False)
        system_code = String(required=False)
        system_kind = String(required=False)
        namespace = String(required=False)
        provider_corp_external_id = String(required=False)
        endpoint_url = String(required=False)
        adapter_id = String(required=False)
        auth_strategy = String(required=False)
        # Plaintext credential. WRITE-ONLY: accepted here but never returned through
        # any GraphQL output type. See ExternalSystemConfigType.
        auth_secret_value = String(required=False)
        auth_secret_ref = String(required=False)
        timeout_seconds = Int(required=False)
        cache_ttl_seconds = Int(required=False)
        extra_config = JSONCamelCase(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateExternalSystemConfig":
        try:
            external_system_config = insert_update_external_system_config(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateExternalSystemConfig(
            external_system_config=external_system_config
        )


class DeleteExternalSystemConfig(Mutation):
    ok = Boolean()

    class Arguments:
        config_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteExternalSystemConfig":
        try:
            ok = delete_external_system_config(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteExternalSystemConfig(ok=ok)