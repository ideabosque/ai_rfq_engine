#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed flight-themed product data for the AI RFQ engine.

Looks up an existing ``Segment`` (does NOT create one — run
``prepare_segments_and_contacts.py`` first if you have none) and then
generates a coherent flight catalog across five tables:

    Item                 ── a flight cabin product (e.g. "Flight JFK->LAX Economy")
    ProviderItem         ── an airline's offering of that product
    CancellationPolicy   ── refund tiers per ticket class
    ProviderItemBatch    ── a specific flight number on a specific date
                              with departure/arrival as service window and
                              seat count as availability_qty
    ItemPriceTier        ── adult / child / infant prices for the segment

The data is generated with Faker for flavour, but flight-specific structure
(IATA codes, cabin classes, flight numbers) is curated locally because
Faker does not provide flight data.

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_flight_products.py

Counts and selection are configurable via env vars (or edit the constants):

    SEED_FLIGHT_NUM_ROUTES=8        # number of Item rows
    SEED_FLIGHT_BATCHES_PER_ROUTE=3 # ProviderItemBatch rows per route
    SEED_FLIGHT_SEGMENT_UUID=...    # pin a specific segment instead of the
                                    # first one returned by segmentList

Writes results to ``flight_products.json`` next to this script.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import random
import sys
from datetime import timedelta

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
logger = logging.getLogger("prepare_flight_products")

fake = Faker()

UPDATED_BY = "prepare_flight_products"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "flight_products.json")

NUM_ROUTES = int(os.getenv("SEED_FLIGHT_NUM_ROUTES", "5"))
BATCHES_PER_ROUTE = int(os.getenv("SEED_FLIGHT_BATCHES_PER_ROUTE", "2"))
PINNED_SEGMENT_UUID = os.getenv("SEED_FLIGHT_SEGMENT_UUID")

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


# --- Flight-domain reference data ------------------------------------------ #

AIRPORTS = [
    ("JFK", "New York"),
    ("LAX", "Los Angeles"),
    ("ORD", "Chicago"),
    ("SFO", "San Francisco"),
    ("ATL", "Atlanta"),
    ("DFW", "Dallas"),
    ("SEA", "Seattle"),
    ("MIA", "Miami"),
    ("BOS", "Boston"),
    ("LHR", "London"),
    ("CDG", "Paris"),
    ("NRT", "Tokyo"),
    ("SIN", "Singapore"),
    ("HKG", "Hong Kong"),
    ("SYD", "Sydney"),
]

AIRLINES = [
    ("AA", "American Airlines"),
    ("DL", "Delta Air Lines"),
    ("UA", "United Airlines"),
    ("BA", "British Airways"),
    ("AF", "Air France"),
    ("LH", "Lufthansa"),
    ("SQ", "Singapore Airlines"),
    ("CX", "Cathay Pacific"),
    ("JL", "Japan Airlines"),
    ("QF", "Qantas"),
]

CABIN_CLASSES = [
    {"name": "Economy", "base_price": 250.0, "multiplier": 1.0},
    {"name": "Premium Economy", "base_price": 450.0, "multiplier": 1.4},
    {"name": "Business", "base_price": 1800.0, "multiplier": 2.5},
    {"name": "First", "base_price": 4500.0, "multiplier": 4.0},
]

PAX_TYPES = [
    ("adult", 1.00),
    ("child", 0.75),
    ("infant", 0.10),
]


# --- GraphQL ---------------------------------------------------------------- #


SEGMENT_LIST_QUERY = """
query SegmentList($limit: Int, $offset: Int) {
    segmentList(limit: $limit, pageNumber: $offset) {
        segmentList { segmentUuid segmentName }
        total
    }
}
"""

ITEM_MUTATION = """
mutation InsertUpdateItem(
    $type: String, $name: String, $desc: String,
    $mode: String, $uom: String, $extId: String, $by: String!
) {
    insertUpdateItem(
        itemType: $type, itemName: $name, itemDescription: $desc,
        pricingMode: $mode, uom: $uom, itemExternalId: $extId,
        updatedBy: $by
    ) {
        item { itemUuid }
    }
}
"""

