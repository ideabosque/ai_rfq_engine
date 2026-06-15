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
        context={
            "partition_key": "tenant-test",
            "endpoint_id": "gpt",
            "part_id": "test",
        }
    )


_FUNCTS_ON_LOCAL_SETTING = {
    "functs_on_local": {
        "knowledge_graph_graphql": {
            "module_name": "knowledge_graph_engine",
            "class_name": "KnowledgeGraphEngine",
        },
    },
}


@pytest.mark.unit
def test_dispatch_inquire_rejects_unpublished_node_lookup(info):
    from ai_rfq_engine.handlers.catalog import OperationUnsupportedError, dispatch_inquire

    with pytest.raises(OperationUnsupportedError, match="node-by-id"):
        dispatch_inquire(info, namespace="hotel", node_id="room-1")


@pytest.mark.unit
def test_dispatch_inquire_invokes_kge_graphql_search(info, monkeypatch):
    from ai_rfq_engine.handlers.catalog import dispatch_inquire
    from ai_rfq_engine.handlers.catalog import handler as catalog_handler

    monkeypatch.setattr(
        catalog_handler.Config, "get_setting", lambda: _FUNCTS_ON_LOCAL_SETTING
    )
    invoker_mock = MagicMock(
        return_value={"search": {"results": [{"name": "Onsen"}], "total": 1}}
    )
    monkeypatch.setattr(
        catalog_handler.Invoker, "invoke_funct_on_local", invoker_mock
    )

    result = dispatch_inquire(info, query={"query_text": "onsen hotel"})

    args, kwargs = invoker_mock.call_args
    assert args[1] is _FUNCTS_ON_LOCAL_SETTING
    assert args[2] == "knowledge_graph_graphql"
    assert kwargs["variables"]["queryText"] == "onsen hotel"
    assert kwargs["endpoint_id"] == "gpt"
    assert kwargs["part_id"] == "test"
    assert result["payload"]["total"] == 1


@pytest.mark.unit
def test_dispatch_inquire_requires_partition_key():
    from ai_rfq_engine.handlers.catalog import CatalogSystemError, dispatch_inquire

    with pytest.raises(CatalogSystemError, match="partition_key"):
        dispatch_inquire(SimpleNamespace(context={}), query={"query_text": "room"})


@pytest.mark.unit
def test_dispatch_inquire_requires_functs_on_local(info, monkeypatch):
    from ai_rfq_engine.handlers.catalog import CatalogSystemError, dispatch_inquire
    from ai_rfq_engine.handlers.catalog import handler as catalog_handler

    monkeypatch.setattr(
        catalog_handler.Config, "get_setting", lambda: {"functs_on_local": {}}
    )
    with pytest.raises(CatalogSystemError, match="functs_on_local"):
        dispatch_inquire(info, query={"query_text": "room"})


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
