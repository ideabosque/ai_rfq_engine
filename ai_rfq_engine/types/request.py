#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.batch_loaders import get_loaders

# Use the shared normalization helper instead of a local copy.
from ..utils.normalization import normalize_to_json


class RequestType(ObjectType):
    endpoint_id = String()
    request_uuid = String()
    email = String()
    request_title = String()
    request_description = String()
    billing_address = JSON()
    shipping_address = JSON()
    items = List(JSON)
    notes = String()
    status = String()
    expired_at = DateTime()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    quotes = List(JSON)
    files = List(JSON)
    # ------- Nested resolvers -------

    def resolve_quotes(parent, info):
        """Resolve nested Quotes for this request."""
        # Check if already embedded
        existing = getattr(parent, "quotes", None)
        if isinstance(existing, list) and existing:
            return [normalize_to_json(q) for q in existing]

        # Fetch quotes for this request
        request_uuid = getattr(parent, "request_uuid", None)
        if not request_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.quotes_by_request_loader.load(request_uuid).then(
            lambda quotes: [normalize_to_json(quote) for quote in (quotes or [])]
        )

    def resolve_files(parent, info):
        """Resolve nested Files for this request."""
        # Check if already embedded
        existing = getattr(parent, "files", None)
        if isinstance(existing, list) and existing:
            return [normalize_to_json(f) for f in existing]

        # Fetch files for this request
        request_uuid = getattr(parent, "request_uuid", None)
        if not request_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.files_by_request_loader.load(request_uuid).then(
            lambda files: [normalize_to_json(file) for file in (files or [])]
        )


class RequestListType(ListObjectType):
    request_list = List(RequestType)
