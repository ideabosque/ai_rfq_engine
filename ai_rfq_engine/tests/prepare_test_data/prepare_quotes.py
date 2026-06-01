#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed ``are-quotes`` — supplier-specific quote shells per request.

Per ``TEST_DATA_PREPARATION.md §15`` a Quote answers a Request from a
specific supplier; multiple quotes can co-exist for one request (one per
airline competing for the booking). This script reads the requests you
just generated and writes 1–3 distinct-provider quote shells against
each.

Inputs:

    * ``requests.json``         — requestUuids to quote against, plus the
                                  pinned provider preferences (used to
                                  bias provider selection so at least
                                  one quote matches the customer's
                                  preferred airline when possible).
    * ``flight_products.json``  — the universe of airline corporate ids
                                  available; provides realistic FX
                                  scenarios via the ``currency`` field.

Each quote carries:

    * ``providerCorpExternalId`` — a real airline id from the seeded
                                   inventory (e.g. ``AIRLINE-AA``).
    * ``salesRepEmail``          — Faker-generated rep contact.
    * ``currency``               — supplier-native (``USD`` to match the
                                   flight catalog).
    * ``displayCurrency`` +
      ``fxRate`` +
      ``fxRateLockedAt``         — populated on ~40% of quotes so the
                                   FX conversion path is exercised.
    * ``shippingMethod`` /
      ``shippingAmount``         — usually unset for flight quotes;
                                   occasionally set to a small "ticket
                                   delivery" fee for variety.
    * ``status``                 — mostly ``initial``, some ``pending``.
    * ``notes``                  — Faker sentence.

Totals (``totalQuoteAmount`` etc.) stay at zero — they roll up from
``QuoteItem`` inserts via ``update_quote_totals``, which is the next
step in the pipeline.

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_quotes.py

Configurable via env vars (defaults shown)::

    SEED_QUOTE_MIN_PER_REQUEST=1
    SEED_QUOTE_MAX_PER_REQUEST=3
    SEED_QUOTE_FX_PROB=0.4              # chance display_currency + fx_rate are set
    SEED_QUOTE_SHIPPING_PROB=0.15       # chance a ticket-delivery fee is added

Writes ``quotes.json`` next to this script.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import random
import sys
from typing import Any

import pendulum
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

try:
    from faker import Faker
except ModuleNotFoundError:
    sys.exit(
        "The 'faker' package is not installed. Install it with: pip install faker"
    )


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prepare_quotes")

fake = Faker()

UPDATED_BY = "prepare_quotes"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "quotes.json")
REQUESTS_INPUT = os.path.join(os.path.dirname(__file__), "requests.json")
FLIGHTS_INPUT = os.path.join(os.path.dirname(__file__), "flight_products.json")
FX_INPUT = os.path.join(os.path.dirname(__file__), "fx_rates.json")

MIN_PER_REQUEST = max(1, int(os.getenv("SEED_QUOTE_MIN_PER_REQUEST", "1")))
MAX_PER_REQUEST = max(
    MIN_PER_REQUEST, int(os.getenv("SEED_QUOTE_MAX_PER_REQUEST", "3"))
)
FX_PROB = float(os.getenv("SEED_QUOTE_FX_PROB", "0.4"))
SHIPPING_PROB = float(os.getenv("SEED_QUOTE_SHIPPING_PROB", "0.15"))

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


# --- FX lookup from prepare_fx_rates.py output ----------------------------- #


