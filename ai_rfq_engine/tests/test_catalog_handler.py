#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for the direct knowledge graph catalog resolver."""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def info():
    return SimpleNamespace(
        context={"partition_key": "tenant-test", "aws_lambda_invoker": MagicMock()}
    )


@pytest.mark.unit
def test_dispatch_inquire_rejects_unpublished_node_lookup(info):
    from ai_rfq_engine.handlers.catalog import OperationUnsupportedError, dispatch_inquire

    with pytest.raises(OperationUnsupportedError, match="node-by-id"):
        dispatch_inquire(info, namespace="hotel", node_id="room-1")


@pytest.mark.unit
def test_dispatch_inquire_invokes_kge_graphql_search(info):
    from ai_rfq_engine.handlers.catalog import dispatch_inquire

    info.context["aws_lambda_invoker"].return_value = {
        "statusCode": 200,
        "body": {"data": {"search": {"results": [{"name": "Onsen"}], "total": 1}}},
    }
    result = dispatch_inquire(info, query={"query_text": "onsen hotel"})
    call = info.context["aws_lambda_invoker"].call_args.kwargs
    payload = call["payload"]
    from silvaengine_constants import InvocationType

    assert call["invocation_type"] is InvocationType.REQUEST_RESPONSE
    assert payload["module_name"] == "knowledge_graph_engine"
    assert payload["class_name"] == "KnowledgeGraphEngine"
    assert payload["function_name"] == "knowledge_graph_graphql"
    assert payload["parameters"]["variables"]["queryText"] == "onsen hotel"
    assert result["payload"]["total"] == 1


@pytest.mark.unit
def test_dispatch_inquire_requires_partition_key():
    from ai_rfq_engine.handlers.catalog import CatalogSystemError, dispatch_inquire

    with pytest.raises(CatalogSystemError, match="partition_key"):
        dispatch_inquire(SimpleNamespace(context={}), query={"query_text": "room"})


@pytest.mark.unit
def test_dispatch_inquire_requires_invoker():
    from ai_rfq_engine.handlers.catalog import CatalogSystemError, dispatch_inquire

    with pytest.raises(CatalogSystemError, match="aws_lambda_invoker"):
        dispatch_inquire(
            SimpleNamespace(context={"partition_key": "tenant"}),
            query={"query_text": "room"},
        )


@pytest.mark.unit
def test_graphql_wrapper_returns_structured_catalog_error(info, monkeypatch):
    from ai_rfq_engine.handlers.catalog import CatalogSystemError
    from ai_rfq_engine.queries import catalog_inquiry

    monkeypatch.setattr(
        catalog_inquiry,
        "dispatch_inquire",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CatalogSystemError("KGE unavailable")
        ),
    )
    result = catalog_inquiry.resolve_inquire_catalog(
        info, node_id="room-1"
    )
    assert result.error_code == "system_error"
    assert result.payload is None
