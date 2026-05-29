#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Seed ``are-discount_prompts`` for the AI RFQ engine.

Generates one or more discount-prompt rules at each scope from
``TEST_DATA_PREPARATION.md §12``:

    * ``global``        — applies tenant-wide; no tags
    * ``segment``       — tagged with a real ``segmentUuid``
    * ``item``          — tagged with a real ``itemUuid``
    * ``provider_item`` — tagged with a real ``providerItemUuid``

Reads previously-generated output to scope to real data:

    * ``segments_and_contacts.json`` (for segment scope)
    * ``flight_products.json``        (for item + provider_item scopes)

If a JSON is missing the corresponding scoped prompts are skipped — the
``global`` block still runs, so this script is usable in isolation.

Every ``discount_rules`` ladder is generated to pass the validator in
``models.discount_prompt.validate_and_normalize_discount_rules``:
contiguous brackets starting at 0, last tier open-ended, and
``max_discount_percentage`` strictly increasing across tiers.

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_discount_prompts.py

Counts are configurable via env vars (defaults shown)::

    SEED_DISCOUNT_NUM_GLOBAL=3                  # global-scope prompts
    SEED_DISCOUNT_NUM_PER_SEGMENT=2             # per segment_uuid
    SEED_DISCOUNT_NUM_PER_ITEM=1                # per item_uuid
    SEED_DISCOUNT_NUM_PER_PROVIDER_ITEM=1       # per provider_item_uuid

Writes generated UUIDs and payloads to ``discount_prompts.json``.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import random
import sys
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

try:
    from faker import Faker
except ModuleNotFoundError:
    sys.exit(
        "The 'faker' package is not installed. Install it with: pip install faker"
    )


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prepare_discount_prompts")

fake = Faker()

UPDATED_BY = "prepare_discount_prompts"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "discount_prompts.json")

SEGMENTS_INPUT = os.path.join(
    os.path.dirname(__file__), "segments_and_contacts.json"
)
FLIGHTS_INPUT = os.path.join(os.path.dirname(__file__), "flight_products.json")

NUM_GLOBAL = int(os.getenv("SEED_DISCOUNT_NUM_GLOBAL", "3"))
NUM_PER_SEGMENT = int(os.getenv("SEED_DISCOUNT_NUM_PER_SEGMENT", "2"))
NUM_PER_ITEM = int(os.getenv("SEED_DISCOUNT_NUM_PER_ITEM", "1"))
NUM_PER_PROVIDER_ITEM = int(os.getenv("SEED_DISCOUNT_NUM_PER_PROVIDER_ITEM", "1"))

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


# --- Prompt content templates ---------------------------------------------- #

GLOBAL_PROMPT_TEMPLATES = [
    "Apply a volume-tier discount when the total quote subtotal exceeds the configured thresholds.",
    "Encourage early-bird bookings: applicants who confirm at least {lead} days before service receive escalating discounts.",
    "Recurring-customer loyalty incentive: discounts scale with cumulative annual spend across all bookings.",
    "Promotional window for off-peak travel: reduce prices when departure date falls in the configured low-season window.",
    "Multi-leg itinerary incentive: bundle two or more flights on the same quote to qualify for tiered savings.",
]

SEGMENT_PROMPT_TEMPLATES = [
    "Preferred segment '{segment}' members receive volume discounts at lower thresholds than retail customers.",
    "Corporate-rate customers in segment '{segment}' qualify for negotiated tier pricing on Business and First fares.",
    "Loyalty tier '{segment}' triggers automatic discount escalation tied to cumulative bookings.",
]

ITEM_PROMPT_TEMPLATES = [
    "Promotional pricing on '{item}': discount scales with booked seat count on this specific route + cabin.",
    "Inventory clearance for '{item}': aggressive tiered discounting to move slow-moving capacity.",
    "Featured route '{item}': marketing-driven discount ladder to drive demand.",
]

PROVIDER_ITEM_PROMPT_TEMPLATES = [
    "Strategic-partner pricing for '{airline}' on this route: preferred-rate tiers when minimums are met.",
    "Group-booking discount with '{airline}' for {cabin} class: kicks in at the configured passenger thresholds.",
    "Inventory-clearance arrangement with '{airline}' for unsold seats on this flight number.",
]


