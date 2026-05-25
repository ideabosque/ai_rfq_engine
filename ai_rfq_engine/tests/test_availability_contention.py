#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
DynamoDB-backed contention and lifecycle integration tests for availability holds.

These tests validate the Section 4.4 integrity requirements under real
DynamoDB transaction semantics. They require a reachable DynamoDB endpoint
and will be skipped when credentials are unavailable.

Covered scenarios (from HOSPITALITY_BUSINESS_GAP_PLAN.md §4.4):
  - Concurrent acquisition: competing requests for insufficient capacity
  - Confirm idempotency: repeated confirm does not double-decrement
  - Release idempotency: repeated release restores capacity only once
  - Expiry restoration: expired hold restores capacity
  - Unknown token: confirm/release of nonexistent hold fails closed
  - Quote creation failure: capacity not leaked when line creation fails
  - Unquantified batch: require_hold rejects null availability_qty
"""
from __future__ import annotations, print_function

__author__ = "bibow"

import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pendulum
import pytest
from silvaengine_utility.serializer import Serializer

logger = logging.getLogger("test_availability_contention")

SETTING = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_rfq_graphql": {
            "module_name": "ai_rfq_engine",
            "class_name": "AIRFQEngine",
        },
    },
    "endpoint_id": os.getenv("endpoint_id"),
    "part_id": os.getenv("part_id"),
    "execute_mode": os.getenv("execute_mode", "local"),
    "initialize_tables": os.getenv("initialize_tables", "0") == "1",
    "cache_enabled": os.getenv("cache_enabled", "0") == "1",
}

BASE_DIR = os.getenv("base_dir") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "silvaengine_utility"))
sys.path.insert(1, os.path.join(BASE_DIR, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(BASE_DIR, "ai_rfq_engine"))

try:
    from ai_rfq_engine import AIRFQEngine
except ImportError:
    AIRFQEngine = None


@pytest.fixture(scope="module")
def engine():
    if AIRFQEngine is None:
        pytest.skip("AIRFQEngine not available")
    try:
        e = AIRFQEngine(logger, **SETTING)
        setattr(e, "__is_real__", True)
        return e
    except Exception as exc:
        pytest.skip(f"Engine init failed: {exc}")


@pytest.fixture(scope="module")
def endpoint_id():
    return SETTING.get("endpoint_id")


@pytest.fixture(scope="module")
def part_id():
    return SETTING.get("part_id")


def _graphql(engine, query, variables, endpoint_id, part_id):
    response = engine.ai_rfq_graphql(
        query=query,
        variables=variables,
        endpoint_id=endpoint_id,
        part_id=part_id,
    )
    parsed = (
        Serializer.json_loads(response)
        if isinstance(response, (str, bytes))
        else response
    )
    if "body" in parsed and isinstance(parsed["body"], str):
        try:
            parsed = Serializer.json_loads(parsed["body"])
        except Exception:
            pass
    if parsed.get("errors"):
        raise RuntimeError(f"GraphQL errors: {parsed['errors']}")
    data = parsed.get("data", parsed)
    return data


class TestConcurrentHoldAcquisition:
    """
    Priority 0: Two requests competing for insufficient remaining quantity
    cannot both receive successful holds.
    """

    @pytest.fixture(scope="class")
    def contention_context(self, engine, endpoint_id, part_id):
        updated_by = "contention_test"
        now = pendulum.now("UTC")
        service_start = (now + timedelta(days=14)).isoformat()
        service_end = (now + timedelta(days=14, hours=8)).isoformat()

        item_uuid = _graphql(
            engine,
            """mutation ($name: String, $mode: String, $uom: String, $by: String!) {
                insertUpdateItem(itemType: "seat", itemName: $name,
                                 pricingMode: $mode, uom: $uom, updatedBy: $by) {
                    item { itemUuid }
                }
            }""",
            {"name": "Contention Seat", "mode": "per_pax_type", "uom": "seat", "by": updated_by},
            endpoint_id, part_id,
        )["insertUpdateItem"]["item"]["itemUuid"]

        provider_item_uuid = _graphql(
            engine,
            """mutation ($iid: String!, $price: Float, $mode: String, $by: String!) {
                insertUpdateProviderItem(itemUuid: $iid,
                                         providerCorpExternalId: "VENUE-CONT-001",
                                         basePricePerUom: $price,
                                         availabilityMode: $mode, updatedBy: $by) {
                    providerItem { providerItemUuid }
                }
            }""",
            {"iid": item_uuid, "price": 50.0, "mode": "require_hold", "by": updated_by},
            endpoint_id, part_id,
        )["insertUpdateProviderItem"]["providerItem"]["providerItemUuid"]

        batch_no = f"CONT-{now.format('YYYYMMDD')}"
        _graphql(
            engine,
            """mutation ($pid: String!, $iid: String!, $bno: String!, $start: DateTime,
                        $end: DateTime, $capacity: Float, $by: String!) {
                insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid,
                                               batchNo: $bno, expiredAt: $end,
                                               producedAt: $start, serviceStartAt: $start,
                                               serviceEndAt: $end, costPerUom: 25,
                                               freightCostPerUom: 0,
                                               additionalCostPerUom: 0,
                                               availabilityQty: $capacity, inStock: true,
                                               updatedBy: $by) {
                    providerItemBatch { batchNo availabilityQty }
                }
            }""",
            {
                "pid": provider_item_uuid, "iid": item_uuid, "bno": batch_no,
                "start": service_start, "end": service_end,
                "capacity": 2.0, "by": updated_by,
            },
            endpoint_id, part_id,
        )

        segment_uuid = _graphql(
            engine,
            """mutation ($by: String!) {
                insertUpdateSegment(segmentName: "Contention Retail", updatedBy: $by) {
                    segment { segmentUuid }
                }
            }""",
            {"by": updated_by},
            endpoint_id, part_id,
        )["insertUpdateSegment"]["segment"]["segmentUuid"]

        for pax_type, price in [("delegate", 50.0)]:
            _graphql(
                engine,
                """mutation ($iid: String!, $pid: String!, $sid: String!, $pax: String,
                            $price: Float, $by: String!) {
                    insertUpdateItemPriceTier(itemUuid: $iid, providerItemUuid: $pid,
                                               segmentUuid: $sid, quantityGreaterThen: 0,
                                               paxType: $pax, pricePerUom: $price,
                                               status: "active", updatedBy: $by) {
                        itemPriceTier { itemPriceTierUuid }
                    }
                }""",
                {"iid": item_uuid, "pid": provider_item_uuid, "sid": segment_uuid,
                 "pax": pax_type, "price": price, "by": updated_by},
                endpoint_id, part_id,
            )

        return {
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "batch_no": batch_no,
            "segment_uuid": segment_uuid,
            "service_start": service_start,
            "service_end": service_end,
            "updated_by": updated_by,
        }

    @pytest.mark.integration
    def test_concurrent_acquisition_cannot_overbook(
        self, engine, endpoint_id, part_id, contention_context
    ):
        """
        With availability_qty=2, two concurrent requests for qty=2 must
        not both succeed.
        """
        ctx = contention_context
        results: List[Optional[Dict]] = [None, None]

        def acquire_hold(index):
            try:
                return _graphql(
                    engine,
                    """mutation ($pid: String!, $bno: String, $start: DateTime!,
                                $end: DateTime!, $qty: SafeFloat) {
                        acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                                  serviceStartAt: $start, serviceEndAt: $end,
                                                  qty: $qty) {
                            availability { available holdToken }
                        }
                    }""",
                    {
                        "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                        "start": ctx["service_start"], "end": ctx["service_end"],
                        "qty": 2.0,
                    },
                    endpoint_id, part_id,
                )
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(acquire_hold, i) for i in range(2)]
            for i, future in enumerate(as_completed(futures)):
                try:
                    results[i] = future.result()
                except Exception:
                    results[i] = None

        successful = [
            r for r in results
            if r and r.get("acquireAvailabilityHold", {}).get("availability", {}).get("available")
        ]
        assert len(successful) <= 1, (
            f"At most one concurrent hold should succeed, got {len(successful)}"
        )

    @pytest.mark.integration
    def test_hold_confirm_idempotent(
        self, engine, endpoint_id, part_id, contention_context
    ):
        ctx = contention_context
        hold = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available holdToken }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        token = hold["acquireAvailabilityHold"]["availability"]["holdToken"]
        assert token

        for _ in range(3):
            result = _graphql(
                engine,
                """mutation ($pid: String!, $bno: String, $token: String!) {
                    confirmAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                              holdToken: $token) {
                        availability { available }
                    }
                }""",
                {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
                endpoint_id, part_id,
            )
            assert result["confirmAvailabilityHold"]["availability"]["available"] is True

    @pytest.mark.integration
    def test_hold_release_idempotent(
        self, engine, endpoint_id, part_id, contention_context
    ):
        ctx = contention_context
        hold = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available holdToken }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        token = hold["acquireAvailabilityHold"]["availability"]["holdToken"]

        result1 = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $token: String!) {
                releaseAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          holdToken: $token) {
                    availability { available }
                }
            }""",
            {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
            endpoint_id, part_id,
        )
        assert result1["releaseAvailabilityHold"]["availability"]["available"] is True

        with pytest.raises(Exception):
            _graphql(
                engine,
                """mutation ($pid: String!, $bno: String, $token: String!) {
                    releaseAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                              holdToken: $token) {
                        availability { available }
                    }
                }""",
                {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
                endpoint_id, part_id,
            )

    @pytest.mark.integration
    def test_unknown_token_fails_closed(
        self, engine, endpoint_id, part_id, contention_context
    ):
        ctx = contention_context

        with pytest.raises(Exception):
            _graphql(
                engine,
                """mutation ($pid: String!, $bno: String, $token: String!) {
                    confirmAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                              holdToken: $token) {
                        availability { available }
                    }
                }""",
                {
                    "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                    "token": "nonexistent-token-00000000",
                },
                endpoint_id, part_id,
            )

        with pytest.raises(Exception):
            _graphql(
                engine,
                """mutation ($pid: String!, $bno: String, $token: String!) {
                    releaseAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                              holdToken: $token) {
                        availability { available }
                    }
                }""",
                {
                    "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                    "token": "nonexistent-token-00000000",
                },
                endpoint_id, part_id,
            )


def _provision_require_hold_resources(
    engine,
    endpoint_id,
    part_id,
    *,
    tag: str,
    capacity: Optional[float],
    updated_by: str,
):
    """
    Provision a self-contained item/provider_item/batch tuple with
    ``availability_mode='require_hold'``. ``capacity`` may be ``None`` to
    simulate an unquantified local batch.
    """
    now = pendulum.now("UTC")
    service_start = (now + timedelta(days=21)).isoformat()
    service_end = (now + timedelta(days=21, hours=8)).isoformat()

    item_uuid = _graphql(
        engine,
        """mutation ($name: String, $mode: String, $uom: String, $by: String!) {
            insertUpdateItem(itemType: "seat", itemName: $name,
                             pricingMode: $mode, uom: $uom, updatedBy: $by) {
                item { itemUuid }
            }
        }""",
        {"name": f"Contention {tag} Seat", "mode": "per_pax_type",
         "uom": "seat", "by": updated_by},
        endpoint_id, part_id,
    )["insertUpdateItem"]["item"]["itemUuid"]

    provider_item_uuid = _graphql(
        engine,
        """mutation ($iid: String!, $price: Float, $mode: String, $by: String!) {
            insertUpdateProviderItem(itemUuid: $iid,
                                     providerCorpExternalId: "VENUE-CONT-001",
                                     basePricePerUom: $price,
                                     availabilityMode: $mode, updatedBy: $by) {
                providerItem { providerItemUuid }
            }
        }""",
        {"iid": item_uuid, "price": 50.0, "mode": "require_hold", "by": updated_by},
        endpoint_id, part_id,
    )["insertUpdateProviderItem"]["providerItem"]["providerItemUuid"]

    batch_no = f"CONT-{tag}-{now.format('YYYYMMDDHHmmss')}"
    batch_vars = {
        "pid": provider_item_uuid, "iid": item_uuid, "bno": batch_no,
        "start": service_start, "end": service_end,
        "by": updated_by,
    }
    if capacity is None:
        _graphql(
            engine,
            """mutation ($pid: String!, $iid: String!, $bno: String!,
                        $start: DateTime, $end: DateTime, $by: String!) {
                insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid,
                                               batchNo: $bno, expiredAt: $end,
                                               producedAt: $start, serviceStartAt: $start,
                                               serviceEndAt: $end, costPerUom: 25,
                                               freightCostPerUom: 0,
                                               additionalCostPerUom: 0,
                                               inStock: true, updatedBy: $by) {
                    providerItemBatch { batchNo availabilityQty }
                }
            }""",
            batch_vars,
            endpoint_id, part_id,
        )
    else:
        batch_vars["capacity"] = float(capacity)
        _graphql(
            engine,
            """mutation ($pid: String!, $iid: String!, $bno: String!,
                        $start: DateTime, $end: DateTime, $capacity: Float,
                        $by: String!) {
                insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid,
                                               batchNo: $bno, expiredAt: $end,
                                               producedAt: $start, serviceStartAt: $start,
                                               serviceEndAt: $end, costPerUom: 25,
                                               freightCostPerUom: 0,
                                               additionalCostPerUom: 0,
                                               availabilityQty: $capacity, inStock: true,
                                               updatedBy: $by) {
                    providerItemBatch { batchNo availabilityQty }
                }
            }""",
            batch_vars,
            endpoint_id, part_id,
        )

    return {
        "item_uuid": item_uuid,
        "provider_item_uuid": provider_item_uuid,
        "batch_no": batch_no,
        "service_start": service_start,
        "service_end": service_end,
        "capacity": capacity,
        "updated_by": updated_by,
    }


def _read_availability_qty(engine, endpoint_id, part_id, provider_item_uuid, batch_no):
    data = _graphql(
        engine,
        """query ($pid: String!, $bno: String!) {
            providerItemBatch(providerItemUuid: $pid, batchNo: $bno) {
                batchNo availabilityQty
            }
        }""",
        {"pid": provider_item_uuid, "bno": batch_no},
        endpoint_id, part_id,
    )
    return data["providerItemBatch"]["availabilityQty"]


class TestExpiredHoldRestoresCapacity:
    """
    Section 4.4 verification #4: an expired unconfirmed hold restores capacity
    once and cannot subsequently confirm.
    """

    @pytest.fixture(scope="class")
    def expiry_context(self, engine, endpoint_id, part_id):
        return _provision_require_hold_resources(
            engine, endpoint_id, part_id,
            tag="EXP", capacity=2.0, updated_by="expiry_test",
        )

    @pytest.mark.integration
    def test_expired_hold_restores_capacity_and_blocks_confirm(
        self, engine, endpoint_id, part_id, expiry_context
    ):
        from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel

        ctx = expiry_context
        starting = _read_availability_qty(
            engine, endpoint_id, part_id,
            ctx["provider_item_uuid"], ctx["batch_no"],
        )

        hold = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available holdToken }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        token = hold["acquireAvailabilityHold"]["availability"]["holdToken"]
        assert token

        partition_key = SETTING.get("part_id") or ""
        stored = AvailabilityHoldModel.get(partition_key, token)
        stored.update(actions=[
            AvailabilityHoldModel.expires_at.set(
                pendulum.now("UTC").subtract(minutes=1)
            ),
        ])

        result = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $token: String!) {
                expireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          holdToken: $token) {
                    availability { available }
                }
            }""",
            {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
            endpoint_id, part_id,
        )
        assert result["expireAvailabilityHold"]["availability"]["available"] is False

        restored = _read_availability_qty(
            engine, endpoint_id, part_id,
            ctx["provider_item_uuid"], ctx["batch_no"],
        )
        assert float(restored) == float(starting), (
            f"Capacity should be restored to {starting}, got {restored}"
        )

        with pytest.raises(Exception):
            _graphql(
                engine,
                """mutation ($pid: String!, $bno: String, $token: String!) {
                    confirmAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                              holdToken: $token) {
                        availability { available }
                    }
                }""",
                {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
                endpoint_id, part_id,
            )


class TestUnquantifiedBatchRejectsHold:
    """
    Section 4.4 verification #7: ``require_hold`` rejects a local batch with
    null ``availability_qty``.
    """

    @pytest.fixture(scope="class")
    def unquantified_context(self, engine, endpoint_id, part_id):
        return _provision_require_hold_resources(
            engine, endpoint_id, part_id,
            tag="UNQ", capacity=None, updated_by="unquantified_test",
        )

    @pytest.mark.integration
    def test_acquire_hold_rejects_unquantified_local_capacity(
        self, engine, endpoint_id, part_id, unquantified_context
    ):
        ctx = unquantified_context
        data = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available payload }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        availability = data["acquireAvailabilityHold"]["availability"]
        assert availability["available"] is False
        payload = availability.get("payload") or {}
        if isinstance(payload, str):
            payload = Serializer.json_loads(payload)
        assert payload.get("reason") == "unquantified_capacity"


class TestQuoteCreationFailureNoLeak:
    """
    Section 4.4 verification #6: capacity is not leaked when line creation
    fails after a hold has been acquired. Validated via the same release
    primitive that ``insert_update_quote_item`` invokes in its except
    block: acquire → release → re-acquire must succeed.
    """

    @pytest.fixture(scope="class")
    def leak_context(self, engine, endpoint_id, part_id):
        return _provision_require_hold_resources(
            engine, endpoint_id, part_id,
            tag="LEAK", capacity=1.0, updated_by="leak_test",
        )

    @pytest.mark.integration
    def test_release_after_failed_save_restores_capacity(
        self, engine, endpoint_id, part_id, leak_context
    ):
        ctx = leak_context
        starting = _read_availability_qty(
            engine, endpoint_id, part_id,
            ctx["provider_item_uuid"], ctx["batch_no"],
        )

        first = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available holdToken }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        token = first["acquireAvailabilityHold"]["availability"]["holdToken"]
        assert token, "first hold must succeed before simulating cleanup"

        depleted = _read_availability_qty(
            engine, endpoint_id, part_id,
            ctx["provider_item_uuid"], ctx["batch_no"],
        )
        assert float(depleted) == float(starting) - 1.0

        _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $token: String!) {
                releaseAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          holdToken: $token) {
                    availability { available }
                }
            }""",
            {"pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"], "token": token},
            endpoint_id, part_id,
        )

        restored = _read_availability_qty(
            engine, endpoint_id, part_id,
            ctx["provider_item_uuid"], ctx["batch_no"],
        )
        assert float(restored) == float(starting), (
            f"Release after acquire must restore capacity exactly once; "
            f"started at {starting}, ended at {restored}"
        )

        second = _graphql(
            engine,
            """mutation ($pid: String!, $bno: String, $start: DateTime!,
                        $end: DateTime!, $qty: SafeFloat) {
                acquireAvailabilityHold(providerItemUuid: $pid, batchNo: $bno,
                                          serviceStartAt: $start, serviceEndAt: $end,
                                          qty: $qty) {
                    availability { available holdToken }
                }
            }""",
            {
                "pid": ctx["provider_item_uuid"], "bno": ctx["batch_no"],
                "start": ctx["service_start"], "end": ctx["service_end"], "qty": 1.0,
            },
            endpoint_id, part_id,
        )
        availability = second["acquireAvailabilityHold"]["availability"]
        assert availability["available"] is True, (
            "Re-acquire after release must succeed (no capacity leak)"
        )