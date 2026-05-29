#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed ``are-fx_rates`` for the AI RFQ engine.

The FX table is operator-facing: ``QuoteModel`` carries a locked numeric
``fxRate`` at quote time, so this table is not consulted on the hot path.
Seeding it produces realistic rate-management state for UI / audit /
analytics tests.

The script:

    1. Reads ``flight_products.json`` (if present) to learn which native
       currencies the existing inventory is denominated in. Logs a warning
       when something other than the configured base currencies appears.
    2. Generates rate records for every (source, target) currency pair
       across a date window (1 day by default; override for time-series
       testing of the ``currency_pair_date-index`` LSI).
    3. Optionally also writes reverse-direction pairs so a quote that
       picks either direction works without extra lookups.

Each rate has:

    * ``sourceCurrency`` / ``targetCurrency``  ISO codes
    * ``rate``                                  target units per 1 source
                                                (small ±2% jitter per day so
                                                multi-day runs look real)
    * ``currencyPairDate``                      composite key per the doc:
                                                ``"USD#EUR#2026-05-25"``
    * ``rateDate``                              ISO timestamp for that day
    * ``provider``                              Faker-generated bank/source
    * ``notes``                                 Faker-generated occasional
    * ``status``                                mostly ``active``

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_fx_rates.py

Configurable via env vars (defaults shown)::

    SEED_FX_BASE_CURRENCIES=USD                            # comma list
    SEED_FX_TARGET_CURRENCIES=EUR,GBP,JPY,CNY,AUD,CAD,SGD,HKD
    SEED_FX_NUM_DAYS=1                                     # backfill window
    SEED_FX_INCLUDE_REVERSE=1                              # also write target->source

Writes ``fx_rates.json`` next to this script.
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
logger = logging.getLogger("prepare_fx_rates")

fake = Faker()

UPDATED_BY = "prepare_fx_rates"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "fx_rates.json")
FLIGHTS_INPUT = os.path.join(os.path.dirname(__file__), "flight_products.json")

BASE_CURRENCIES = [
    c.strip().upper()
    for c in os.getenv("SEED_FX_BASE_CURRENCIES", "USD").split(",")
    if c.strip()
]
TARGET_CURRENCIES = [
    c.strip().upper()
    for c in os.getenv(
        "SEED_FX_TARGET_CURRENCIES", "EUR,GBP,JPY,CNY,AUD,CAD,SGD,HKD"
    ).split(",")
    if c.strip()
]
NUM_DAYS = max(1, int(os.getenv("SEED_FX_NUM_DAYS", "1")))
INCLUDE_REVERSE = os.getenv("SEED_FX_INCLUDE_REVERSE", "1") == "1"

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


# --- Reference rates (rough 2026 baselines; jittered per day) -------------- #
#
# Quoted as 1 USD = N target. Pairs not in this table fall back to a random
# realistic baseline so non-USD source currencies still seed something.

_USD_BASELINE = {
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 155.0,
    "CNY": 7.20,
    "AUD": 1.53,
    "CAD": 1.36,
    "SGD": 1.34,
    "HKD": 7.81,
    "CHF": 0.88,
    "INR": 83.50,
    "KRW": 1370.0,
    "MXN": 17.20,
    "BRL": 5.10,
    "ZAR": 18.60,
    "USD": 1.0,
}

_FX_PROVIDERS = [
    "Reuters Refinitiv",
    "Bloomberg FX",
    "OANDA",
    "ECB Reference",
    "XE Currency Data",
    "Wise Mid-Market",
    "Tenant Treasury Desk",
]


def baseline_rate(source: str, target: str) -> float:
    """Return a realistic 1-source-to-target rate."""
    if source == target:
        return 1.0
    src = _USD_BASELINE.get(source)
    tgt = _USD_BASELINE.get(target)
    if src and tgt:
        # 1 source = (1/src) USD = tgt/src target
        return tgt / src
    # Unknown pair — generate something coarse but stable-ish per pair.
    rng = random.Random(f"{source}#{target}")
    return round(rng.uniform(0.5, 150.0), 4)


def jittered_rate(source: str, target: str, day_offset: int) -> float:
    """Baseline ± up to 2% drift; deterministic per (pair, day) so reruns match."""
    base = baseline_rate(source, target)
    rng = random.Random(f"{source}#{target}#{day_offset}")
    drift = rng.uniform(-0.02, 0.02)
    rate = base * (1.0 + drift)
    # 6 sig figs for fiat pairs.
    return round(rate, 6)


def currency_pair_date_key(source: str, target: str, day: pendulum.Date) -> str:
    return f"{source}#{target}#{day.format('YYYY-MM-DD')}"


# --- GraphQL --------------------------------------------------------------- #