def _build_conditions() -> list[str]:
    pool = [
        f"min_passengers >= {random.choice([5, 10, 15, 20])}",
        f"booking_lead_days >= {random.choice([7, 14, 30, 60])}",
        "loyalty_tier in ['gold', 'platinum']",
        "season != 'peak'",
        "channel == 'direct'",
        "payment_method in ['wire_transfer', 'credit_card']",
        "is_refundable == false",
    ]
    return random.sample(pool, k=random.randint(1, 3))


def _build_discount_rules() -> list[dict]:
    """Generate a valid tier ladder.

    Rules satisfied (see validate_and_normalize_discount_rules):
      * first tier starts at 0
      * each non-last tier has less_than == next tier's greater_than (contiguous)
      * last tier omits less_than (open-ended)
      * max_discount_percentage strictly increases across tiers
    """
    tier_count = random.randint(2, 4)
    bounds = [0.0]
    cursor = 0.0
    for _ in range(tier_count - 1):
        cursor += random.choice([500, 1000, 2500, 5000, 10000])
        bounds.append(float(cursor))

    # Strictly increasing discount percentages within sensible commercial bounds.
    start = random.choice([2.5, 5.0, 7.5])
    step = random.choice([2.5, 5.0])
    discounts = [round(start + i * step, 2) for i in range(tier_count)]
    discounts = [min(d, 50.0) for d in discounts]
    # Repair monotonicity if the cap above flattened anything.
    for i in range(1, len(discounts)):
        if discounts[i] <= discounts[i - 1]:
            discounts[i] = round(discounts[i - 1] + 0.5, 2)

    rules: list[dict] = []
    for i in range(tier_count):
        rule = {
            "greaterThan": bounds[i],
            "maxDiscountPercentage": discounts[i],
        }
        if i < tier_count - 1:
            rule["lessThan"] = bounds[i + 1]
        rules.append(rule)
    return rules


def _pick_status() -> str:
    return random.choices(["active", "in_review"], weights=[0.8, 0.2])[0]


# --- GraphQL --------------------------------------------------------------- #


