#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GraphQL output type for the ``inquire_catalog`` query (G7b).

Errors are returned in-band as ``error_code`` / ``error_message`` rather than
raised as GraphQL errors. AI-agent callers need to branch on ``not_configured``
vs ``auth_unavailable`` vs ``system_timeout`` differently, and an in-band
result keeps the error-code switch on the client side simple.
"""
from __future__ import annotations

__author__ = "bibow"

from graphene import DateTime, Int, ObjectType, String
from silvaengine_utility import JSONCamelCase


class CatalogInquiryResultType(ObjectType):
    """
    Result envelope for a single catalog inquiry.

    On success: ``payload`` is populated; ``error_code`` is null.
    On failure: ``error_code`` is one of the codes documented on
    ``handlers.catalog.CatalogHandlerError`` subclasses (``not_configured``,
    ``auth_unavailable``, ``system_timeout``, ``system_error``, ``unknown_node``);
    ``error_message`` carries the human-readable detail; ``payload`` is null.
    """

    # Identity echo (so callers can correlate batched inquiries)
    system = String()
    namespace = String()
    node_id = String()

    # Success fields
    payload = JSONCamelCase()
    fetched_at = DateTime()
    ttl_seconds = Int()

    # Error fields (mutually exclusive with payload/fetched_at)
    error_code = String()
    error_message = String()
