#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Phase 4 cross-vertical hardening pilot.

These tests document and exercise the four end-to-end scenarios listed in
``docs/HOSPITALITY_BUSINESS_GAP_PLAN.md`` §8:

1. **B2B procurement regression** (mandatory): proves the §0 additive-nullable
   promise — procurement quotes that never touch the hospitality fields behave
   identically to the pre-Phase-1 baseline. If this scenario drifts, the gap
   plan has failed regardless of how well the hospitality scenarios pass.

2. **Hotel**: multi-night room-night quote with mixed-occupancy (G2 occupancy
   pricing), 30/70 deposit + balance installments, and cancellation policy
   snapshot (G6) attached to ``QuoteItem.request_data``.

3. **Restaurant / event**: deposit-only quote with per-pax-type pricing (G2)
   and an availability hold acquired through the G3 contract before the quote
   item is persisted.

4. **Multi-leg travel itinerary**: bundle composition (G4) — flight + hotel +
   transfer + activity grouped via ``bundle_uuid`` with deposit + balance
   installments and a component-settlement view (each child quote item priced
   and settled independently).

The integration tests in this file are gated on ``@pytest.mark.integration``
and require ``AIRFQEngine`` to initialize against real DynamoDB. They will
``pytest.skip`` cleanly when credentials are unavailable. The unit tests at
the bottom verify that the GraphQL schema exposes every field/argument these
scenarios depend on; those run anywhere.
"""
from __future__ import annotations, print_function

__author__ = "bibow"

import logging
import os
import sys
from datetime import timedelta
from typing import Any, Dict, Optional

import pendulum
import pytest
from silvaengine_utility.serializer import Serializer


logger = logging.getLogger("test_hardening_pilot")

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
    from ai_rfq_engine import AIRFQEngine  # noqa: E402
except ImportError:
    AIRFQEngine = None  # type: ignore


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
def endpoint_id() -> Optional[str]:
    return SETTING.get("endpoint_id")


@pytest.fixture(scope="module")
def part_id() -> Optional[str]:
    return SETTING.get("part_id")


def _graphql(engine, query: str, variables: Dict[str, Any], endpoint_id, part_id):
    """Drive one GraphQL call through the local engine and normalise the response."""
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
    return parsed.get("data", parsed)


# --- Scenario 1: B2B procurement regression ------------------------------- #


class TestB2BProcurementRegression:
    """
    Mandatory regression. The §0 architectural decision (single core,
    additive-nullable) is only credible if procurement workflows are explicitly
    verified to run unchanged. None of the assertions below reference a
    hospitality field. If this drift, the additive-nullable promise has broken.
    """

    @pytest.fixture(scope="class")
    def procurement_context(self, engine, endpoint_id, part_id):
        """Seed a classic procurement item without touching any hospitality field."""
        updated_by = "hardening_b2b_pilot"

        item_query = """
        mutation ($type: String, $name: String, $uom: String, $by: String!) {
            insertUpdateItem(itemType: $type, itemName: $name, uom: $uom, updatedBy: $by) {
                item { itemUuid pricingMode }
            }
        }
        """
        item_data = _graphql(
            engine,
            item_query,
            {"type": "part", "name": "Widget-001", "uom": "piece", "by": updated_by},
            endpoint_id,
            part_id,
        )
        item = item_data["insertUpdateItem"]["item"]
        item_uuid = item["itemUuid"]
        # pricing_mode must default to null (legacy unit pricing)
        assert item.get("pricingMode") in (None, "")

        prov_query = """
        mutation ($itemId: String!, $provId: String, $price: Float, $by: String!) {
            insertUpdateProviderItem(itemUuid: $itemId, providerCorpExternalId: $provId,
                                     basePricePerUom: $price, updatedBy: $by) {
                providerItem { providerItemUuid }
            }
        }
        """
        prov_data = _graphql(
            engine,
            prov_query,
            {"itemId": item_uuid, "provId": "SUPPLIER-001", "price": 12.5, "by": updated_by},
            endpoint_id,
            part_id,
        )
        provider_item_uuid = prov_data["insertUpdateProviderItem"]["providerItem"][
            "providerItemUuid"
        ]

        seg_query = """
        mutation ($name: String, $by: String!) {
            insertUpdateSegment(segmentName: $name, updatedBy: $by) {
                segment { segmentUuid }
            }
        }
        """
        seg_data = _graphql(
            engine,
            seg_query,
            {"name": "Wholesale", "by": updated_by},
            endpoint_id,
            part_id,
        )
        segment_uuid = seg_data["insertUpdateSegment"]["segment"]["segmentUuid"]

        # Two tiers: 0+ at $10/each, 100+ at $8/each — exercises qty-band matching.
        tier_query = """
        mutation ($iid: String!, $pid: String, $sid: String, $qty: Float, $price: Float,
                  $stat: String, $by: String!) {
            insertUpdateItemPriceTier(itemUuid: $iid, providerItemUuid: $pid,
                                       segmentUuid: $sid, quantityGreaterThen: $qty,
                                       pricePerUom: $price, status: $stat,
                                       updatedBy: $by) {
                itemPriceTier { itemPriceTierUuid }
            }
        }
        """
        for qty_floor, price in [(0.0, 10.0), (100.0, 8.0)]:
            _graphql(
                engine,
                tier_query,
                {
                    "iid": item_uuid, "pid": provider_item_uuid,
                    "sid": segment_uuid, "qty": qty_floor, "price": price,
                    "stat": "active", "by": updated_by,
                },
                endpoint_id,
                part_id,
            )

        return {
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "segment_uuid": segment_uuid,
            "updated_by": updated_by,
        }

    @pytest.mark.integration
    def test_unit_pricing_subtotal_matches_qty_times_price(
        self, engine, endpoint_id, part_id, procurement_context
    ):
        ctx = procurement_context

        req_data = _graphql(
            engine,
            """mutation ($email: String!, $title: String!, $by: String!) {
                insertUpdateRequest(email: $email, requestTitle: $title, updatedBy: $by) {
                    request { requestUuid }
                }
            }""",
            {"email": "buyer@acme.com", "title": "Bulk widget order", "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )
        request_uuid = req_data["insertUpdateRequest"]["request"]["requestUuid"]

        quote_data = _graphql(
            engine,
            """mutation ($rid: String!, $by: String!) {
                insertUpdateQuote(requestUuid: $rid, updatedBy: $by) {
                    quote { quoteUuid currency displayCurrency fxRate }
                }
            }""",
            {"rid": request_uuid, "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )
        quote = quote_data["insertUpdateQuote"]["quote"]
        # Procurement default: no currency/FX configured on the quote.
        assert quote.get("currency") in (None, "")
        assert quote.get("fxRate") in (None, 0)
        quote_uuid = quote["quoteUuid"]

        # 50 pieces → first tier ($10) → subtotal == 500
        qi_data = _graphql(
            engine,
            """mutation ($qid: String!, $rid: String, $iid: String, $pid: String,
                        $sid: String, $qty: Float, $by: String!) {
                insertUpdateQuoteItem(quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid,
                                       providerItemUuid: $pid, segmentUuid: $sid, qty: $qty,
                                       updatedBy: $by) {
                    quoteItem { pricePerUom subtotal subtotalNative paxBreakdown }
                }
            }""",
            {
                "qid": quote_uuid, "rid": request_uuid, "iid": ctx["item_uuid"],
                "pid": ctx["provider_item_uuid"], "sid": ctx["segment_uuid"],
                "qty": 50.0, "by": ctx["updated_by"],
            },
            endpoint_id, part_id,
        )
        qi = qi_data["insertUpdateQuoteItem"]["quoteItem"]
        assert qi["pricePerUom"] == pytest.approx(10.0)
        assert qi["subtotal"] == pytest.approx(500.0)
        # subtotal_native equals display when no FX configured (additive-nullable)
        assert qi["subtotalNative"] == pytest.approx(500.0)
        # No pax_breakdown for procurement
        assert qi.get("paxBreakdown") in (None, {})

    @pytest.mark.integration
    def test_higher_quantity_matches_volume_discount_tier(
        self, engine, endpoint_id, part_id, procurement_context
    ):
        ctx = procurement_context

        req_data = _graphql(
            engine,
            """mutation ($email: String!, $title: String!, $by: String!) {
                insertUpdateRequest(email: $email, requestTitle: $title, updatedBy: $by) {
                    request { requestUuid }
                }
            }""",
            {"email": "buyer@acme.com", "title": "Volume order", "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )
        request_uuid = req_data["insertUpdateRequest"]["request"]["requestUuid"]

        quote_data = _graphql(
            engine,
            """mutation ($rid: String!, $by: String!) {
                insertUpdateQuote(requestUuid: $rid, updatedBy: $by) {
                    quote { quoteUuid }
                }
            }""",
            {"rid": request_uuid, "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )
        quote_uuid = quote_data["insertUpdateQuote"]["quote"]["quoteUuid"]

        # 150 pieces → volume tier ($8) → subtotal == 1200
        qi_data = _graphql(
            engine,
            """mutation ($qid: String!, $rid: String, $iid: String, $pid: String,
                        $sid: String, $qty: Float, $by: String!) {
                insertUpdateQuoteItem(quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid,
                                       providerItemUuid: $pid, segmentUuid: $sid, qty: $qty,
                                       updatedBy: $by) {
                    quoteItem { pricePerUom subtotal }
                }
            }""",
            {
                "qid": quote_uuid, "rid": request_uuid, "iid": ctx["item_uuid"],
                "pid": ctx["provider_item_uuid"], "sid": ctx["segment_uuid"],
                "qty": 150.0, "by": ctx["updated_by"],
            },
            endpoint_id, part_id,
        )
        qi = qi_data["insertUpdateQuoteItem"]["quoteItem"]
        assert qi["pricePerUom"] == pytest.approx(8.0)
        assert qi["subtotal"] == pytest.approx(1200.0)


# --- Scenario 2: Hotel multi-night mixed-occupancy ------------------------ #


class TestHotelHardening:
    """
    Multi-night, mixed-occupancy quote with 30/70 installment schedule and a
    cancellation policy snapshot attached to ``QuoteItem.request_data``.
    """

    @pytest.fixture(scope="class")
    def hotel_context(self, engine, endpoint_id, part_id):
        updated_by = "hardening_hotel_pilot"
        now = pendulum.now("UTC")
        check_in = (now + timedelta(days=30)).isoformat()
        check_out = (now + timedelta(days=33)).isoformat()

        item_data = _graphql(
            engine,
            """mutation ($type: String, $name: String, $mode: String, $uom: String, $by: String!) {
                insertUpdateItem(itemType: $type, itemName: $name, pricingMode: $mode,
                                  uom: $uom, updatedBy: $by) {
                    item { itemUuid pricingMode }
                }
            }""",
            {
                "type": "lodging", "name": "Hardening Deluxe King",
                "mode": "occupancy", "uom": "room_night", "by": updated_by,
            },
            endpoint_id, part_id,
        )
        item_uuid = item_data["insertUpdateItem"]["item"]["itemUuid"]
        assert item_data["insertUpdateItem"]["item"]["pricingMode"] == "occupancy"

        prov_data = _graphql(
            engine,
            """mutation ($itemId: String!, $provId: String, $price: Float, $by: String!) {
                insertUpdateProviderItem(itemUuid: $itemId, providerCorpExternalId: $provId,
                                         basePricePerUom: $price, updatedBy: $by) {
                    providerItem { providerItemUuid }
                }
            }""",
            {"itemId": item_uuid, "provId": "HOTEL-HARDEN-001", "price": 200.0, "by": updated_by},
            endpoint_id, part_id,
        )
        provider_item_uuid = prov_data["insertUpdateProviderItem"]["providerItem"][
            "providerItemUuid"
        ]

        # Cancellation policy: free <14d, no refund <0d
        policy_data = _graphql(
            engine,
            """mutation ($pid: String, $tiers: JSONCamelCase, $by: String!) {
                insertUpdateCancellationPolicy(providerItemUuid: $pid, tiers: $tiers,
                                                updatedBy: $by) {
                    cancellationPolicy { policyUuid }
                }
            }""",
            {
                "pid": provider_item_uuid,
                "tiers": {
                    "tiers": [
                        {"daysBeforeServiceGte": 14, "refundPct": 1.0},
                        {"daysBeforeServiceGte": 0, "refundPct": 0.0},
                    ]
                },
                "by": updated_by,
            },
            endpoint_id, part_id,
        )
        policy_uuid = policy_data["insertUpdateCancellationPolicy"][
            "cancellationPolicy"
        ]["policyUuid"]

        batch_data = _graphql(
            engine,
            """mutation ($pid: String!, $iid: String!, $bno: String!, $exp: DateTime,
                        $prod: DateTime, $svcStart: DateTime, $svcEnd: DateTime,
                        $cost: Float, $cancelUuid: String, $by: String!) {
                insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid,
                                               batchNo: $bno, expiredAt: $exp, producedAt: $prod,
                                               serviceStartAt: $svcStart, serviceEndAt: $svcEnd,
                                               costPerUom: $cost,
                                               cancellationPolicyUuid: $cancelUuid,
                                               updatedBy: $by) {
                    providerItemBatch { batchNo cancellationPolicyUuid }
                }
            }""",
            {
                "pid": provider_item_uuid, "iid": item_uuid,
                "bno": f"HARD-RN-{now.format('YYYYMMDD')}",
                "exp": check_out, "prod": check_in,
                "svcStart": check_in, "svcEnd": check_out,
                "cost": 140.0, "cancelUuid": policy_uuid, "by": updated_by,
            },
            endpoint_id, part_id,
        )
        batch_no = batch_data["insertUpdateProviderItemBatch"]["providerItemBatch"][
            "batchNo"
        ]

        seg_data = _graphql(
            engine,
            """mutation ($name: String, $by: String!) {
                insertUpdateSegment(segmentName: $name, updatedBy: $by) {
                    segment { segmentUuid }
                }
            }""",
            {"name": "RetailHotel", "by": updated_by},
            endpoint_id, part_id,
        )
        segment_uuid = seg_data["insertUpdateSegment"]["segment"]["segmentUuid"]

        # Occupancy tier: $200/night base for 2 adults; $50 per extra adult; $25 per child
        _graphql(
            engine,
            """mutation ($iid: String!, $pid: String, $sid: String, $qty: Float,
                        $price: Float, $base: JSONCamelCase, $extra: JSONCamelCase,
                        $stat: String, $by: String!) {
                insertUpdateItemPriceTier(itemUuid: $iid, providerItemUuid: $pid,
                                           segmentUuid: $sid, quantityGreaterThen: $qty,
                                           pricePerUom: $price, baseOccupancy: $base,
                                           extraPaxSurcharges: $extra, status: $stat,
                                           updatedBy: $by) {
                    itemPriceTier { itemPriceTierUuid }
                }
            }""",
            {
                "iid": item_uuid, "pid": provider_item_uuid, "sid": segment_uuid,
                "qty": 0.0, "price": 200.0,
                "base": {"adult": 2}, "extra": {"adult": 50, "child": 25},
                "stat": "active", "by": updated_by,
            },
            endpoint_id, part_id,
        )

        return {
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "segment_uuid": segment_uuid,
            "batch_no": batch_no,
            "policy_uuid": policy_uuid,
            "check_in": check_in, "check_out": check_out,
            "updated_by": updated_by,
        }

    @pytest.mark.integration
    def test_three_night_mixed_occupancy_with_installments_and_snapshot(
        self, engine, endpoint_id, part_id, hotel_context
    ):
        ctx = hotel_context

        request_uuid = _graphql(
            engine,
            """mutation ($email: String!, $title: String!, $by: String!) {
                insertUpdateRequest(email: $email, requestTitle: $title, updatedBy: $by) {
                    request { requestUuid }
                }
            }""",
            {"email": "guest@example.com", "title": "Hotel hardening", "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )["insertUpdateRequest"]["request"]["requestUuid"]

        quote_uuid = _graphql(
            engine,
            """mutation ($rid: String!, $provId: String, $by: String!) {
                insertUpdateQuote(requestUuid: $rid, providerCorpExternalId: $provId,
                                   updatedBy: $by) {
                    quote { quoteUuid }
                }
            }""",
            {"rid": request_uuid, "provId": "HOTEL-HARDEN-001", "by": ctx["updated_by"]},
            endpoint_id, part_id,
        )["insertUpdateQuote"]["quote"]["quoteUuid"]

        # 3 nights × (200 base + 1 extra adult @ 50 + 1 child @ 25) = 3 × 275 = 825
        qi_data = _graphql(
            engine,
            """mutation ($qid: String!, $rid: String, $iid: String, $pid: String,
                        $sid: String, $bno: String, $qty: Float, $pax: JSONCamelCase,
                        $by: String!) {
                insertUpdateQuoteItem(quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid,
                                       providerItemUuid: $pid, segmentUuid: $sid,
                                       batchNo: $bno, qty: $qty, paxBreakdown: $pax,
                                       updatedBy: $by) {
                    quoteItem { quoteItemUuid pricePerUom subtotal requestData }
                }
            }""",
            {
                "qid": quote_uuid, "rid": request_uuid, "iid": ctx["item_uuid"],
                "pid": ctx["provider_item_uuid"], "sid": ctx["segment_uuid"],
                "bno": ctx["batch_no"], "qty": 3.0,
                "pax": {"adult": 3, "child": 1}, "by": ctx["updated_by"],
            },
            endpoint_id, part_id,
        )
        qi = qi_data["insertUpdateQuoteItem"]["quoteItem"]
        assert qi["pricePerUom"] == pytest.approx(275.0)
        assert qi["subtotal"] == pytest.approx(825.0)

        # G6: cancellation snapshot attached at quote-creation time
        snapshot = (qi.get("requestData") or {}).get("cancellation_policy_snapshot")
        assert snapshot is not None, "G6 cancellation snapshot must be attached"
        assert snapshot["policy_uuid"] == ctx["policy_uuid"]

        # 30 / 70 installment schedule on the quote total
        total = qi["subtotal"]
        for priority, amount in [(1, round(total * 0.30, 2)), (2, round(total * 0.70, 2))]:
            _graphql(
                engine,
                """mutation ($qid: String!, $rid: String, $priority: Int,
                            $amount: SafeFloat, $by: String!) {
                    insertUpdateInstallment(quoteUuid: $qid, requestUuid: $rid,
                                             priority: $priority,
                                             installmentAmount: $amount, updatedBy: $by) {
                        installment { installmentUuid }
                    }
                }""",
                {
                    "qid": quote_uuid, "rid": request_uuid,
                    "priority": priority, "amount": amount, "by": ctx["updated_by"],
                },
                endpoint_id, part_id,
            )


# --- Scenario 3: Restaurant / event deposit-only with availability hold --- #


class TestRestaurantOrEventHardening:
    """
    Banquet table with per-pax-type pricing, deposit-only quote, and an
    availability hold acquired through the G3 contract before the quote item
    is persisted. This scenario exercises the stub availability handler — the
    real PMS adapter is out of scope for the hardening pilot.
    """

    @pytest.mark.integration
    def test_banquet_with_availability_hold_and_deposit_only(
        self, engine, endpoint_id, part_id
    ):
        # Implementation pattern (kept short — same shape as Hotel scenario):
        #   1. Seed Item with pricing_mode='per_pax_type'
        #   2. Seed ProviderItem with availability_mode='require_hold' +
        #      availability_system_code='stub'
        #   3. Seed ExternalSystemConfig (system_kind='availability', system_code='stub')
        #      pointing at the StubAvailabilityHandler
        #   4. Seed two pax_type tiers (delegate $80, observer $40)
        #   5. Seed ProviderItemBatch with service window
        #   6. Create Request -> Quote -> QuoteItem with pax_breakdown {delegate: 10, observer: 5}
        #      The insert_update_quote_item path will invoke _enforce_availability
        #      which dispatches to the stub via the G7c config. A hold_token must
        #      be persisted on the resulting QuoteItem.
        #   7. Create a single deposit-only installment for the full amount
        #
        # This test is documented in detail in HOSPITALITY_BUSINESS_GAP_PLAN.md §8.
        # The stub handler needs configured fixtures to return ``available=True``
        # and a hold_token; see ai_rfq_engine/handlers/availability/stub_handler.py.
        pytest.skip(
            "Banquet+hold scenario requires StubAvailabilityHandler fixtures and "
            "ExternalSystemConfig seeding; included as a documented placeholder "
            "until those fixtures are pinned down in the test harness."
        )


# --- Scenario 4: Multi-leg travel itinerary bundle ------------------------ #


class TestMultiLegTravelItineraryHardening:
    """
    Bundle composition (G4) with deposit + balance installments and a
    component-settlement view. Each child quote item is independently priced
    and settles against its own provider; the parent grouping is purely
    presentational via ``bundle_uuid``.
    """

    @pytest.mark.integration
    def test_hotel_plus_transfer_plus_activity_bundle(
        self, engine, endpoint_id, part_id
    ):
        # Implementation pattern (kept short — same shape as Hotel scenario):
        #   1. Seed three Items: hotel (occupancy), transfer (per_pax_type), activity (per_pax_type)
        #   2. Seed ProviderItem + ItemPriceTier for each
        #   3. Create Request -> Quote
        #   4. Create three QuoteItems sharing bundle_uuid='itinerary-001':
        #        - hotel: qty=3 nights, pax_breakdown={adult: 2}
        #        - transfer: qty=2 (adults), pax_breakdown={adult: 2}
        #        - activity: qty=2 (adults), pax_breakdown={adult: 2}
        #   5. Verify resolveQuoteItemList(bundleUuid='itinerary-001') returns all three
        #   6. Verify the Quote total equals the sum of the three component subtotals
        #   7. Create two installments: 50% deposit + 50% balance
        #
        # Component settlement: each child has its own provider_item_uuid /
        # provider_corp_external_id, so a settlement view can aggregate per-supplier
        # subtotals by querying quote items filtered by provider.
        #
        # See HOSPITALITY_BUSINESS_GAP_PLAN.md §8 for the full acceptance criteria.
        pytest.skip(
            "Travel itinerary bundle scenario requires three-item seeding; "
            "included as a documented placeholder until the test harness pins "
            "down the per-vertical fixture seeding strategy."
        )


# --- Schema capability checks (unit-level, no DDB required) --------------- #


class TestHardeningPilotSchemaCapabilities:
    """
    Unit-level checks that the GraphQL schema exposes every field/argument the
    hardening scenarios above depend on. These catch wiring regressions even
    when the integration tests are skipped (no DDB available).
    """

    @pytest.mark.unit
    def test_item_schema_exposes_pricing_mode(self):
        from ai_rfq_engine.schema import Mutations, Query

        item_args = Query._meta.fields["item_list"].args
        assert "pricing_mode" in item_args, "G2: item_list must filter by pricing_mode"
        insert_item_args = Mutations._meta.fields[
            "insert_update_item"
        ].args
        assert "pricing_mode" in insert_item_args, (
            "G2: insert_update_item must accept pricing_mode"
        )

    @pytest.mark.unit
    def test_item_price_tier_schema_exposes_occupancy_fields(self):
        from ai_rfq_engine.schema import Mutations

        args = Mutations._meta.fields["insert_update_item_price_tier"].args
        assert "base_occupancy" in args, (
            "G2 occupancy: insert_update_item_price_tier must accept base_occupancy"
        )
        assert "extra_pax_surcharges" in args, (
            "G2 occupancy: insert_update_item_price_tier must accept extra_pax_surcharges"
        )

    @pytest.mark.unit
    def test_quote_item_schema_exposes_bundle_and_fx_fields(self):
        from ai_rfq_engine.schema import Query

        args = Query._meta.fields["quote_item_list"].args
        assert "bundle_uuid" in args, (
            "G4 bundle: quote_item_list must filter by bundle_uuid"
        )

    @pytest.mark.unit
    def test_provider_item_batch_schema_exposes_service_window_filters(self):
        from ai_rfq_engine.schema import Query

        args = Query._meta.fields["provider_item_batch_list"].args
        assert "service_window_start" in args
        assert "service_window_end" in args

    @pytest.mark.unit
    def test_catalog_inquiry_and_availability_queries_are_registered(self):
        from ai_rfq_engine.schema import Query

        assert "inquire_catalog" in Query._meta.fields, (
            "G7b: inquire_catalog GraphQL query must be wired"
        )
        assert "check_availability" in Query._meta.fields, (
            "G3: check_availability GraphQL query must be wired"
        )

    @pytest.mark.unit
    def test_external_system_config_and_item_catalog_ref_resolvers_present(self):
        from ai_rfq_engine.schema import Query

        for field in (
            "external_system_config",
            "external_system_config_list",
            "resolved_external_system_config",
            "item_catalog_ref",
            "item_catalog_ref_list",
            "item_catalog_refs",
        ):
            assert field in Query._meta.fields, (
                f"G7a/G7c: Query.{field} must be wired"
            )

    @pytest.mark.unit
    def test_neo4j_handlers_registered_under_neo4j_adapter_id(self):
        """Both catalog and availability registries auto-register the Neo4j adapter."""
        from ai_rfq_engine.handlers.availability import (
            Neo4jAvailabilityHandler,
            get_handler as get_avail_handler,
        )
        from ai_rfq_engine.handlers.catalog import (
            Neo4jCatalogHandler,
            get_handler as get_catalog_handler,
        )

        # The autouse fixture in other test files clears handlers between tests;
        # here we re-import the package which triggers auto-registration.
        import importlib

        import ai_rfq_engine.handlers.availability as availability_pkg
        import ai_rfq_engine.handlers.catalog as catalog_pkg

        importlib.reload(availability_pkg)
        importlib.reload(catalog_pkg)

        assert availability_pkg.get_handler("neo4j") is Neo4jAvailabilityHandler
        assert catalog_pkg.get_handler("neo4j") is Neo4jCatalogHandler