PROVIDER_ITEM_MUTATION = """
mutation InsertUpdateProviderItem(
    $iid: String!, $extId: String, $providerExt: String,
    $price: SafeFloat, $mode: String, $spec: JSONCamelCase, $by: String!
) {
    insertUpdateProviderItem(
        itemUuid: $iid,
        providerCorpExternalId: $extId,
        providerItemExternalId: $providerExt,
        basePricePerUom: $price,
        availabilityMode: $mode,
        itemSpec: $spec,
        updatedBy: $by
    ) {
        providerItem { providerItemUuid }
    }
}
"""

CANCELLATION_POLICY_MUTATION = """
mutation InsertUpdateCancellationPolicy(
    $label: String, $desc: String, $tiers: JSONCamelCase,
    $provider: String, $by: String!
) {
    insertUpdateCancellationPolicy(
        label: $label, description: $desc, tiers: $tiers,
        providerItemUuid: $provider, updatedBy: $by
    ) {
        cancellationPolicy { policyUuid }
    }
}
"""

PROVIDER_ITEM_BATCH_MUTATION = """
mutation InsertUpdateProviderItemBatch(
    $pid: String!, $iid: String!, $bno: String!,
    $prod: DateTime, $exp: DateTime,
    $start: DateTime, $end: DateTime,
    $cost: SafeFloat, $freight: SafeFloat, $addl: SafeFloat,
    $qty: SafeFloat, $cur: String, $polUuid: String, $by: String!
) {
    insertUpdateProviderItemBatch(
        providerItemUuid: $pid, itemUuid: $iid, batchNo: $bno,
        producedAt: $prod, expiredAt: $exp,
        serviceStartAt: $start, serviceEndAt: $end,
        costPerUom: $cost, freightCostPerUom: $freight, additionalCostPerUom: $addl,
        availabilityQty: $qty, inStock: true,
        currency: $cur, cancellationPolicyUuid: $polUuid,
        updatedBy: $by
    ) {
        providerItemBatch { batchNo availabilityQty }
    }
}
"""

ITEM_PRICE_TIER_MUTATION = """
mutation InsertUpdateItemPriceTier(
    $iid: String!, $pid: String, $sid: String,
    $qty: SafeFloat, $price: SafeFloat, $pax: String, $cur: String,
    $stat: String, $by: String!
) {
    insertUpdateItemPriceTier(
        itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid,
        quantityGreaterThen: $qty, pricePerUom: $price, paxType: $pax,
        currency: $cur, status: $stat, updatedBy: $by
    ) {
        itemPriceTier { itemPriceTierUuid }
    }
}
"""


# --- Engine helpers --------------------------------------------------------- #


def create_engine() -> AIRFQEngine:
    try:
        engine = AIRFQEngine(logger, **SETTING)
        setattr(engine, "__is_real__", True)
        return engine
    except Exception:
        logger.exception("Failed to initialize AIRFQEngine")
        raise


