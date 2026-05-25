#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Unit tests for the availability hold expiry scanner, handler telemetry,
and cancellation snapshot content hash.
"""
from __future__ import annotations

__author__ = "bibow"

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pendulum
import pytest


# --- Expiry scanner tests --------------------------------------------------- #


class TestExpiryScanner:
    @pytest.mark.unit
    def test_scan_expired_holds_dry_run(self):
        from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

        hold_a = SimpleNamespace(
            hold_token="tok-a",
            provider_item_uuid="pi-1",
            batch_no="B-001",
            status="held",
            expires_at=pendulum.now("UTC").subtract(minutes=5),
        )
        fake_query = lambda pk: iter([hold_a])

        logger = logging.getLogger("test_expiry_scanner")
        result = scan_expired_holds(
            logger, partition_key="tenant-test", dry_run=True, _query_fn=fake_query
        )

        assert result["scanned"] == 1
        assert result["expired"] == 1
        assert result["errors"] == 0

    @pytest.mark.unit
    def test_scan_expired_holds_invokes_dispatch(self):
        from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

        hold = SimpleNamespace(
            hold_token="tok-expired",
            provider_item_uuid="pi-1",
            batch_no="B-001",
            status="held",
            expires_at=pendulum.now("UTC").subtract(minutes=5),
        )
        fake_query = lambda pk: iter([hold])
        logger = logging.getLogger("test_expiry_scanner")
        info = SimpleNamespace(
            context={"partition_key": "tenant-test", "logger": logger}
        )

        mock_dispatch = MagicMock(return_value={"operation": "expire_hold", "available": False})
        with patch(
            "ai_rfq_engine.handlers.availability.handler.dispatch_expire_hold",
            mock_dispatch,
        ):
            result = scan_expired_holds(
                logger,
                partition_key="tenant-test",
                info=info,
                dry_run=False,
                _query_fn=fake_query,
            )

        assert result["expired"] == 1
        mock_dispatch.assert_called_once_with(
            info,
            provider_item_uuid="pi-1",
            batch_no="B-001",
            hold_token="tok-expired",
        )

    @pytest.mark.unit
    def test_scan_expired_holds_builds_dispatch_context_when_info_omitted(self):
        from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

        hold = SimpleNamespace(
            hold_token="tok-scheduled",
            provider_item_uuid="pi-1",
            batch_no="B-001",
            status="held",
            expires_at=pendulum.now("UTC").subtract(minutes=5),
        )
        logger = logging.getLogger("test_expiry_scanner")
        mock_dispatch = MagicMock(return_value={"operation": "expire_hold"})

        with patch(
            "ai_rfq_engine.handlers.availability.handler.dispatch_expire_hold",
            mock_dispatch,
        ):
            result = scan_expired_holds(
                logger,
                partition_key="tenant-test",
                _query_fn=lambda pk: iter([hold]),
            )

        assert result["expired"] == 1
        generated_info = mock_dispatch.call_args.args[0]
        assert generated_info.context["partition_key"] == "tenant-test"
        assert generated_info.context["logger"] is logger

    @pytest.mark.unit
    def test_scan_expired_holds_rejects_mismatched_dispatch_context(self):
        from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

        info = SimpleNamespace(context={"partition_key": "other-tenant"})

        with pytest.raises(ValueError, match="partition_key must match"):
            scan_expired_holds(
                logging.getLogger("test_expiry_scanner"),
                partition_key="tenant-test",
                info=info,
                _query_fn=lambda pk: iter([]),
            )

    @pytest.mark.unit
    def test_scan_expired_holds_batch_size_limit(self):
        from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

        holds = [
            SimpleNamespace(
                hold_token=f"tok-{i}",
                provider_item_uuid="pi-1",
                batch_no="B-001",
                status="held",
                expires_at=pendulum.now("UTC").subtract(minutes=i),
            )
            for i in range(10)
        ]
        fake_query = lambda pk: iter(holds)
        logger = logging.getLogger("test_expiry_scanner")
        result = scan_expired_holds(
            logger, partition_key="tenant-test", batch_size=3, dry_run=True, _query_fn=fake_query
        )

        assert result["scanned"] == 3
        assert result["expired"] == 3


# --- Handler telemetry tests ------------------------------------------------- #


class TestHandlerTelemetry:
    @pytest.mark.unit
    def test_emit_handler_event_logs_on_success(self):
        from ai_rfq_engine.handlers.telemetry import emit_handler_event

        logger = MagicMock()
        info = SimpleNamespace(context={"logger": logger, "partition_key": "tenant-a"})
        emit_handler_event(
            info, operation="check", handler="availability", duration_ms=12.5
        )
        logger.info.assert_called_once()
        event = logger.info.call_args[0][1]
        assert event["operation"] == "check"
        assert event["handler"] == "availability"
        assert event["duration_ms"] == 12.5
        assert event["tenant"] == "tenant-a"
        assert event["error_code"] is None

    @pytest.mark.unit
    def test_emit_handler_event_warns_on_error(self):
        from ai_rfq_engine.handlers.telemetry import emit_handler_event

        logger = MagicMock()
        info = SimpleNamespace(context={"logger": logger, "partition_key": "tenant-b"})
        emit_handler_event(
            info, operation="acquire_hold", handler="availability",
            error_code="insufficient_availability",
        )
        logger.warning.assert_called_once()
        event = logger.warning.call_args[0][1]
        assert event["error_code"] == "insufficient_availability"

    @pytest.mark.unit
    def test_measure_handler_duration_emits_on_success(self):
        from ai_rfq_engine.handlers.telemetry import measure_handler_duration

        logger = MagicMock()
        info = SimpleNamespace(context={"logger": logger, "partition_key": "tenant-c"})

        with measure_handler_duration(info, operation="inquire", handler="catalog"):
            pass

        logger.info.assert_called_once()
        event = logger.info.call_args[0][1]
        assert event["operation"] == "inquire"
        assert event["handler"] == "catalog"
        assert event["duration_ms"] >= 0
        assert event["error_code"] is None

    @pytest.mark.unit
    def test_measure_handler_duration_emits_on_failure(self):
        from ai_rfq_engine.handlers.telemetry import measure_handler_duration

        logger = MagicMock()
        info = SimpleNamespace(context={"logger": logger, "partition_key": "tenant-d"})

        class TestError(Exception):
            code = "system_timeout"

        with pytest.raises(TestError):
            with measure_handler_duration(info, operation="inquire", handler="catalog"):
                raise TestError("timeout")

        logger.warning.assert_called_once()
        event = logger.warning.call_args[0][1]
        assert event["error_code"] == "system_timeout"

    @pytest.mark.unit
    def test_emit_handler_event_with_namespace(self):
        from ai_rfq_engine.handlers.telemetry import emit_handler_event

        logger = MagicMock()
        info = SimpleNamespace(context={"logger": logger, "partition_key": "tenant-e"})
        emit_handler_event(
            info, operation="inquire", handler="catalog",
            namespace="hotel",
        )
        event = logger.info.call_args[0][1]
        assert event["namespace"] == "hotel"

    @pytest.mark.unit
    def test_emit_handler_event_noop_without_logger(self):
        from ai_rfq_engine.handlers.telemetry import emit_handler_event

        info = SimpleNamespace(context={})
        emit_handler_event(info, operation="check", handler="availability")


# --- Cancellation snapshot content hash tests ------------------------------- #


class TestCancellationSnapshotContentHash:
    @pytest.mark.unit
    def test_snapshot_includes_content_hash(self):
        from ai_rfq_engine.models.quote_item import _build_cancellation_snapshot

        fake_batch = SimpleNamespace(cancellation_policy_uuid="pol-hash-001")
        fake_policy = SimpleNamespace(
            policy_uuid="pol-hash-001",
            label="Standard",
            description="Free <14d",
            tiers={"tiers": [{"days_before_service_gte": 14, "refund_pct": 1.0}]},
            notes_template_uuid=None,
        )

        with patch(
            "ai_rfq_engine.models.provider_item_batches.get_provider_item_batch",
            return_value=fake_batch,
        ), patch(
            "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy_count",
            return_value=1,
        ), patch(
            "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy",
            return_value=fake_policy,
        ):
            snapshot = _build_cancellation_snapshot(
                "tenant-test", "pi-1", "batch-001"
            )

        assert snapshot is not None
        assert "content_hash" in snapshot
        assert len(snapshot["content_hash"]) == 16
        assert snapshot["policy_uuid"] == "pol-hash-001"

    @pytest.mark.unit
    def test_content_hash_differs_for_different_policies(self):
        from ai_rfq_engine.models.quote_item import _build_cancellation_snapshot

        def _make_snapshot(policy_uuid, label):
            fake_batch = SimpleNamespace(cancellation_policy_uuid=policy_uuid)
            fake_policy = SimpleNamespace(
                policy_uuid=policy_uuid,
                label=label,
                description="desc",
                tiers={"tiers": [{"days_before_service_gte": 14, "refund_pct": 1.0}]},
                notes_template_uuid=None,
            )
            with patch(
                "ai_rfq_engine.models.provider_item_batches.get_provider_item_batch",
                return_value=fake_batch,
            ), patch(
                "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy_count",
                return_value=1,
            ), patch(
                "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy",
                return_value=fake_policy,
            ):
                return _build_cancellation_snapshot("tenant-test", "pi-1", "batch-001")

        snap_a = _make_snapshot("pol-a", "Standard")
        snap_b = _make_snapshot("pol-b", "Strict")
        assert snap_a["content_hash"] != snap_b["content_hash"]

    @pytest.mark.unit
    def test_content_hash_is_stable_for_identical_policy_terms(self):
        from ai_rfq_engine.models.quote_item import _build_cancellation_snapshot

        fake_batch = SimpleNamespace(cancellation_policy_uuid="pol-stable")
        fake_policy = SimpleNamespace(
            policy_uuid="pol-stable",
            label="Standard",
            description="Free <14d",
            tiers={"tiers": [{"days_before_service_gte": 14, "refund_pct": 1.0}]},
            notes_template_uuid=None,
        )

        with patch(
            "ai_rfq_engine.models.provider_item_batches.get_provider_item_batch",
            return_value=fake_batch,
        ), patch(
            "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy_count",
            return_value=1,
        ), patch(
            "ai_rfq_engine.models.cancellation_policy.get_cancellation_policy",
            return_value=fake_policy,
        ):
            first = _build_cancellation_snapshot("tenant-test", "pi-1", "batch-001")
            second = _build_cancellation_snapshot("tenant-test", "pi-1", "batch-001")

        assert first["content_hash"] == second["content_hash"]
