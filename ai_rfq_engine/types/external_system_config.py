#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Float, Int, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSONCamelCase


class ExternalSystemConfigType(ObjectType):
    """
    SECURITY INVARIANT: do NOT add ``auth_secret_value`` to this type. The plaintext
    credential is write-only and must never reach a GraphQL response. The mutation
    accepts it; the model stores it; handlers read it through
    ``models.external_system_config.resolve_credential_for`` only.
    """

    partition_key = String()
    config_uuid = String()
    system_code = String()
    system_kind = String()
    namespace = String()
    provider_corp_external_id = String()
    system_provider_key = String()
    endpoint_url = String()
    adapter_id = String()
    auth_strategy = String()
    # Pointer to an external secrets manager (when used). The actual credential is
    # never exposed here. See models/external_system_config.py for resolution order.
    auth_secret_ref = String()
    timeout_seconds = Int()
    cache_ttl_seconds = Int()
    extra_config = JSONCamelCase()
    status = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()


class ExternalSystemConfigListType(ListObjectType):
    external_system_config_list = List(ExternalSystemConfigType)