def run_graphql(engine: AIRFQEngine, query: str, variables: dict) -> dict | None:
    try:
        response = engine.ai_rfq_graphql(
            query=query,
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


# --- Segment lookup --------------------------------------------------------- #


def lookup_segment_uuid(engine: AIRFQEngine) -> str:
    if PINNED_SEGMENT_UUID:
        logger.info("Using pinned segment %s from SEED_FLIGHT_SEGMENT_UUID", PINNED_SEGMENT_UUID)
        return PINNED_SEGMENT_UUID

    data = run_graphql(engine, SEGMENT_LIST_QUERY, {"limit": 10, "offset": 1})
    if not data:
        raise RuntimeError("Could not query segmentList — fix segment table first")
    segments = (data.get("segmentList") or {}).get("segmentList") or []
    if not segments:
        raise RuntimeError(
            "No segments found. Run prepare_segments_and_contacts.py first, "
            "or pin a uuid via SEED_FLIGHT_SEGMENT_UUID env var."
        )
    segment = segments[0]
    logger.info(
        "Using existing segment: %s (%s)",
        segment.get("segmentName"),
        segment.get("segmentUuid"),
    )
    return segment["segmentUuid"]


# --- Flight data generators ------------------------------------------------- #


def pick_route() -> tuple[tuple[str, str], tuple[str, str]]:
    origin, destination = random.sample(AIRPORTS, 2)
    return origin, destination


def pick_cabin() -> dict:
    return random.choice(CABIN_CLASSES)


def pick_airline() -> tuple[str, str]:
    return random.choice(AIRLINES)


def flight_number(airline_code: str) -> str:
    return f"{airline_code}{random.randint(100, 9999)}"


def flight_duration_hours(origin_code: str, destination_code: str) -> float:
    # crude domestic/international heuristic
    international = {origin_code, destination_code} & {
        "LHR", "CDG", "NRT", "SIN", "HKG", "SYD"
    }
    if international:
        return random.uniform(7.0, 14.0)
    return random.uniform(1.5, 6.0)


# --- Seeders ---------------------------------------------------------------- #


def seed_cancellation_policy(
    engine: AIRFQEngine, cabin_name: str
) -> dict | None:
    label = f"{cabin_name} Fare Cancellation"
    description = fake.sentence(nb_words=12)
    if cabin_name in {"Business", "First"}:
        tiers = {
            "tiers": [
                {"hours_before_departure_gte": 24, "refund_pct": 1.0},
                {"hours_before_departure_gte": 2, "refund_pct": 0.5},
                {"hours_before_departure_gte": 0, "refund_pct": 0.0},
            ]
        }
    else:
        tiers = {
            "tiers": [
                {"hours_before_departure_gte": 168, "refund_pct": 1.0},  # 7 days
                {"hours_before_departure_gte": 24, "refund_pct": 0.5},
                {"hours_before_departure_gte": 0, "refund_pct": 0.0},
            ]
        }

    data = run_graphql(
        engine,
        CANCELLATION_POLICY_MUTATION,
        {
            "label": label,
            "desc": description,
            "tiers": tiers,
            "provider": None,
            "by": UPDATED_BY,
        },
    )
    if not data:
        return None
    policy_uuid = data["insertUpdateCancellationPolicy"]["cancellationPolicy"][
        "policyUuid"
    ]
    logger.info("  cancellation policy: %s (%s)", label, policy_uuid)
    return {
        "policyUuid": policy_uuid,
        "label": label,
        "description": description,
        "tiers": tiers,
    }


def seed_item(engine: AIRFQEngine, route: tuple, cabin: dict) -> dict | None:
    (orig_code, orig_city), (dest_code, dest_city) = route
    name = f"Flight {orig_code}->{dest_code} {cabin['name']}"
    description = (
        f"{cabin['name']} class non-stop service from {orig_city} ({orig_code}) "
        f"to {dest_city} ({dest_code})."
    )
    external_id = f"FLIGHT-{orig_code}-{dest_code}-{cabin['name'][:3].upper()}"

    data = run_graphql(
        engine,
        ITEM_MUTATION,
        {
            "type": "flight",
            "name": name,
            "desc": description,
            "mode": "per_pax_type",
            "uom": "seat",
            "extId": external_id,
            "by": UPDATED_BY,
        },
    )
    if not data:
        return None
    item_uuid = data["insertUpdateItem"]["item"]["itemUuid"]
    logger.info("  item: %s -> %s", name, item_uuid)
    return {
        "itemUuid": item_uuid,
        "itemType": "flight",
        "itemName": name,
        "itemDescription": description,
        "pricingMode": "per_pax_type",
        "uom": "seat",
        "itemExternalId": external_id,
    }


def seed_provider_item(
    engine: AIRFQEngine,
    item_uuid: str,
    airline: tuple[str, str],
    cabin: dict,
    route: tuple,
) -> dict | None:
    airline_code, airline_name = airline
    (orig_code, _), (dest_code, _) = route
    base_price = cabin["base_price"]
    item_spec = {
        "airline_code": airline_code,
        "airline_name": airline_name,
        "cabin_class": cabin["name"],
        "origin_iata": orig_code,
        "destination_iata": dest_code,
        "baggage_allowance_kg": 23 if cabin["name"] == "Economy" else 32,
        "meal_included": cabin["name"] != "Economy",
    }
    provider_item_external = f"{airline_code}-{orig_code}-{dest_code}-{cabin['name'][:3].upper()}"
    provider_corp = f"AIRLINE-{airline_code}"

    data = run_graphql(
        engine,
        PROVIDER_ITEM_MUTATION,
        {
            "iid": item_uuid,
            "extId": provider_corp,
            "providerExt": provider_item_external,
            "price": base_price,
            "mode": "require_hold",
            "spec": item_spec,
            "by": UPDATED_BY,
        },
    )
    if not data:
        return None
    provider_item_uuid = data["insertUpdateProviderItem"]["providerItem"][
        "providerItemUuid"
    ]
    logger.info(
        "  provider item: %s %s -> %s",
        airline_name,
        cabin["name"],
        provider_item_uuid,
    )
    return {
        "providerItemUuid": provider_item_uuid,
        "itemUuid": item_uuid,
        "providerCorpExternalId": provider_corp,
        "providerItemExternalId": provider_item_external,
        "basePricePerUom": base_price,
        "availabilityMode": "require_hold",
        "itemSpec": item_spec,
    }


def seed_batch(
    engine: AIRFQEngine,
    item_uuid: str,
    provider_item_uuid: str,
    airline: tuple[str, str],
    route: tuple,
    cabin: dict,
    policy_uuid: str,
    days_ahead: int,
) -> dict | None:
    airline_code, _ = airline
    (orig_code, _), (dest_code, _) = route
    flight_no = flight_number(airline_code)
    departure = pendulum.now("UTC").add(days=days_ahead).at(
        random.randint(6, 22), random.choice([0, 15, 30, 45])
    )
    duration_h = flight_duration_hours(orig_code, dest_code)
    arrival = departure + timedelta(hours=duration_h)
    batch_no = f"{flight_no}-{departure.format('YYYYMMDD')}"

    capacity_by_cabin = {
        "Economy": random.randint(120, 240),
        "Premium Economy": random.randint(30, 60),
        "Business": random.randint(20, 40),
        "First": random.randint(4, 12),
    }
    availability_qty = capacity_by_cabin.get(cabin["name"], 100)
    cost = round(cabin["base_price"] * 0.55, 2)

    data = run_graphql(
        engine,
        PROVIDER_ITEM_BATCH_MUTATION,
        {
            "pid": provider_item_uuid,
            "iid": item_uuid,
            "bno": batch_no,
            "prod": departure.subtract(days=180).to_iso8601_string(),
            "exp": arrival.to_iso8601_string(),
            "start": departure.to_iso8601_string(),
            "end": arrival.to_iso8601_string(),
            "cost": cost,
            "freight": 0.0,
            "addl": round(random.uniform(15.0, 60.0), 2),
            "qty": float(availability_qty),
            "cur": "USD",
            "polUuid": policy_uuid,
            "by": UPDATED_BY,
        },
    )
    if not data:
        return None
    logger.info(
        "  batch: %s %s seats=%d depart=%s",
        batch_no,
        cabin["name"],
        availability_qty,
        departure.to_iso8601_string(),
    )
    return {
        "providerItemUuid": provider_item_uuid,
        "batchNo": batch_no,
        "itemUuid": item_uuid,
        "flightNumber": flight_no,
        "serviceStartAt": departure.to_iso8601_string(),
        "serviceEndAt": arrival.to_iso8601_string(),
        "availabilityQty": availability_qty,
        "currency": "USD",
        "cancellationPolicyUuid": policy_uuid,
    }


def seed_price_tiers(
    engine: AIRFQEngine,
    item_uuid: str,
    provider_item_uuid: str,
    segment_uuid: str,
    cabin: dict,
) -> list[dict]:
    tiers = []
    base = cabin["base_price"]
    for pax_type, multiplier in PAX_TYPES:
        price = round(base * multiplier, 2)
        data = run_graphql(
            engine,
            ITEM_PRICE_TIER_MUTATION,
            {
                "iid": item_uuid,
                "pid": provider_item_uuid,
                "sid": segment_uuid,
                "qty": 0.0,
                "price": price,
                "pax": pax_type,
                "cur": "USD",
                "stat": "active",
                "by": UPDATED_BY,
            },
        )
        if not data:
            continue
        tier_uuid = data["insertUpdateItemPriceTier"]["itemPriceTier"][
            "itemPriceTierUuid"
        ]
        logger.info("  tier: %s %s @ $%.2f -> %s", cabin["name"], pax_type, price, tier_uuid)
        tiers.append(
            {
                "itemPriceTierUuid": tier_uuid,
                "itemUuid": item_uuid,
                "providerItemUuid": provider_item_uuid,
                "segmentUuid": segment_uuid,
                "paxType": pax_type,
                "pricePerUom": price,
                "currency": "USD",
                "status": "active",
            }
        )
    return tiers


# --- Orchestrator ----------------------------------------------------------- #


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    segment_uuid = lookup_segment_uuid(engine)

    output: dict = {
        "segmentUuid": segment_uuid,
        "cancellation_policies": [],
        "items": [],
        "provider_items": [],
        "provider_item_batches": [],
        "item_price_tiers": [],
    }

    logger.info(
        "--- Seeding %d flight routes, %d batches per route ---",
        NUM_ROUTES,
        BATCHES_PER_ROUTE,
    )

    # One cancellation policy per distinct cabin class encountered.
    policy_by_cabin: dict[str, str] = {}

    for route_idx in range(NUM_ROUTES):
        route = pick_route()
        cabin = pick_cabin()
        airline = pick_airline()
        (orig_code, _), (dest_code, _) = route
        logger.info(
            "[%d/%d] %s %s %s->%s",
            route_idx + 1,
            NUM_ROUTES,
            airline[1],
            cabin["name"],
            orig_code,
            dest_code,
        )

        if cabin["name"] not in policy_by_cabin:
            policy = seed_cancellation_policy(engine, cabin["name"])
            if not policy:
                continue
            policy_by_cabin[cabin["name"]] = policy["policyUuid"]
            output["cancellation_policies"].append(policy)
        policy_uuid = policy_by_cabin[cabin["name"]]

        item = seed_item(engine, route, cabin)
        if not item:
            continue
        output["items"].append(item)

        provider_item = seed_provider_item(
            engine, item["itemUuid"], airline, cabin, route
        )
        if not provider_item:
            continue
        output["provider_items"].append(provider_item)

        for n in range(BATCHES_PER_ROUTE):
            batch = seed_batch(
                engine,
                item["itemUuid"],
                provider_item["providerItemUuid"],
                airline,
                route,
                cabin,
                policy_uuid,
                days_ahead=random.randint(14, 120),
            )
            if batch:
                output["provider_item_batches"].append(batch)

        tiers = seed_price_tiers(
            engine,
            item["itemUuid"],
            provider_item["providerItemUuid"],
            segment_uuid,
            cabin,
        )
        output["item_price_tiers"].extend(tiers)

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info(
        "Wrote: %d items, %d provider_items, %d batches, %d tiers, %d policies -> %s",
        len(output["items"]),
        len(output["provider_items"]),
        len(output["provider_item_batches"]),
        len(output["item_price_tiers"]),
        len(output["cancellation_policies"]),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
