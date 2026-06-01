#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Ingest AI RFQ flight products into the knowledge graph and bridge them
back via ``ItemCatalogRef``.

End-to-end flow per item in ``flight_products.json``:

    1. Compose a natural-language description from the bundled item +
       provider item(s) + batches + tiers + cancellation policy.
    2. Call ``executeExtract`` on ``knowledge_graph_engine`` so the
       neo4j-graphrag pipeline writes entities/relationships into Neo4j
       and a ``kge-documents`` row.
    3. Use the local ``itemExternalId`` as the stable bridge identifier
       (passed to KGE as ``documentExternalId``).
    4. Call ``insertUpdateItemCatalogRef`` on the AI RFQ engine for each
       (item, provider_item) pair, linking
       ``namespace + nodeId → (item_uuid, provider_item_uuid)``.

Both engines are invoked through ``silvaengine_utility.Invoker``'s
``invoke_funct_on_local`` so the cross-project call shape mirrors the
production aws_lambda_invoker path used by
``ai_rfq_engine/handlers/catalog/handler.py``.

Usage::

    python ai_rfq_engine/tests/prepare_test_data/prepare_flight_catalog_refs.py

Configurable via env vars::

    SEED_CATALOG_INPUT=flight_products.json     # filename in this directory
    SEED_CATALOG_NAMESPACE=FLIGHTS              # ItemCatalogRef namespace
    SEED_CATALOG_SKIP_INGEST=0                  # 1 = link-only; search KGE for an existing node
    SEED_CATALOG_SEARCH_MODE=vector             # used when SKIP_INGEST=1
    SEED_CATALOG_TOP_K=5                        # used when SKIP_INGEST=1
    SEED_CATALOG_FALLBACK_TO_EXTERNAL_ID=1      # link-only fallback when KGE returns nothing

Writes ``flight_catalog_refs.json`` next to this script.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
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
sys.path.insert(3, os.path.join(BASE_DIR, "knowledge_graph_engine"))

from silvaengine_utility import Invoker  # noqa: E402


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("prepare_flight_catalog_refs")


UPDATED_BY = "prepare_flight_catalog_refs"
INPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    os.getenv("SEED_CATALOG_INPUT", "flight_products.json"),
)
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "flight_catalog_refs.json")

NAMESPACE = os.getenv("SEED_CATALOG_NAMESPACE", "FLIGHTS")
SKIP_INGEST = os.getenv("SEED_CATALOG_SKIP_INGEST", "0") == "1"
SEARCH_MODE = os.getenv("SEED_CATALOG_SEARCH_MODE", "vector")
TOP_K = int(os.getenv("SEED_CATALOG_TOP_K", "5"))
FALLBACK_TO_EXTERNAL_ID = os.getenv(
    "SEED_CATALOG_FALLBACK_TO_EXTERNAL_ID", "1"
) == "1"

SETTING = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_rfq_graphql": {
            "module_name": "ai_rfq_engine",
            "class_name": "AIRFQEngine",
        },
        "knowledge_graph_graphql": {
            "module_name": "knowledge_graph_engine",
            "class_name": "KnowledgeGraphEngine",
        },
    },
    "endpoint_id": os.getenv("endpoint_id"),
    "part_id": os.getenv("part_id"),
    "execute_mode": os.getenv("execute_mode", "local"),
    "initialize_tables": os.getenv("initialize_tables", "0") == "1",
    "cache_enabled": os.getenv("cache_enabled", "0") == "1",
}


# --- GraphQL ---------------------------------------------------------------- #


EXECUTE_EXTRACT_MUTATION = """
mutation ExecuteExtract(
    $text: String!,
    $documentSource: String,
    $documentExternalId: String
) {
    executeExtract(
        text: $text,
        documentSource: $documentSource,
        documentExternalId: $documentExternalId
    ) {
        status documentUuid entitiesExtracted relationshipsExtracted
    }
}
"""

INQUIRE_CATALOG_QUERY = """
query InquireCatalog($namespace: String, $query: JSONCamelCase) {
    inquireCatalog(namespace: $namespace, query: $query) {
        namespace nodeId payload errorCode errorMessage
    }
}
"""

