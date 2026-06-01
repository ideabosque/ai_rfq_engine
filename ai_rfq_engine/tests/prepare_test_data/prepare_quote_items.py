#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed ``are-quote_items`` for the quote shells produced by
``prepare_quotes.py``.

This is what makes ``QuoteModel.total_quote_amount``,
``total_quote_discount``, and ``final_total_quote_amount`` non-zero:
``insert_update_quote_item`` drives tier pricing, acquires availability
holds, applies FX conversion, and then rolls up the totals onto the
parent quote via ``update_quote_totals``.

Per ``TEST_DATA_PREPARATION.md §18`` each QuoteItem requires:

    * ``quoteUuid``, ``requestUuid``, ``itemUuid``, ``providerItemUuid``,
      ``segmentUuid``                — for tier pricing.
    * ``qty``                         — must equal the total of
                                        ``paxBreakdown`` for
                                        per_pax_type / occupancy.
    * ``paxBreakdown``                — required because the flight
                                        items use ``per_pax_type``.
    * ``batchNo``                     — required because the flight
                                        provider items use
                                        ``availabilityMode="require_hold"``
                                        and a service window must be
                                        resolvable; pinning the batch
                                        gives the engine its dates.
    * ``bundleUuid`` /
      ``bundleComponentUuid``         — when the request came from a
                                        persisted flight itinerary bundle.

The script consumes prior outputs:

    * ``quotes.json``           — list of quote shells (one per
                                  (request, provider) pair).
    * ``requests.json``         — to learn which items each request
                                  asked for, including pinned
                                  provider_item / batch preferences and
                                  pax composition.
    * ``flight_products.json``  — provider_items (filtered to the
                                  quote's airline corp), batches with
                                  capacity, segment_uuid for tier
                                  selection.

When a request asks for items that the quote's airline doesn't sell,
the corresponding line is skipped. Such quotes may end up empty (totals
remain 0) — a realistic outcome modelled after a non-competing
supplier.

A configurable fraction of inserted items receive a flat
``subtotalDiscount`` so the parent quote's
``total_quote_discount`` rolls up to non-zero.

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_quote_items.py

Configurable via env vars::

    SEED_QITEM_DISCOUNT_PROB=0.4         # fraction of items getting a discount
    SEED_QITEM_DISCOUNT_MIN=20.0         # discount range (display currency)
    SEED_QITEM_DISCOUNT_MAX=250.0
    SEED_QITEM_PROPAGATION_DELAY=0       # seconds to sleep before starting
                                         # (raise to 60-120 if tiers were just
                                         # written and the GSI hasn't caught up)

Writes ``quote_items.json`` next to this script.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import random
import sys
import time
from typing import Any

from dotenv import load_dotenv

TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(TESTS_DIR, ".env"))

BASE_DIR = os.getenv("base_dir") or os.path.abspath(
    os.path.join(TESTS_DIR, "..", "..")
)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "silvaengine_utility"))
sys.path.insert(1, os.path.join(BASE_DIR, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(BASE_DIR, "ai_rfq_engine"))

from ai_rfq_engine import AIRFQEngine  # noqa: E402
from silvaengine_utility.serializer import Serializer  # noqa: E402


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prepare_quote_items")


UPDATED_BY = "prepare_quote_items"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "quote_items.json")
QUOTES_INPUT = os.path.join(os.path.dirname(__file__), "quotes.json")
REQUESTS_INPUT = os.path.join(os.path.dirname(__file__), "requests.json")
FLIGHTS_INPUT = os.path.join(os.path.dirname(__file__), "flight_products.json")

DISCOUNT_PROB = float(os.getenv("SEED_QITEM_DISCOUNT_PROB", "0.4"))
DISCOUNT_MIN = float(os.getenv("SEED_QITEM_DISCOUNT_MIN", "20.0"))
DISCOUNT_MAX = float(os.getenv("SEED_QITEM_DISCOUNT_MAX", "250.0"))
PROPAGATION_DELAY = int(os.getenv("SEED_QITEM_PROPAGATION_DELAY", "0"))

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


# --- GraphQL --------------------------------------------------------------- #


QUOTE_ITEM_MUTATION = """
mutation InsertUpdateQuoteItem(
    $qid: String!, $rid: String, $iid: String, $pid: String, $sid: String,
    $bno: String, $qty: SafeFloat, $pax: JSONCamelCase,
    $bundleUuid: String, $bundleComponentUuid: String, $bundleLabel: String,
    $discount: SafeFloat, $by: String!
) {
    insertUpdateQuoteItem(
        quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid,
        providerItemUuid: $pid, segmentUuid: $sid, batchNo: $bno,
        qty: $qty, paxBreakdown: $pax,
        bundleUuid: $bundleUuid,
        bundleComponentUuid: $bundleComponentUuid,
        bundleLabel: $bundleLabel,
        subtotalDiscount: $discount,
        updatedBy: $by
    ) {
        quoteItem {
            quoteItemUuid
            pricePerUom qty
            subtotal subtotalDiscount finalSubtotal
            subtotalNative currency
            bundleUuid bundleComponentUuid
        }
    }
}
"""