DISCOUNT_PROMPT_MUTATION = """
mutation InsertUpdateDiscountPrompt(
    $scope: String, $tags: [String], $prompt: String,
    $conditions: [String], $rules: [JSONCamelCase],
    $priority: Int, $status: String, $by: String!
) {
    insertUpdateDiscountPrompt(
        scope: $scope, tags: $tags, discountPrompt: $prompt,
        conditions: $conditions, discountRules: $rules,
        priority: $priority, status: $status, updatedBy: $by
    ) {
        discountPrompt { discountPromptUuid }
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
            query=DISCOUNT_PROMPT_MUTATION,
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


# --- Seeders --------------------------------------------------------------- #


def _seed_one(
    engine: AIRFQEngine,
    *,
    scope: str,
    tags: list[str],
    prompt_text: str,
) -> dict | None:
    rules = _build_discount_rules()
    conditions = _build_conditions()
    priority = random.randint(1, 10)
    status = _pick_status()

    variables = {
        "scope": scope,
        "tags": tags,
        "prompt": prompt_text,
        "conditions": conditions,
        "rules": rules,
        "priority": priority,
        "status": status,
        "by": UPDATED_BY,
    }
    data = run_mutation(engine, variables)
    if not data:
        return None
    uuid = data["insertUpdateDiscountPrompt"]["discountPrompt"]["discountPromptUuid"]
    logger.info(
        "  %s (priority=%d, status=%s, tiers=%d) -> %s",
        scope,
        priority,
        status,
        len(rules),
        uuid,
    )
    return {
        "discountPromptUuid": uuid,
        "scope": scope,
        "tags": tags,
        "discountPrompt": prompt_text,
        "conditions": conditions,
        "discountRules": rules,
        "priority": priority,
        "status": status,
    }


def seed_global(engine: AIRFQEngine, count: int) -> list[dict]:
    out: list[dict] = []
    for i in range(count):
        template = random.choice(GLOBAL_PROMPT_TEMPLATES)
        text = template.format(
            lead=random.choice([14, 30, 60]),
        )
        # Light Faker flavour so multiple runs differ.
        text = f"{text} (ref: {fake.bothify('PROMO-####-??').upper()})"
        logger.info("[global %d/%d]", i + 1, count)
        record = _seed_one(engine, scope="global", tags=[], prompt_text=text)
        if record:
            out.append(record)
    return out


def seed_segments(engine: AIRFQEngine, segments: list[dict], per: int) -> list[dict]:
    out: list[dict] = []
    for s_idx, segment in enumerate(segments, start=1):
        seg_uuid = segment.get("segmentUuid")
        seg_name = segment.get("segmentName") or seg_uuid
        if not seg_uuid:
            continue
        for i in range(per):
            template = random.choice(SEGMENT_PROMPT_TEMPLATES)
            text = template.format(segment=seg_name)
            logger.info(
                "[segment %d/%d, prompt %d/%d] %s",
                s_idx,
                len(segments),
                i + 1,
                per,
                seg_name,
            )
            record = _seed_one(
                engine, scope="segment", tags=[seg_uuid], prompt_text=text
            )
            if record:
                out.append(record)
    return out


def seed_items(
    engine: AIRFQEngine,
    items: list[dict],
    provider_items_by_item: dict[str, list[dict]],
    per_item: int,
    per_provider_item: int,
) -> tuple[list[dict], list[dict]]:
    item_out: list[dict] = []
    provider_item_out: list[dict] = []
    for i_idx, item in enumerate(items, start=1):
        item_uuid = item.get("itemUuid")
        item_name = item.get("itemName") or item_uuid
        if not item_uuid:
            continue

        for i in range(per_item):
            template = random.choice(ITEM_PROMPT_TEMPLATES)
            text = template.format(item=item_name)
            logger.info(
                "[item %d/%d, prompt %d/%d] %s",
                i_idx,
                len(items),
                i + 1,
                per_item,
                item_name,
            )
            record = _seed_one(
                engine, scope="item", tags=[item_uuid], prompt_text=text
            )
            if record:
                item_out.append(record)

        for provider_item in provider_items_by_item.get(item_uuid, []):
            pi_uuid = provider_item.get("providerItemUuid")
            spec = provider_item.get("itemSpec") or {}
            airline = spec.get("airline_name") or "Provider"
            cabin = spec.get("cabin_class") or "the cabin"
            if not pi_uuid:
                continue
            for i in range(per_provider_item):
                template = random.choice(PROVIDER_ITEM_PROMPT_TEMPLATES)
                text = template.format(airline=airline, cabin=cabin)
                logger.info(
                    "[provider_item %s prompt %d/%d] %s",
                    pi_uuid,
                    i + 1,
                    per_provider_item,
                    airline,
                )
                record = _seed_one(
                    engine,
                    scope="provider_item",
                    tags=[pi_uuid],
                    prompt_text=text,
                )
                if record:
                    provider_item_out.append(record)
    return item_out, provider_item_out


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


def generate(engine: AIRFQEngine) -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    output: dict[str, Any] = {
        "global": [],
        "segment": [],
        "item": [],
        "provider_item": [],
    }

    logger.info("--- Seeding %d global discount prompts ---", NUM_GLOBAL)
    output["global"] = seed_global(engine, NUM_GLOBAL)

    segments_data = _safe_load(SEGMENTS_INPUT)
    segments = (segments_data or {}).get("segments") or []
    if segments and NUM_PER_SEGMENT > 0:
        logger.info(
            "--- Seeding %d prompts across %d segments ---",
            NUM_PER_SEGMENT * len(segments),
            len(segments),
        )
        output["segment"] = seed_segments(engine, segments, NUM_PER_SEGMENT)
    else:
        logger.info("Skipping segment-scoped prompts (no segments_and_contacts.json)")

    flights_data = _safe_load(FLIGHTS_INPUT)
    items = (flights_data or {}).get("items") or []
    provider_items = (flights_data or {}).get("provider_items") or []
    provider_items_by_item = _index_provider_items(provider_items)
    if items and (NUM_PER_ITEM > 0 or NUM_PER_PROVIDER_ITEM > 0):
        logger.info(
            "--- Seeding item / provider_item prompts across %d items ---",
            len(items),
        )
        item_out, pi_out = seed_items(
            engine,
            items,
            provider_items_by_item,
            NUM_PER_ITEM,
            NUM_PER_PROVIDER_ITEM,
        )
        output["item"] = item_out
        output["provider_item"] = pi_out
    else:
        logger.info("Skipping item/provider_item prompts (no flight_products.json)")

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info(
        "Wrote: %d global, %d segment, %d item, %d provider_item -> %s",
        len(output["global"]),
        len(output["segment"]),
        len(output["item"]),
        len(output["provider_item"]),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    engine = create_engine()
    result = generate(engine)
    write_output(result)
    logger.info("--- Done ---")
