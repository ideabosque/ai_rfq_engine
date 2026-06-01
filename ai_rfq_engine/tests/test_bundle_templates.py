#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for reusable bundle/package template references."""
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
            "endpoint_id": "endpoint-test",
            "logger": MagicMock(),
        }
    )


@pytest.mark.unit
def test_request_rejects_unknown_bundle_reference(info, monkeypatch):
    from ai_rfq_engine.models import request as request_model

    monkeypatch.setattr(request_model, "_validate_request_items", lambda *args: None)
    monkeypatch.setattr(
        request_model,
        "validate_bundle_exists",
        lambda partition_key, bundle_uuid: False,
    )

    raw_insert = request_model.insert_update_request.__wrapped__.__wrapped__
    with pytest.raises(ValueError, match="bundle_uuid 'bundle-missing' does not exist"):
        raw_insert(
            info,
            entity=None,
            request_uuid="request-1",
            email="guest@example.com",
            request_title="Package inquiry",
            bundle_uuid="bundle-missing",
            updated_by="tester",
        )


@pytest.mark.unit
def test_request_persists_bundle_reference(info, monkeypatch):
    from ai_rfq_engine.models import request as request_model

    captured = {}

    class FakeRequestModel:
        updated_by = SimpleNamespace(set=lambda value: ("updated_by", value))
        updated_at = SimpleNamespace(set=lambda value: ("updated_at", value))

        def __init__(self, partition_key, request_uuid, **cols):
            captured["partition_key"] = partition_key
            captured["request_uuid"] = request_uuid
            captured["cols"] = cols

        def save(self):
            return None

    monkeypatch.setattr(request_model, "_validate_request_items", lambda *args: None)
    monkeypatch.setattr(
        request_model, "validate_bundle_exists", lambda partition_key, bundle_uuid: True
    )
    monkeypatch.setattr(request_model, "RequestModel", FakeRequestModel)

    raw_insert = request_model.insert_update_request.__wrapped__.__wrapped__
    raw_insert(
        info,
        entity=None,
        request_uuid="request-1",
        email="guest@example.com",
        request_title="Package inquiry",
        bundle_uuid="bundle-1",
        updated_by="tester",
    )

    assert captured["partition_key"] == "tenant-test"
    assert captured["cols"]["bundle_uuid"] == "bundle-1"


@pytest.mark.unit
def test_quote_item_requires_bundle_for_bundle_component(info, monkeypatch):
    from ai_rfq_engine.tests.test_availability_handler import (
        FakeSavedQuoteItem,
        _patch_quote_creation,
        _quote_kwargs,
    )

    raw_insert = _patch_quote_creation(monkeypatch)
    kwargs = _quote_kwargs()
    kwargs["bundle_component_uuid"] = "component-1"

    with pytest.raises(
        ValueError, match="bundle_uuid is required when bundle_component_uuid"
    ):
        raw_insert(info, **kwargs)
    assert FakeSavedQuoteItem.captured is None


@pytest.mark.unit
def test_quote_item_rejects_component_from_different_bundle(info, monkeypatch):
    from ai_rfq_engine.models import utils as utils_model
    from ai_rfq_engine.tests.test_availability_handler import (
        FakeSavedQuoteItem,
        _patch_quote_creation,
        _quote_kwargs,
    )

    monkeypatch.setattr(
        utils_model,
        "validate_bundle_component_exists",
        lambda partition_key, bundle_uuid, bundle_component_uuid: False,
    )

    raw_insert = _patch_quote_creation(monkeypatch)
    kwargs = _quote_kwargs()
    kwargs["bundle_uuid"] = "bundle-1"
    kwargs["bundle_component_uuid"] = "component-other"

    with pytest.raises(ValueError, match="does not belong"):
        raw_insert(info, **kwargs)
    assert FakeSavedQuoteItem.captured is None


@pytest.mark.unit
def test_quote_item_persists_bundle_component_reference(info, monkeypatch):
    from ai_rfq_engine.models import utils as utils_model
    from ai_rfq_engine.tests.test_availability_handler import (
        FakeSavedQuoteItem,
        _patch_quote_creation,
        _quote_kwargs,
    )

    monkeypatch.setattr(
        utils_model,
        "validate_bundle_component_exists",
        lambda partition_key, bundle_uuid, bundle_component_uuid: True,
    )

    raw_insert = _patch_quote_creation(monkeypatch)
    kwargs = _quote_kwargs()
    kwargs["bundle_uuid"] = "bundle-1"
    kwargs["bundle_component_uuid"] = "component-1"
    raw_insert(info, **kwargs)

    assert FakeSavedQuoteItem.captured["bundle_uuid"] == "bundle-1"
    assert FakeSavedQuoteItem.captured["bundle_component_uuid"] == "component-1"