# --- Engine helpers -------------------------------------------------------- #


def create_engine() -> AIRFQEngine:
    try:
        engine = AIRFQEngine(logger, **SETTING)
        setattr(engine, "__is_real__", True)
        return engine
    except Exception:
        logger.exception("Failed to initialize AIRFQEngine")
        raise


def run_mutation(engine: AIRFQEngine, variables: dict) -> dict | None:
    try:
        response = engine.ai_rfq_graphql(
            query=QUOTE_ITEM_MUTATION,
            variables=variables,
            endpoint_id=SETTING["endpoint_id"],
            part_id=SETTING["part_id"],
        )
    except Exception:
        logger.exception("GraphQL execution failed")
        return None

    parsed = (
        Serializer.json_loads(response)
        if isinstance(response, (str, bytes))
        else response
    )
    if isinstance(parsed, dict) and isinstance(parsed.get("body"), str):
        try:
            parsed = Serializer.json_loads(parsed["body"])
        except Exception:
            pass
    if not isinstance(parsed, dict):
        logger.error("Unexpected response: %s", parsed)
        return None
    if parsed.get("errors"):
        logger.error("GraphQL error: %s", Serializer.json_dumps(parsed["errors"]))
        return None
    return parsed.get("data", parsed)


# --- Inputs ---------------------------------------------------------------- #