ITEM_CATALOG_REF_MUTATION = """
mutation InsertUpdateItemCatalogRef(
    $ns: String, $node: String, $iid: String, $pid: String,
    $extra: JSONCamelCase, $stat: String, $by: String!
) {
    insertUpdateItemCatalogRef(
        namespace: $ns, nodeId: $node, itemUuid: $iid,
        providerItemUuid: $pid, extra: $extra, status: $stat, updatedBy: $by
    ) {
        itemCatalogRef { catalogRefUuid }
    }
}
"""


# --- Invocation ------------------------------------------------------------- #


def invoke(funct: str, query: str, variables: dict) -> dict | None:
    """
    Call either ``ai_rfq_graphql`` or ``knowledge_graph_graphql`` through
    ``Invoker.invoke_funct_on_local``. The helper unwraps the body /
    error envelope for us and returns the GraphQL ``data`` payload.
    """
    try:
        return Invoker.invoke_funct_on_local(
            logger,
            SETTING,
            funct,
            query=query,
            variables=variables,
            endpoint_id=SETTING["endpoint_id"],
            part_id=SETTING["part_id"],
        )
    except Exception as exc:
        logger.error("Invoke %s failed: %s", funct, exc)
        return None


# --- Description composer --------------------------------------------------- #


def _format_price_tier(tier: dict) -> str:
    pax = tier.get("paxType") or "unit"
    price = tier.get("pricePerUom")
    currency = tier.get("currency") or "USD"
    return f"{pax} {currency} {price}"


def _format_policy_tiers(tiers_blob: Any) -> str:
    if not isinstance(tiers_blob, dict):
        return ""
    tiers = tiers_blob.get("tiers")
    if not isinstance(tiers, list):
        return ""
    parts = []
    for t in tiers:
        if not isinstance(t, dict):
            continue
        gate = (
            t.get("hours_before_departure_gte")
            or t.get("hours_before_service_gte")
            or t.get("days_before_service_gte")
        )
        refund = t.get("refund_pct")
        if gate is not None and refund is not None:
            parts.append(f"{gate}h+: {int(refund * 100)}% refund")
    return "; ".join(parts)


def compose_description(
    *,
    item: dict,
    provider_items: list[dict],
    batches: list[dict],
    tiers: list[dict],
    policy: dict | None,
    bundle_components: list[dict] | None = None,
    bundles_by_uuid: dict[str, dict] | None = None,
) -> str:
    """Build the prose KGE will run extraction over."""
    lines: list[str] = []
    name = item.get("itemName") or item.get("itemExternalId") or item.get("itemUuid")
    description = item.get("itemDescription")
    lines.append(f"Flight product: {name}.")
    if description:
        lines.append(description)

    if provider_items:
        # All provider items under one item share itemSpec keys; treat the
        # first as canonical for prose, then list every airline that sells it.
        airlines = []
        for pi in provider_items:
            spec = pi.get("itemSpec") or {}
            code = spec.get("airline_code") or ""
            airline_name = spec.get("airline_name") or "unknown carrier"
            airlines.append(f"{airline_name} ({code})" if code else airline_name)
        primary_spec = provider_items[0].get("itemSpec") or {}
        origin = primary_spec.get("origin_iata")
        destination = primary_spec.get("destination_iata")
        cabin = primary_spec.get("cabin_class")
        baggage = primary_spec.get("baggage_allowance_kg")
        meal = primary_spec.get("meal_included")
        if origin and destination:
            lines.append(f"Route: {origin} to {destination}.")
        if cabin:
            lines.append(f"Cabin class: {cabin}.")
        lines.append(f"Operated by: {', '.join(airlines)}.")
        if baggage:
            lines.append(f"Baggage allowance: {baggage} kg.")
        if meal is not None:
            lines.append(f"Meal included: {'yes' if meal else 'no'}.")

    if tiers:
        priced = [_format_price_tier(t) for t in tiers if t.get("pricePerUom") is not None]
        if priced:
            lines.append(f"Fares: {', '.join(priced)}.")

    if batches:
        rendered = []
        for b in batches[:5]:
            flight_no = b.get("flightNumber") or b.get("batchNo")
            start = b.get("serviceStartAt")
            qty = b.get("availabilityQty")
            seats = f", {int(qty)} seats" if qty is not None else ""
            rendered.append(f"{flight_no} departing {start}{seats}")
        lines.append(f"Scheduled flights: {'; '.join(rendered)}.")

    if policy:
        label = policy.get("label") or "Cancellation policy"
        tiers_text = _format_policy_tiers(policy.get("tiers"))
        if tiers_text:
            lines.append(f"{label}: {tiers_text}.")
        elif policy.get("description"):
            lines.append(f"{label}: {policy['description']}.")

    package_names = []
    for component in bundle_components or []:
        bundle = (bundles_by_uuid or {}).get(component.get("bundleUuid"), {})
        name = bundle.get("bundleName") or bundle.get("bundleCode")
        if name and name not in package_names:
            package_names.append(name)
    if package_names:
        lines.append(
            "This flight can be used as a component in package templates: "
            + ", ".join(package_names)
            + "."
        )

    return " ".join(lines)


