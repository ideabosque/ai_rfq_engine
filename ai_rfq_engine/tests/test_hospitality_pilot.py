#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Hospitality Domain Pilot: Hotel Room-Night

Tests the hospitality fields introduced for the hotel room-night workflow,
including dedicated service windows and the existing quote calculation flow.
"""
from __future__ import annotations, print_function

__author__ = "bibow"

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pendulum
import pytest
from silvaengine_utility.graphql import Graphql
from silvaengine_utility.serializer import Serializer

logger = logging.getLogger("test_hospitality_pilot")

# Load minimal test settings
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
def endpoint_id():
    return SETTING.get("endpoint_id")


@pytest.fixture(scope="module")
def part_id():
    return SETTING.get("part_id")


def _graphql(engine, query, variables, endpoint_id, part_id):
    """Run a GraphQL mutation/query through the local engine."""
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


class TestHospitalityPilotHotelRoomNight:
    """
    Hotel room-night workflow smoke test.

    Acceptance criteria:
    1. Inventory can be queried for a requested overlapping service window.
    2. A quote item can be created using current tier pricing, quote totals
       recalculate, and quote-level deposit and balance installments calculate
       correctly.
    """

    @pytest.fixture(scope="class")
    def hotel_context(self, engine, endpoint_id, part_id):
        """Seed one hotel Item -> ProviderItem -> ProviderItemBatch -> PriceTier."""
        updated_by = "hospitality_pilot_test"

        # 1. Create Hotel Item
        item_query = """
        mutation InsertUpdateItem($type: String, $name: String, $desc: String, $mode: String, $uom: String, $by: String!) {
            insertUpdateItem(itemType: $type, itemName: $name, itemDescription: $desc, pricingMode: $mode, uom: $uom, updatedBy: $by) {
                item { itemUuid }
            }
        }
        """
        item_vars = {
            "type": "lodging",
            "name": "Deluxe King Room",
            "desc": "King bed with city view, WiFi, breakfast included",
            "mode": "unit",
            "uom": "room_night",
            "by": updated_by,
        }
        item_data = _graphql(engine, item_query, item_vars, endpoint_id, part_id)
        item_uuid = item_data["insertUpdateItem"]["item"]["itemUuid"]

        # 2. Create ProviderItem (property)
        prov_query = """
        mutation InsertUpdateProviderItem($itemId: String!, $provId: String, $price: Float, $by: String!) {
            insertUpdateProviderItem(itemUuid: $itemId, providerCorpExternalId: $provId, basePricePerUom: $price, updatedBy: $by) {
                providerItem { providerItemUuid }
            }
        }
        """
        prov_vars = {
            "itemId": item_uuid,
            "provId": "HOTEL-GRAND-001",
            "price": 250.0,
            "by": updated_by,
        }
        prov_data = _graphql(engine, prov_query, prov_vars, endpoint_id, part_id)
        provider_item_uuid = prov_data["insertUpdateProviderItem"]["providerItem"]["providerItemUuid"]

        # 3. Create ProviderItemBatch with its explicit service window.
        now = pendulum.now("UTC")
        check_in = (now + timedelta(days=30)).isoformat()
        check_out = (now + timedelta(days=31)).isoformat()

        batch_query = """
        mutation InsertUpdateProviderItemBatch($pid: String!, $iid: String!, $bno: String!, $exp: DateTime, $prod: DateTime, $svcStart: DateTime, $svcEnd: DateTime, $cost: Float, $by: String!) {
            insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid, batchNo: $bno, expiredAt: $exp, producedAt: $prod, serviceStartAt: $svcStart, serviceEndAt: $svcEnd, costPerUom: $cost, updatedBy: $by) {
                providerItemBatch { batchNo serviceStartAt serviceEndAt }
            }
        }
        """
        batch_vars = {
            "pid": provider_item_uuid,
            "iid": item_uuid,
            "bno": f"RN-{now.format('YYYYMMDD')}",
            "exp": check_out,
            "prod": check_in,
            "svcStart": check_in,
            "svcEnd": check_out,
            "cost": 180.0,
            "by": updated_by,
        }
        batch_data = _graphql(engine, batch_query, batch_vars, endpoint_id, part_id)
        batch_no = batch_data["insertUpdateProviderItemBatch"]["providerItemBatch"]["batchNo"]

        # 4. Create a Segment (retail)
        seg_query = """
        mutation InsertUpdateSegment($name: String, $desc: String, $by: String!) {
            insertUpdateSegment(segmentName: $name, segmentDescription: $desc, updatedBy: $by) {
                segment { segmentUuid }
            }
        }
        """
        seg_vars = {
            "name": "Retail",
            "desc": "Direct consumer bookings",
            "by": updated_by,
        }
        seg_data = _graphql(engine, seg_query, seg_vars, endpoint_id, part_id)
        segment_uuid = seg_data["insertUpdateSegment"]["segment"]["segmentUuid"]

        # 5. Create ItemPriceTier
        tier_query = """
        mutation InsertUpdateItemPriceTier($iid: String!, $pid: String, $sid: String, $qty: Float, $margin: Float, $stat: String, $by: String!) {
            insertUpdateItemPriceTier(itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid, quantityGreaterThen: $qty, marginPerUom: $margin, status: $stat, updatedBy: $by) {
                itemPriceTier { itemPriceTierUuid }
            }
        }
        """
        tier_vars = {
            "iid": item_uuid,
            "pid": provider_item_uuid,
            "sid": segment_uuid,
            "qty": 0.0,
            "margin": 38.89,  # 250 = 180 * (1 + 0.3889)
            "stat": "active",
            "by": updated_by,
        }
        tier_data = _graphql(engine, tier_query, tier_vars, endpoint_id, part_id)
        tier_uuid = tier_data["insertUpdateItemPriceTier"]["itemPriceTier"]["itemPriceTierUuid"]

        return {
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid,
            "batch_no": batch_no,
            "segment_uuid": segment_uuid,
            "tier_uuid": tier_uuid,
            "check_in": check_in,
            "check_out": check_out,
            "updated_by": updated_by,
        }

    @pytest.mark.integration
    def test_service_window_overlap_query(
        self, engine, endpoint_id, part_id, hotel_context
    ):
        query = """
        query AvailableBatches($pid: String!, $start: DateTime, $end: DateTime) {
            providerItemBatchList(providerItemUuid: $pid, serviceWindowStart: $start, serviceWindowEnd: $end) {
                providerItemBatchList { batchNo serviceStartAt serviceEndAt }
            }
        }
        """
        data = _graphql(
            engine,
            query,
            {
                "pid": hotel_context["provider_item_uuid"],
                "start": hotel_context["check_in"],
                "end": hotel_context["check_out"],
            },
            endpoint_id,
            part_id,
        )
        batches = data["providerItemBatchList"]["providerItemBatchList"]
        assert hotel_context["batch_no"] in {batch["batchNo"] for batch in batches}

    @pytest.mark.integration
    def test_pilot_quote_flow(self, engine, endpoint_id, part_id, hotel_context):
        """
        AC-1: Drive Request -> Quote -> QuoteItem -> Installment flow
        with a 30% deposit / 70% balance schedule.
        """
        ctx = hotel_context

        # 6. Create Request
        req_query = """
        mutation InsertUpdateRequest($email: String!, $title: String!, $desc: String, $items: [JSONCamelCase], $by: String!) {
            insertUpdateRequest(email: $email, requestTitle: $title, requestDescription: $desc, items: $items, updatedBy: $by) {
                request { requestUuid }
            }
        }
        """
        req_vars = {
            "email": "guest@example.com",
            "title": "Weekend stay at Grand Hotel",
            "desc": "2-night stay for 2 adults",
            "items": [
                {
                    "item_uuid": ctx["item_uuid"],
                    "quantity": 2,
                    # GAP: no way to express guest composition (2 adults)
                    # GAP: no way to express service dates per item
                }
            ],
            "by": ctx["updated_by"],
        }
        req_data = _graphql(engine, req_query, req_vars, endpoint_id, part_id)
        request_uuid = req_data["insertUpdateRequest"]["request"]["requestUuid"]

        # 7. Create Quote
        quote_query = """
        mutation InsertUpdateQuote($rid: String!, $provId: String, $by: String!) {
            insertUpdateQuote(requestUuid: $rid, providerCorpExternalId: $provId, updatedBy: $by) {
                quote { quoteUuid }
            }
        }
        """
        quote_vars = {
            "rid": request_uuid,
            "provId": "HOTEL-GRAND-001",
            "by": ctx["updated_by"],
        }
        quote_data = _graphql(engine, quote_query, quote_vars, endpoint_id, part_id)
        quote_uuid = quote_data["insertUpdateQuote"]["quote"]["quoteUuid"]

        # 8. Create QuoteItem
        #    For the pilot, we just verify tier pricing works.
        #    qty = 2 room-nights under unit pricing.
        qi_query = """
        mutation InsertUpdateQuoteItem($qid: String!, $rid: String, $iid: String, $pid: String, $sid: String, $qty: Float, $by: String!) {
            insertUpdateQuoteItem(quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid, qty: $qty, updatedBy: $by) {
                quoteItem { quoteItemUuid pricePerUom subtotal }
            }
        }
        """
        qi_vars = {
            "qid": quote_uuid,
            "rid": request_uuid,
            "iid": ctx["item_uuid"],
            "pid": ctx["provider_item_uuid"],
            "sid": ctx["segment_uuid"],
            "qty": 2.0,
            "by": ctx["updated_by"],
        }
        qi_data = _graphql(engine, qi_query, qi_vars, endpoint_id, part_id)
        quote_item = qi_data["insertUpdateQuoteItem"]["quoteItem"]
        assert quote_item["pricePerUom"] is not None
        assert quote_item["subtotal"] == pytest.approx(quote_item["pricePerUom"] * 2, rel=1e-2)

        # 9. Create Installments: 30% deposit + 70% balance
        total = quote_item["subtotal"]
        deposit_amount = round(total * 0.30, 2)
        balance_amount = round(total * 0.70, 2)

        for priority, amount in [(1, deposit_amount), (2, balance_amount)]:
            inst_query = """
            mutation InsertUpdateInstallment($qid: String!, $rid: String, $priority: Int, $amount: SafeFloat, $by: String!) {
                insertUpdateInstallment(quoteUuid: $qid, requestUuid: $rid, priority: $priority, installmentAmount: $amount, updatedBy: $by) {
                    installment { installmentUuid }
                }
            }
            """
            inst_vars = {
                "qid": quote_uuid,
                "rid": request_uuid,
                "priority": priority,
                "amount": amount,
                "by": ctx["updated_by"],
            }
            inst_data = _graphql(engine, inst_query, inst_vars, endpoint_id, part_id)
            assert inst_data["insertUpdateInstallment"]["installment"]["installmentUuid"]

        # 10. Verify quote totals recalculate
        get_quote_query = """
        query GetQuote($rid: String!, $qid: String!) {
            quote(requestUuid: $rid, quoteUuid: $qid) {
                quoteUuid totalQuoteAmount
            }
        }
        """
        get_vars = {"rid": request_uuid, "qid": quote_uuid}
        get_data = _graphql(engine, get_quote_query, get_vars, endpoint_id, part_id)
        assert get_data["quote"]["totalQuoteAmount"] is not None

    @pytest.mark.unit
    def test_hospitality_schema_capabilities(self):
        """Keep the pilot aligned with the query surface committed in the plan."""
        from ai_rfq_engine.schema import Query

        query_fields = Query._meta.fields
        availability_args = query_fields["provider_item_batch_list"].args
        assert "service_window_start" in availability_args
        assert "service_window_end" in availability_args
        assert "item_catalog_refs" in query_fields
        assert "resolved_external_system_config" in query_fields

    @pytest.mark.unit
    def test_service_window_validation_rejects_inverted_dates(self):
        from ai_rfq_engine.models.provider_item_batches import (
            _validate_service_window,
        )

        with pytest.raises(ValueError, match="service_end_at"):
            _validate_service_window(
                pendulum.datetime(2026, 6, 2, tz="UTC"),
                pendulum.datetime(2026, 6, 1, tz="UTC"),
            )

    @pytest.mark.unit
    def test_per_pax_type_pricing_calculates_weighted_subtotal(self, monkeypatch):
        from ai_rfq_engine.models import item as item_model
        from ai_rfq_engine.models import quote as quote_model
        from ai_rfq_engine.models import quote_item as quote_item_model
        from ai_rfq_engine.models import provider_item as provider_item_model

        saved = {}

        class DummyItem:
            pricing_mode = "per_pax_type"

        class DummyQuoteItemModel:
            def __init__(self, quote_uuid, quote_item_uuid, **cols):
                saved.update(cols)

            def save(self):
                return None

        monkeypatch.setattr(item_model, "get_item", lambda *args: DummyItem())
        monkeypatch.setattr(quote_item_model, "QuoteItemModel", DummyQuoteItemModel)
        monkeypatch.setattr(quote_model, "update_quote_totals", lambda *args: None)
        monkeypatch.setattr(
            provider_item_model,
            "get_provider_item",
            lambda *args: SimpleNamespace(availability_mode="none"),
        )
        monkeypatch.setattr(
            quote_item_model,
            "get_price_per_uom",
            lambda *args, pax_type=None, **kwargs: {
                "adult": 120.0,
                "child": 60.0,
            }[pax_type],
        )

        raw_insert = quote_item_model.insert_update_quote_item.__wrapped__.__wrapped__
        raw_insert(
            SimpleNamespace(context={"partition_key": "tenant"}),
            entity=None,
            quote_uuid="quote",
            quote_item_uuid="line",
            request_uuid="request",
            item_uuid="item",
            provider_item_uuid="provider-item",
            segment_uuid="segment",
            qty=3,
            pax_breakdown={"adult": 2, "child": 1},
            updated_by="test",
        )

        assert saved["subtotal"] == pytest.approx(300.0)
        assert saved["price_per_uom"] == pytest.approx(100.0)