def _safe_load(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


# --- Index helpers --------------------------------------------------------- #


def _index_provider_items_by_corp(provider_items: list[dict]) -> dict[tuple[str, str], dict]:
    """
    Build (provider_corp_external_id, item_uuid) -> provider_item dict.
    Quote items must reference a provider_item whose corp matches the
    parent quote's airline.
    """
    by_corp_item: dict[tuple[str, str], dict] = {}
    for pi in provider_items:
        corp = pi.get("providerCorpExternalId")
        iid = pi.get("itemUuid")
        if corp and iid:
            by_corp_item[(corp, iid)] = pi
    return by_corp_item


def _index_batches_by_provider(batches: list[dict]) -> dict[str, list[dict]]:
    by_provider: dict[str, list[dict]] = {}
    for b in batches:
        pid = b.get("providerItemUuid")
        if pid:
            by_provider.setdefault(pid, []).append(b)
    return by_provider


def _pick_batch(
    provider_item_uuid: str,
    pinned_batch_no: str | None,
    batches_by_provider: dict[str, list[dict]],
) -> dict | None:
    candidates = batches_by_provider.get(provider_item_uuid, [])
    if not candidates:
        return None
    if pinned_batch_no:
        for b in candidates:
            if b.get("batchNo") == pinned_batch_no:
                return b
    return random.choice(candidates)


# --- Seed ------------------------------------------------------------------ #


def _seed_one(
    engine: AIRFQEngine,
    *,
    quote: dict,
    request_item: dict,
    provider_item: dict,
    batch: dict,
    segment_uuid: str,
    bundle_uuid: str | None,
    bundle_label: str | None,
) -> dict | None:
    pax_breakdown = request_item.get("pax_breakdown") or {"adult": int(request_item.get("quantity") or 1)}
    qty = sum(int(v) for v in pax_breakdown.values())

    discount = None
    if random.random() < DISCOUNT_PROB:
        discount = round(random.uniform(DISCOUNT_MIN, DISCOUNT_MAX), 2)

    bundle_component_uuid = request_item.get("bundle_component_uuid")

    variables = {
        "qid": quote["quoteUuid"],
        "rid": quote["requestUuid"],
        "iid": request_item["item_uuid"],
        "pid": provider_item["providerItemUuid"],
        "sid": segment_uuid,
        "bno": batch.get("batchNo"),
        "qty": float(qty),
        "pax": pax_breakdown,
        "bundleUuid": bundle_uuid,
        "bundleComponentUuid": bundle_component_uuid,
        "bundleLabel": bundle_label,
        "discount": discount,
        "by": UPDATED_BY,
    }
    data = run_mutation(engine, variables)
    if not data:
        return None
    qi = data["insertUpdateQuoteItem"]["quoteItem"]
    logger.info(
        "    -> %s qty=%s pricePerUom=%s subtotal=%s discount=%s final=%s (native=%s %s)",
        qi.get("quoteItemUuid"),
        qi.get("qty"),
        qi.get("pricePerUom"),
        qi.get("subtotal"),
        qi.get("subtotalDiscount"),
        qi.get("finalSubtotal"),
        qi.get("subtotalNative"),
        qi.get("currency"),
    )
    return {
        "quoteUuid": quote["quoteUuid"],
        "quoteItemUuid": qi["quoteItemUuid"],
        "requestUuid": quote["requestUuid"],
        "itemUuid": request_item["item_uuid"],
        "providerItemUuid": provider_item["providerItemUuid"],
        "segmentUuid": segment_uuid,
        "batchNo": batch.get("batchNo"),
        "qty": qi.get("qty"),
        "paxBreakdown": pax_breakdown,
        "pricePerUom": qi.get("pricePerUom"),
        "subtotal": qi.get("subtotal"),
        "subtotalDiscount": qi.get("subtotalDiscount"),
        "finalSubtotal": qi.get("finalSubtotal"),
        "subtotalNative": qi.get("subtotalNative"),
        "currency": qi.get("currency"),
        "bundleUuid": bundle_uuid,
        "bundleComponentUuid": qi.get("bundleComponentUuid")
        or bundle_component_uuid,
        "bundleLabel": bundle_label,
    }


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    quotes_data = _safe_load(QUOTES_INPUT) or {}
    quotes = quotes_data.get("quotes") or []
    if not quotes:
        raise RuntimeError(
            f"No quotes in {QUOTES_INPUT}. Run prepare_quotes.py first."
        )

    requests_data = _safe_load(REQUESTS_INPUT) or {}
    requests_by_uuid = {
        r["requestUuid"]: r
        for r in (requests_data.get("requests") or [])
        if r.get("requestUuid")
    }
    if not requests_by_uuid:
        raise RuntimeError(
            f"No requests in {REQUESTS_INPUT}. Run prepare_requests.py first."
        )

    flight_data = _safe_load(FLIGHTS_INPUT) or {}
    segment_uuid = flight_data.get("segmentUuid")
    if not segment_uuid:
        raise RuntimeError(
            f"No segmentUuid in {FLIGHTS_INPUT}. "
            "prepare_flight_products.py must run first."
        )
    pi_by_corp_item = _index_provider_items_by_corp(
        flight_data.get("provider_items") or []
    )
    batches_by_provider = _index_batches_by_provider(
        flight_data.get("provider_item_batches") or []
    )

    if PROPAGATION_DELAY > 0:
        logger.info(
            "Sleeping %ds for DynamoDB GSI propagation before inserting quote items...",
            PROPAGATION_DELAY,
        )
        time.sleep(PROPAGATION_DELAY)

    output: dict[str, Any] = {"quote_items": [], "empty_quotes": [], "skipped": []}

    logger.info("--- Seeding quote items for %d quotes ---", len(quotes))
    for q_idx, quote in enumerate(quotes, start=1):
        request = requests_by_uuid.get(quote.get("requestUuid"))
        if not request:
            logger.warning(
                "  [%d/%d] no source request for quote %s; skipping",
                q_idx,
                len(quotes),
                quote.get("quoteUuid"),
            )
            continue

        request_items = request.get("items") or []
        corp = quote.get("providerCorpExternalId")
        logger.info(
            "[%d/%d] quote=%s corp=%s items_in_request=%d",
            q_idx,
            len(quotes),
            quote.get("quoteUuid"),
            corp,
            len(request_items),
        )

        # Package grouping comes from prepare_requests.py, which references
        # persisted Bundle/BundleComponent rows created by prepare_flight_products.py.
        bundle_uuid = request.get("bundleUuid")
        bundle_label = (
            request.get("bundleName")
            or request.get("requestTitle")
            or "Itinerary"
        )
        if not bundle_uuid:
            bundle_label = None

        seeded = 0
        for ri in request_items:
            item_uuid = ri.get("item_uuid")
            if not item_uuid:
                continue

            provider_item = pi_by_corp_item.get((corp, item_uuid))
            if not provider_item:
                output["skipped"].append(
                    {
                        "quoteUuid": quote.get("quoteUuid"),
                        "providerCorpExternalId": corp,
                        "itemUuid": item_uuid,
                        "reason": "provider_corp_does_not_sell_this_item",
                    }
                )
                continue

            pinned_batch_no = None
            for pi in ri.get("provider_items") or []:
                if pi.get("provider_item_uuid") == provider_item["providerItemUuid"]:
                    pinned_batch_no = pi.get("batch_no")
                    break

            batch = _pick_batch(
                provider_item["providerItemUuid"],
                pinned_batch_no,
                batches_by_provider,
            )
            if not batch:
                output["skipped"].append(
                    {
                        "quoteUuid": quote.get("quoteUuid"),
                        "providerItemUuid": provider_item["providerItemUuid"],
                        "itemUuid": item_uuid,
                        "reason": "no_batch_available",
                    }
                )
                continue

            record = _seed_one(
                engine,
                quote=quote,
                request_item=ri,
                provider_item=provider_item,
                batch=batch,
                segment_uuid=segment_uuid,
                bundle_uuid=bundle_uuid,
                bundle_label=bundle_label[:80] if bundle_label else None,
            )
            if record:
                output["quote_items"].append(record)
                seeded += 1

        if seeded == 0:
            output["empty_quotes"].append(
                {
                    "quoteUuid": quote.get("quoteUuid"),
                    "providerCorpExternalId": corp,
                }
            )

    return output


def _json_default(obj):
    """``json.dump`` default for Decimal values returned by DynamoDB-backed fields."""
    import decimal

    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=_json_default)
    logger.info(
        "Wrote: %d quote_items, %d empty quotes, %d skipped lines -> %s",
        len(output["quote_items"]),
        len(output["empty_quotes"]),
        len(output["skipped"]),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