# --- KGE ingestion ---------------------------------------------------------- #


def ingest_into_kge(item: dict, text: str) -> dict | None:
    """
    Push ``text`` into KGE via ``executeExtract``. Returns the extract
    result (status, documentUuid, entitiesExtracted, relationshipsExtracted)
    or ``None`` if the call failed.
    """
    external_id = item.get("itemExternalId") or item.get("itemUuid")
    variables = {
        "text": text,
        "documentSource": "ai_rfq_seed",
        "documentExternalId": external_id,
    }
    data = invoke("knowledge_graph_graphql", EXECUTE_EXTRACT_MUTATION, variables)
    if not data:
        return None
    result = data.get("executeExtract") if isinstance(data, dict) else None
    if not result:
        logger.warning("  KGE executeExtract returned no payload for %s", external_id)
        return None
    logger.info(
        "  KGE ingest: documentUuid=%s entities=%s relationships=%s",
        result.get("documentUuid"),
        result.get("entitiesExtracted"),
        result.get("relationshipsExtracted"),
    )
    return result


# --- KGE search-based lookup (used when SKIP_INGEST=1) ---------------------- #


_NODE_ID_KEYS = (
    "elementId",
    "element_id",
    "nodeId",
    "node_id",
    "id",
    "documentExternalId",
    "document_external_id",
    "documentUuid",
    "document_uuid",
    "externalId",
    "external_id",
)


def extract_node_identity(result: Any) -> dict | None:
    if not isinstance(result, dict):
        return None
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    for key in _NODE_ID_KEYS:
        candidate = result.get(key) or metadata.get(key)
        if candidate:
            return {
                "node_id": str(candidate),
                "key": key,
                "metadata": metadata,
                "score": metadata.get("score") or result.get("score"),
            }
    return None


def lookup_existing_node(query_text: str) -> dict | None:
    variables = {
        "namespace": NAMESPACE,
        "query": {
            "queryText": query_text,
            "searchMode": SEARCH_MODE,
            "topK": TOP_K,
            "page": 1,
            "limit": TOP_K,
        },
    }
    data = invoke("ai_rfq_graphql", INQUIRE_CATALOG_QUERY, variables)
    if not data:
        return None
    inquire = data.get("inquireCatalog") or {}
    if inquire.get("errorCode"):
        logger.warning(
            "  inquire_catalog error: %s %s",
            inquire.get("errorCode"),
            inquire.get("errorMessage"),
        )
        return None
    payload = inquire.get("payload") or {}
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return None
    for result in results:
        identity = extract_node_identity(result)
        if identity:
            return identity
    return None


# --- Catalog ref seeder ----------------------------------------------------- #


