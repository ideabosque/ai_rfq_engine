#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed ``are-requests`` with flight-themed test data.

Generates customer inquiries that reference real items / provider items /
batches produced by ``prepare_flight_products.py``, addressed to emails
already attached to a segment via ``prepare_segments_and_contacts.py``.

Per ``TEST_DATA_PREPARATION.md §13`` and the validator in
``models/request.py::_validate_request_items`` the ``items`` list carries
free-form maps; the engine only enforces the existence of any
``item_uuid``, ``provider_item_uuid``, and ``(provider_item_uuid,
batch_no)`` keys it sees. Everything else (``pax_breakdown``,
``cabin_preference``, ...) passes through unchecked and gets stored
verbatim for downstream pricing.

Each request includes:

    * ``email``                — preferred from segments_and_contacts.json
    * ``request_title``        — scenario-based prose
    * ``request_description``  — same scenario, longer form
    * ``items[]``              — 1-3 flight items, some with
                                 provider_item_uuid + batch_no preference
    * ``billing_address``,
      ``shipping_address``     — Faker-generated US addresses
    * ``notes``                — Faker sentence
    * ``status``               — default ``initial``
    * ``expired_at``           — 30-90 days ahead

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_requests.py

Configurable via env vars::

    SEED_REQUEST_NUM_REQUESTS=5             # how many requests
    SEED_REQUEST_MAX_ITEMS=3                # max items per request
    SEED_REQUEST_PIN_PROVIDER_PROB=0.6      # chance a request pins a provider_item
    SEED_REQUEST_PIN_BATCH_PROB=0.4         # chance a pinned provider also pins a batch_no

Writes ``requests.json`` next to this script.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import random
import sys
from datetime import timedelta
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
logger = logging.getLogger("prepare_requests")

fake = Faker()

UPDATED_BY = "prepare_requests"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "requests.json")
SEGMENTS_INPUT = os.path.join(
    os.path.dirname(__file__), "segments_and_contacts.json"
)
FLIGHTS_INPUT = os.path.join(os.path.dirname(__file__), "flight_products.json")

NUM_REQUESTS = int(os.getenv("SEED_REQUEST_NUM_REQUESTS", "5"))
MAX_ITEMS = max(1, int(os.getenv("SEED_REQUEST_MAX_ITEMS", "3")))
PIN_PROVIDER_PROB = float(os.getenv("SEED_REQUEST_PIN_PROVIDER_PROB", "0.6"))
PIN_BATCH_PROB = float(os.getenv("SEED_REQUEST_PIN_BATCH_PROB", "0.4"))

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


# --- Scenario templates ---------------------------------------------------- #
#
# Each scenario shapes title / description / pax composition / item count so
# the seed data resembles real customer inquiries rather than uniform noise.

SCENARIOS = [
    {
        "name": "business_trip",
        "title_tpl": "Business trip {origin} to {destination} {month}",
        "desc_tpl": (
            "Business travel for {pax_count} attendee(s) attending offsite "
            "meetings in {destination}. Prefer Business or Premium Economy "
            "to allow productive flight time."
        ),
        "pax_count": (1, 3),
        "pax_types": ["adult"],
        "item_count": (1, 1),
        "cabin_preference": ["Business", "Premium Economy"],
    },
    {
        "name": "family_vacation",
        "title_tpl": "Family vacation to {destination} ({month})",
        "desc_tpl": (
            "Family of {pax_count} planning a leisure trip. Looking for "
            "Economy class fares with reasonable schedule flexibility."
        ),
        "pax_count": (3, 5),
        "pax_types": ["adult", "child"],
        "item_count": (1, 2),
        "cabin_preference": ["Economy"],
    },
    {
        "name": "group_corporate",
        "title_tpl": "Corporate group booking {origin} -> {destination}",
        "desc_tpl": (
            "Group booking for {pax_count} executives. Quote any cabin "
            "combination that hits the budget; will consider mixed cabins."
        ),
        "pax_count": (6, 12),
        "pax_types": ["adult"],
        "item_count": (1, 2),
        "cabin_preference": ["Business", "First"],
    },
    {
        "name": "multi_leg",
        "title_tpl": "Multi-city itinerary in {month}",
        "desc_tpl": (
            "Multi-leg itinerary for {pax_count} traveller(s). Quote each "
            "leg independently so we can pick the best provider per leg."
        ),
        "pax_count": (1, 4),
        "pax_types": ["adult"],
        "item_count": (2, 3),
        "cabin_preference": ["Economy", "Premium Economy"],
    },
    {
        "name": "honeymoon",
        "title_tpl": "Honeymoon to {destination}",
        "desc_tpl": (
            "Honeymoon trip for 2 adults. Open to splurge on the outbound "
            "in Business if pricing is reasonable."
        ),
        "pax_count": (2, 2),
        "pax_types": ["adult"],
        "item_count": (1, 2),
        "cabin_preference": ["Business", "Premium Economy", "Economy"],
    },
]