FX_RATE_MUTATION = """
mutation InsertUpdateFxRate(
    $src: String, $tgt: String, $rate: Float, $pair: String,
    $date: DateTime, $prov: String, $notes: String,
    $status: String, $by: String!
) {
    insertUpdateFxRate(
        sourceCurrency: $src, targetCurrency: $tgt, rate: $rate,
        currencyPairDate: $pair, rateDate: $date, provider: $prov,
        notes: $notes, status: $status, updatedBy: $by
    ) {
        fxRate { fxRateUuid }
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
            query=FX_RATE_MUTATION,
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


# --- Native currency discovery -------------------------------------------- #


def discover_native_currencies() -> set[str]:
    if not os.path.isfile(FLIGHTS_INPUT):
        return set()
    try:
        with open(FLIGHTS_INPUT, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to read %s: %s", FLIGHTS_INPUT, exc)
        return set()
    found: set[str] = set()
    for batch in data.get("provider_item_batches", []) or []:
        cur = batch.get("currency")
        if isinstance(cur, str) and cur:
            found.add(cur.upper())
    for tier in data.get("item_price_tiers", []) or []:
        cur = tier.get("currency")
        if isinstance(cur, str) and cur:
            found.add(cur.upper())
    return found


# --- Seeder ---------------------------------------------------------------- #


def _seed_one(
    engine: AIRFQEngine,
    *,
    source: str,
    target: str,
    rate: float,
    rate_day: pendulum.Date,
) -> dict | None:
    rate_dt = pendulum.datetime(
        rate_day.year, rate_day.month, rate_day.day, 16, 0, 0, tz="UTC"
    )
    pair_key = currency_pair_date_key(source, target, rate_day)
    notes = (
        fake.sentence(nb_words=8)
        if random.random() < 0.4
        else None
    )
    variables = {
        "src": source,
        "tgt": target,
        "rate": rate,
        "pair": pair_key,
        "date": rate_dt.to_iso8601_string(),
        "prov": random.choice(_FX_PROVIDERS),
        "notes": notes,
        "status": random.choices(["active", "inactive"], weights=[0.9, 0.1])[0],
        "by": UPDATED_BY,
    }
    data = run_mutation(engine, variables)
    if not data:
        return None
    uuid = data["insertUpdateFxRate"]["fxRate"]["fxRateUuid"]
    logger.info(
        "  %s -> %s @ %s on %s = %s  -> %s",
        source,
        target,
        pair_key,
        rate_dt.format("YYYY-MM-DD"),
        rate,
        uuid,
    )
    return {
        "fxRateUuid": uuid,
        "sourceCurrency": source,
        "targetCurrency": target,
        "rate": rate,
        "currencyPairDate": pair_key,
        "rateDate": rate_dt.to_iso8601_string(),
        "provider": variables["prov"],
        "notes": notes,
        "status": variables["status"],
    }


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    native_in_use = discover_native_currencies()
    if native_in_use:
        logger.info(
            "Detected native currencies in flight_products.json: %s",
            ", ".join(sorted(native_in_use)),
        )
        unseen = native_in_use - set(BASE_CURRENCIES)
        if unseen:
            logger.warning(
                "Native currencies %s are NOT in SEED_FX_BASE_CURRENCIES (%s); "
                "their rates will not be seeded. Override SEED_FX_BASE_CURRENCIES "
                "if you want them included.",
                ", ".join(sorted(unseen)),
                ", ".join(BASE_CURRENCIES),
            )

    today = pendulum.now("UTC").date()
    days = [today.subtract(days=offset) for offset in range(NUM_DAYS)]

    output: dict[str, Any] = {
        "baseCurrencies": BASE_CURRENCIES,
        "targetCurrencies": TARGET_CURRENCIES,
        "includeReverse": INCLUDE_REVERSE,
        "rates": [],
    }

    pair_count = (
        len(BASE_CURRENCIES) * len(TARGET_CURRENCIES) * (2 if INCLUDE_REVERSE else 1)
    )
    logger.info(
        "--- Seeding %d (pair x day) rates across %d days ---",
        pair_count * NUM_DAYS,
        NUM_DAYS,
    )

    for day_offset, rate_day in enumerate(days):
        for source in BASE_CURRENCIES:
            for target in TARGET_CURRENCIES:
                if source == target:
                    continue
                forward = jittered_rate(source, target, day_offset)
                record = _seed_one(
                    engine,
                    source=source,
                    target=target,
                    rate=forward,
                    rate_day=rate_day,
                )
                if record:
                    output["rates"].append(record)

                if INCLUDE_REVERSE:
                    # Reverse pair uses the strict inverse so a round-trip
                    # cancels — operators expect consistency.
                    reverse = round(1.0 / forward, 6) if forward else 0.0
                    record = _seed_one(
                        engine,
                        source=target,
                        target=source,
                        rate=reverse,
                        rate_day=rate_day,
                    )
                    if record:
                        output["rates"].append(record)

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info("Wrote: %d rate rows -> %s", len(output["rates"]), OUTPUT_FILE)


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