def _load_fx_rates_by_pair() -> dict[tuple[str, str], list[dict]]:
    """
    Index ``fx_rates.json`` by (sourceCurrency, targetCurrency).

    Returns an empty dict (silently) when the file is missing — in that
    case ``_pick_display_currency`` returns None for every quote and the
    FX path is simply not exercised.
    """
    if not os.path.isfile(FX_INPUT):
        logger.warning(
            "%s not found; quotes will not apply FX. "
            "Run prepare_fx_rates.py first if you want display-currency "
            "conversion seeded.",
            FX_INPUT,
        )
        return {}
    try:
        with open(FX_INPUT, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to read %s: %s", FX_INPUT, exc)
        return {}

    by_pair: dict[tuple[str, str], list[dict]] = {}
    for row in data.get("rates") or []:
        src = row.get("sourceCurrency")
        tgt = row.get("targetCurrency")
        rate = row.get("rate")
        if src and tgt and isinstance(rate, (int, float)):
            by_pair.setdefault((src, tgt), []).append(row)
    return by_pair


def _pick_display_currency(
    native: str, fx_by_pair: dict[tuple[str, str], list[dict]]
) -> tuple[str, float, str | None] | None:
    """
    Choose a display currency and a locked rate sourced from the FX
    rates already in DynamoDB.

    Returns (target_currency, rate, rate_date_iso) or None when no
    matching (native, *) rate exists.
    """
    candidates = sorted({tgt for (src, tgt) in fx_by_pair if src == native})
    if not candidates:
        return None
    target = random.choice(candidates)
    rates = fx_by_pair.get((native, target)) or []
    if not rates:
        return None
    # Pick the most-recent rateDate so the locked rate matches the
    # operator's freshest published value.
    latest = max(rates, key=lambda r: r.get("rateDate") or "")
    rate = float(latest["rate"])
    return target, rate, latest.get("rateDate")


# --- GraphQL --------------------------------------------------------------- #


QUOTE_MUTATION = """
mutation InsertUpdateQuote(
    $rid: String!, $prov: String, $sales: String,
    $shipMethod: String, $shipAmt: SafeFloat,
    $cur: String, $disp: String, $fx: SafeFloat, $fxAt: DateTime,
    $notes: String, $status: String, $by: String!
) {
    insertUpdateQuote(
        requestUuid: $rid, providerCorpExternalId: $prov,
        salesRepEmail: $sales,
        shippingMethod: $shipMethod, shippingAmount: $shipAmt,
        currency: $cur, displayCurrency: $disp,
        fxRate: $fx, fxRateLockedAt: $fxAt,
        notes: $notes, status: $status, updatedBy: $by
    ) {
        quote { quoteUuid }
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
            query=QUOTE_MUTATION,
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


def _provider_corp_ids(flight_data: dict | None) -> dict[str, str]:
    """Map providerItemUuid -> providerCorpExternalId from flight_products.json."""
    mapping: dict[str, str] = {}
    for pi in (flight_data or {}).get("provider_items", []) or []:
        pi_uuid = pi.get("providerItemUuid")
        corp = pi.get("providerCorpExternalId")
        if pi_uuid and corp:
            mapping[pi_uuid] = corp
    return mapping


def _pinned_corp_ids_for_request(
    request: dict, pi_uuid_to_corp: dict[str, str]
) -> list[str]:
    """Collect providerCorpExternalIds the customer explicitly preferred."""
    corps: list[str] = []
    for it in request.get("items", []) or []:
        for pi in it.get("provider_items", []) or []:
            pi_uuid = pi.get("provider_item_uuid")
            corp = pi_uuid_to_corp.get(pi_uuid)
            if corp and corp not in corps:
                corps.append(corp)
    return corps


# --- Seeder ---------------------------------------------------------------- #


def _seed_one(
    engine: AIRFQEngine,
    *,
    request_uuid: str,
    provider_corp: str,
    native_currency: str,
    fx_by_pair: dict[tuple[str, str], list[dict]],
) -> dict | None:
    fx_target = (
        _pick_display_currency(native_currency, fx_by_pair)
        if random.random() < FX_PROB and fx_by_pair
        else None
    )
    if fx_target:
        display_currency, fx_rate, fx_rate_source_date = fx_target
    else:
        display_currency, fx_rate, fx_rate_source_date = (None, None, None)
    fx_locked_at = (
        pendulum.now("UTC").to_iso8601_string() if fx_target else None
    )

    shipping_method = None
    # QuoteModel.shipping_amount is non-null (default=0); explicit None breaks save.
    shipping_amount = 0.0
    if random.random() < SHIPPING_PROB:
        shipping_method = "ticket_delivery"
        shipping_amount = round(random.uniform(15.0, 45.0), 2)

    status = random.choices(["initial", "pending"], weights=[0.7, 0.3])[0]

    variables = {
        "rid": request_uuid,
        "prov": provider_corp,
        "sales": fake.email(),
        "shipMethod": shipping_method,
        "shipAmt": shipping_amount,
        "cur": native_currency,
        "disp": display_currency,
        "fx": fx_rate,
        "fxAt": fx_locked_at,
        "notes": fake.sentence(nb_words=12),
        "status": status,
        "by": UPDATED_BY,
    }
    data = run_mutation(engine, variables)
    if not data:
        return None
    quote_uuid = data["insertUpdateQuote"]["quote"]["quoteUuid"]
    fx_summary = (
        f"{native_currency}->{display_currency}@{fx_rate}"
        if fx_target
        else f"{native_currency} only"
    )
    logger.info(
        "  %s (status=%s, %s)  -> %s",
        provider_corp,
        status,
        fx_summary,
        quote_uuid,
    )
    return {
        "requestUuid": request_uuid,
        "quoteUuid": quote_uuid,
        "providerCorpExternalId": provider_corp,
        "salesRepEmail": variables["sales"],
        "shippingMethod": shipping_method,
        "shippingAmount": shipping_amount,
        "currency": native_currency,
        "displayCurrency": display_currency,
        "fxRate": fx_rate,
        "fxRateLockedAt": fx_locked_at,
        "fxRateSourceDate": fx_rate_source_date,
        "notes": variables["notes"],
        "status": status,
    }


def _pick_providers_for_request(
    request: dict,
    all_corps: list[str],
    pi_uuid_to_corp: dict[str, str],
    desired_count: int,
) -> list[str]:
    """
    Build a list of distinct provider_corp_external_ids to quote against
    a single request. Customer-preferred airlines (from item pins) come
    first, then random fill from the universe.
    """
    chosen: list[str] = list(_pinned_corp_ids_for_request(request, pi_uuid_to_corp))
    remaining = [c for c in all_corps if c not in chosen]
    random.shuffle(remaining)
    while len(chosen) < desired_count and remaining:
        chosen.append(remaining.pop())
    return chosen[:desired_count]


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    requests_data = _safe_load(REQUESTS_INPUT)
    requests = (requests_data or {}).get("requests") or []
    if not requests:
        raise RuntimeError(
            f"No requests in {REQUESTS_INPUT}. Run prepare_requests.py first."
        )

    flight_data = _safe_load(FLIGHTS_INPUT)
    pi_uuid_to_corp = _provider_corp_ids(flight_data)
    all_corps = sorted(set(pi_uuid_to_corp.values()))
    if not all_corps:
        raise RuntimeError(
            f"No providerCorpExternalId values in {FLIGHTS_INPUT}. "
            "Run prepare_flight_products.py first."
        )

    fx_by_pair = _load_fx_rates_by_pair()
    if fx_by_pair:
        pair_count = len(fx_by_pair)
        row_count = sum(len(v) for v in fx_by_pair.values())
        logger.info(
            "Loaded %d FX rate rows across %d distinct currency pair(s) from %s",
            row_count,
            pair_count,
            FX_INPUT,
        )

    output: dict[str, Any] = {"quotes": []}

    logger.info("--- Seeding quotes for %d requests ---", len(requests))
    for r_idx, request in enumerate(requests, start=1):
        request_uuid = request.get("requestUuid")
        if not request_uuid:
            continue
        desired = random.randint(MIN_PER_REQUEST, MAX_PER_REQUEST)
        providers = _pick_providers_for_request(
            request, all_corps, pi_uuid_to_corp, desired
        )
        if not providers:
            providers = [random.choice(all_corps)]

        logger.info(
            "[%d/%d] request=%s (%s) -> %d quote(s) from %s",
            r_idx,
            len(requests),
            request_uuid,
            request.get("scenario") or "?",
            len(providers),
            ", ".join(providers),
        )

        for corp in providers:
            record = _seed_one(
                engine,
                request_uuid=request_uuid,
                provider_corp=corp,
                native_currency="USD",
                fx_by_pair=fx_by_pair,
            )
            if record:
                output["quotes"].append(record)

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info("Wrote: %d quotes -> %s", len(output["quotes"]), OUTPUT_FILE)


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