def _build_pax_breakdown(pax_count: int, types: list[str]) -> dict[str, int]:
    """Allocate pax_count across the allowed pax_types."""
    if not types:
        return {"adult": pax_count}
    if len(types) == 1:
        return {types[0]: pax_count}
    # Split between adults and children: at least 1 adult.
    adults = max(1, pax_count - random.randint(0, max(0, pax_count - 1)))
    children = pax_count - adults
    bd: dict[str, int] = {"adult": adults}
    if children > 0 and "child" in types:
        bd["child"] = children
    return bd


# --- Address helpers ------------------------------------------------------- #


def _build_address() -> dict:
    return {
        "name": fake.name(),
        "street": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "postal_code": fake.zipcode(),
        "country": "US",
        "phone": fake.phone_number(),
    }


# --- Item construction ----------------------------------------------------- #


def _pick_provider_for_item(
    item: dict, provider_items_by_item: dict[str, list[dict]]
) -> dict | None:
    siblings = provider_items_by_item.get(item.get("itemUuid"), [])
    if not siblings:
        return None
    return random.choice(siblings)


def _pick_batch_for_provider(
    provider_item_uuid: str, batches_by_provider: dict[str, list[dict]]
) -> dict | None:
    candidates = batches_by_provider.get(provider_item_uuid, [])
    if not candidates:
        return None
    return random.choice(candidates)


def _build_request_item(
    item: dict,
    *,
    pax_breakdown: dict[str, int],
    cabin_preference: str | None,
    provider_items_by_item: dict[str, list[dict]],
    batches_by_provider: dict[str, list[dict]],
) -> dict:
    qty = sum(pax_breakdown.values())
    entry: dict[str, Any] = {
        "item_uuid": item["itemUuid"],
        "quantity": qty,
        "pax_breakdown": pax_breakdown,
    }
    if cabin_preference:
        entry["cabin_preference"] = cabin_preference

    if random.random() < PIN_PROVIDER_PROB:
        provider_item = _pick_provider_for_item(item, provider_items_by_item)
        if provider_item:
            pi_entry: dict[str, Any] = {
                "provider_item_uuid": provider_item["providerItemUuid"],
                "quantity": qty,
            }
            if random.random() < PIN_BATCH_PROB:
                batch = _pick_batch_for_provider(
                    provider_item["providerItemUuid"], batches_by_provider
                )
                if batch:
                    pi_entry["batch_no"] = batch["batchNo"]
            entry["provider_items"] = [pi_entry]
    return entry


# --- GraphQL --------------------------------------------------------------- #