def upsert_catalog_ref(
    *,
    item: dict,
    provider_item: dict,
    node_id: str,
    extra: dict,
) -> dict | None:
    data = invoke(
        "ai_rfq_graphql",
        ITEM_CATALOG_REF_MUTATION,
        {
            "ns": NAMESPACE,
            "node": node_id,
            "iid": item["itemUuid"],
            "pid": provider_item["providerItemUuid"],
            "extra": extra,
            "stat": "active",
            "by": UPDATED_BY,
        },
    )
    if not data:
        return None
    catalog_ref_uuid = data["insertUpdateItemCatalogRef"]["itemCatalogRef"][
        "catalogRefUuid"
    ]
    record = {
        "catalogRefUuid": catalog_ref_uuid,
        "namespace": NAMESPACE,
        "nodeId": node_id,
        "itemUuid": item["itemUuid"],
        "providerItemUuid": provider_item["providerItemUuid"],
        "extra": extra,
    }
    logger.info(
        "  catalog_ref: %s %s nodeId=%s -> %s",
        item.get("itemName"),
        provider_item.get("providerItemExternalId"),
        node_id,
        catalog_ref_uuid,
    )
    return record


# --- Orchestrator ----------------------------------------------------------- #


def load_input() -> dict:
    if not os.path.isfile(INPUT_FILE):
        raise RuntimeError(
            f"Input file not found: {INPUT_FILE}. Run "
            "prepare_flight_products.py first."
        )
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def index_by(items: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for entry in items:
        k = entry.get(key)
        if k:
            grouped.setdefault(k, []).append(entry)
    return grouped


def index_one_by(items: list[dict], key: str) -> dict[str, dict]:
    return {entry[key]: entry for entry in items if entry.get(key)}


def build_search_text(item: dict, provider_items: list[dict]) -> str:
    external_id = item.get("itemExternalId")
    if external_id:
        return external_id
    parts = [item.get("itemName")]
    spec = (provider_items[0].get("itemSpec") if provider_items else {}) or {}
    if spec.get("airline_name"):
        parts.append(spec["airline_name"])
    if spec.get("cabin_class"):
        parts.append(spec["cabin_class"])
    return " ".join(p for p in parts if p)


def generate() -> dict:
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        raise RuntimeError(
            "endpoint_id and part_id must be set in tests/.env before running"
        )

    flight_data = load_input()
    items = flight_data.get("items") or []
    provider_items_by_item = index_by(
        flight_data.get("provider_items") or [], "itemUuid"
    )
    batches_by_item = index_by(
        flight_data.get("provider_item_batches") or [], "itemUuid"
    )
    tiers_by_item = index_by(
        flight_data.get("item_price_tiers") or [], "itemUuid"
    )
    bundle_components_by_item = index_by(
        flight_data.get("bundle_components") or [], "itemUuid"
    )
    bundles_by_uuid = index_one_by(flight_data.get("bundles") or [], "bundleUuid")
    policies_by_uuid = {
        p.get("policyUuid"): p
        for p in (flight_data.get("cancellation_policies") or [])
        if p.get("policyUuid")
    }

    output: dict[str, Any] = {
        "namespace": NAMESPACE,
        "skipIngest": SKIP_INGEST,
        "ingested": [],
        "matched": [],
        "fallbacks": [],
        "unmatched": [],
    }

    mode = "link-only (skip ingest)" if SKIP_INGEST else "ingest + link"
    logger.info("--- %s mode: %d items ---", mode, len(items))

    for idx, item in enumerate(items, start=1):
        external_id = item.get("itemExternalId") or item.get("itemUuid")
        logger.info("[%d/%d] %s (%s)", idx, len(items), item.get("itemName"), external_id)

        siblings = provider_items_by_item.get(item.get("itemUuid"), [])
        if not siblings:
            logger.warning("  no provider items; skipping")
            continue

        item_batches = batches_by_item.get(item.get("itemUuid"), [])
        item_tiers = tiers_by_item.get(item.get("itemUuid"), [])
        item_components = bundle_components_by_item.get(item.get("itemUuid"), [])
        policy = None
        for b in item_batches:
            pol_uuid = b.get("cancellationPolicyUuid")
            if pol_uuid and pol_uuid in policies_by_uuid:
                policy = policies_by_uuid[pol_uuid]
                break

        node_id: str | None = None
        ingest_result: dict | None = None
        matched_via: str | None = None
        used_fallback = False

        if SKIP_INGEST:
            query_text = build_search_text(item, siblings)
            identity = lookup_existing_node(query_text)
            if identity:
                node_id = identity["node_id"]
                matched_via = identity.get("key")
                logger.info(
                    "  kge lookup: nodeId=%s (via %s) score=%s",
                    node_id,
                    matched_via,
                    identity.get("score"),
                )
            elif FALLBACK_TO_EXTERNAL_ID and item.get("itemExternalId"):
                node_id = item["itemExternalId"]
                used_fallback = True
                matched_via = "fallback:itemExternalId"
                logger.warning(
                    "  KGE returned nothing; falling back to itemExternalId=%s",
                    node_id,
                )
            else:
                logger.error("  no usable nodeId for %s; skipping", external_id)
                output["unmatched"].append(
                    {"itemUuid": item.get("itemUuid"), "queryText": query_text}
                )
                continue
        else:
            description = compose_description(
                item=item,
                provider_items=siblings,
                batches=item_batches,
                tiers=item_tiers,
                policy=policy,
                bundle_components=item_components,
                bundles_by_uuid=bundles_by_uuid,
            )
            ingest_result = ingest_into_kge(item, description)
            if not ingest_result:
                logger.error(
                    "  ingest failed for %s; skipping catalog ref", external_id
                )
                output["unmatched"].append(
                    {
                        "itemUuid": item.get("itemUuid"),
                        "itemExternalId": item.get("itemExternalId"),
                        "reason": "kge_extract_failed",
                    }
                )
                continue
            node_id = item.get("itemExternalId") or ingest_result.get("documentUuid")
            matched_via = "ingest:documentExternalId"
            output["ingested"].append(
                {
                    "itemUuid": item.get("itemUuid"),
                    "itemExternalId": item.get("itemExternalId"),
                    "documentUuid": ingest_result.get("documentUuid"),
                    "entitiesExtracted": ingest_result.get("entitiesExtracted"),
                    "relationshipsExtracted": ingest_result.get(
                        "relationshipsExtracted"
                    ),
                }
            )

        if not node_id:
            logger.error("  resolved nodeId is empty for %s; skipping", external_id)
            continue

        for provider_item in siblings:
            spec = provider_item.get("itemSpec") or {}
            extra = {
                "itemExternalId": item.get("itemExternalId"),
                "providerItemExternalId": provider_item.get(
                    "providerItemExternalId"
                ),
                "airlineCode": spec.get("airline_code"),
                "route": (
                    f"{spec.get('origin_iata')}-{spec.get('destination_iata')}"
                    if spec.get("origin_iata") and spec.get("destination_iata")
                    else None
                ),
                "cabinClass": spec.get("cabin_class"),
                "bundleComponents": [
                    {
                        "bundleUuid": component.get("bundleUuid"),
                        "bundleCode": (
                            bundles_by_uuid.get(component.get("bundleUuid"), {}).get(
                                "bundleCode"
                            )
                        ),
                        "bundleName": (
                            bundles_by_uuid.get(component.get("bundleUuid"), {}).get(
                                "bundleName"
                            )
                        ),
                        "bundleComponentUuid": component.get(
                            "bundleComponentUuid"
                        ),
                        "componentRole": component.get("componentRole"),
                    }
                    for component in item_components
                ],
                "kgeResolution": {
                    "matchedVia": matched_via,
                    "documentUuid": (
                        ingest_result.get("documentUuid") if ingest_result else None
                    ),
                },
            }
            record = upsert_catalog_ref(
                item=item,
                provider_item=provider_item,
                node_id=node_id,
                extra=extra,
            )
            if record:
                bucket = "fallbacks" if used_fallback else "matched"
                output[bucket].append(record)

    return output


def write_output(output: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    logger.info(
        "Wrote: %d ingested, %d matched, %d fallback, %d unmatched -> %s",
        len(output["ingested"]),
        len(output["matched"]),
        len(output["fallbacks"]),
        len(output["unmatched"]),
        OUTPUT_FILE,
    )


if __name__ == "__main__":
    result = generate()
    write_output(result)
    logger.info("--- Done ---")