REQUEST_MUTATION = """
mutation InsertUpdateRequest(
    $email: String, $title: String, $desc: String,
    $billing: JSONCamelCase, $shipping: JSONCamelCase,
    $items: [JSONCamelCase], $notes: String,
    $status: String, $expired: DateTime, $by: String!
) {
    insertUpdateRequest(
        email: $email, requestTitle: $title, requestDescription: $desc,
        billingAddress: $billing, shippingAddress: $shipping,
        items: $items, notes: $notes, status: $status,
        expiredAt: $expired, updatedBy: $by
    ) {
        request { requestUuid }
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
            query=REQUEST_MUTATION,
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


def _index_provider_items(provider_items: list[dict]) -> dict[str, list[dict]]:
    by_item: dict[str, list[dict]] = {}
    for pi in provider_items:
        iid = pi.get("itemUuid")
        if iid:
            by_item.setdefault(iid, []).append(pi)
    return by_item


def _index_batches(batches: list[dict]) -> dict[str, list[dict]]:
    by_provider: dict[str, list[dict]] = {}
    for b in batches:
        pid = b.get("providerItemUuid")
        if pid:
            by_provider.setdefault(pid, []).append(b)
    return by_provider


# --- Generator ------------------------------------------------------------- #


def _scenario_route_hint(item: dict) -> tuple[str, str]:
    """Best-effort origin / destination strings for the title template."""
    external = item.get("itemExternalId") or ""
    parts = external.split("-")
    if len(parts) >= 3:
        return parts[1], parts[2]
    return "origin", "destination"


def _seed_one(
    engine: AIRFQEngine,
    *,
    email: str,
    items: list[dict],
    provider_items_by_item: dict[str, list[dict]],
    batches_by_provider: dict[str, list[dict]],
) -> dict | None:
    scenario = random.choice(SCENARIOS)
    lo, hi = scenario["item_count"]
    item_count = min(random.randint(lo, hi), MAX_ITEMS, len(items))
    chosen_items = random.sample(items, item_count)

    pax_lo, pax_hi = scenario["pax_count"]
    pax_count = random.randint(pax_lo, pax_hi)
    pax_breakdown = _build_pax_breakdown(pax_count, scenario["pax_types"])

    primary = chosen_items[0]
    origin, destination = _scenario_route_hint(primary)
    months = ["June", "July", "August", "September", "October", "November"]
    month = random.choice(months)
    title = scenario["title_tpl"].format(
        origin=origin, destination=destination, month=month
    )
    desc = scenario["desc_tpl"].format(
        pax_count=pax_count, origin=origin, destination=destination
    )

    cabin = (
        random.choice(scenario["cabin_preference"])
        if scenario["cabin_preference"]
        else None
    )

    item_payload = [
        _build_request_item(
            it,
            pax_breakdown=pax_breakdown,
            cabin_preference=cabin,
            provider_items_by_item=provider_items_by_item,
            batches_by_provider=batches_by_provider,
        )
        for it in chosen_items
    ]

    expired_at = (
        pendulum.now("UTC") + timedelta(days=random.randint(30, 90))
    ).to_iso8601_string()

    variables = {
        "email": email,
        "title": title,
        "desc": desc,
        "billing": _build_address(),
        "shipping": _build_address(),
        "items": item_payload,
        "notes": fake.sentence(nb_words=12),
        "status": "initial",
        "expired": expired_at,
        "by": UPDATED_BY,
    }
    data = run_mutation(engine, variables)
    if not data:
        return None
    request_uuid = data["insertUpdateRequest"]["request"]["requestUuid"]
    logger.info(
        "  %s: %s (%d items, %d pax, %s) -> %s",
        scenario["name"],
        title,
        len(item_payload),
        pax_count,
        cabin or "no cabin pref",
        request_uuid,
    )
    return {
        "requestUuid": request_uuid,
        "email": email,
        "scenario": scenario["name"],
        "requestTitle": title,
        "requestDescription": desc,
        "billingAddress": variables["billing"],
        "shippingAddress": variables["shipping"],
        "items": item_payload,
        "notes": variables["notes"],
        "status": "initial",
        "expiredAt": expired_at,
    }


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    flight_data = _safe_load(FLIGHTS_INPUT)
    items = (flight_data or {}).get("items") or []
    if not items:
        raise RuntimeError(
            f"No items in {FLIGHTS_INPUT}. Run prepare_flight_products.py first."
        )
    provider_items = (flight_data or {}).get("provider_items") or []
    batches = (flight_data or {}).get("provider_item_batches") or []
    provider_items_by_item = _index_provider_items(provider_items)
    batches_by_provider = _index_batches(batches)

    segments_data = _safe_load(SEGMENTS_INPUT)
    contact_emails = [
        c.get("email")
        for c in (segments_data or {}).get("segment_contacts", [])
        if c.get("email")
    ]
    if not contact_emails:
        logger.warning(
            "No emails in %s; falling back to Faker emails", SEGMENTS_INPUT
        )

    output: dict[str, Any] = {"requests": []}

    logger.info("--- Seeding %d requests ---", NUM_REQUESTS)
    for idx in range(NUM_REQUESTS):
        email = (
            random.choice(contact_emails) if contact_emails else fake.email()
        )
        logger.info("[%d/%d] %s", idx + 1, NUM_REQUESTS, email)
        record = _seed_one(
            engine,
            email=email,
            items=items,
            provider_items_by_item=provider_items_by_item,
            batches_by_provider=batches_by_provider,
        )
        if record:
            output["requests"].append(record)

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info("Wrote: %d requests -> %s", len(output["requests"]), OUTPUT_FILE)


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
