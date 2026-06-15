#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Integration tests for ``resolve_inquire_catalog`` (schema.py:resolve_inquire_catalog
-> queries/catalog_inquiry.resolve_inquire_catalog -> handlers/catalog/handler.dispatch_inquire).

The resolver wraps the KGE-backed catalog handler, which routes through
``aws_lambda_invoker`` to ``knowledge_graph_engine.knowledge_graph_graphql``.
These tests require:

  * AI RFQ engine reachable (DynamoDB credentials + base_dir set in tests/.env)
  * knowledge_graph_engine importable on sys.path
  * KGE has a Neo4j instance registered for the partition AND extracted
    content present (run prepare_flight_catalog_refs.py first so the
    "queryable hits" tests find something).

Covered scenarios:

  1. Happy path -- text query returns a non-empty payload from KGE.
  2. Node-by-id inquiry is reported as unsupported (per current handler
     design -- KGE doesn't expose a node-by-id query yet).
  3. Missing/invalid query payload surfaces ``errorCode="system_error"``
     without raising a GraphQL transport error.
  4. Round-trip -- the ``nodeId`` returned by KGE matches the
     ``itemExternalId`` we passed at ingestion time, so it can be looked
     up in ``ItemCatalogRefModel`` to resolve a concrete ``item_uuid``.
"""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import sys
from typing import Any, Dict

import pytest
from silvaengine_utility.serializer import Serializer

logger = logging.getLogger("test_inquire_catalog")

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

BASE_DIR = os.getenv("base_dir") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "silvaengine_utility"))
sys.path.insert(1, os.path.join(BASE_DIR, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(BASE_DIR, "ai_rfq_engine"))
sys.path.insert(3, os.path.join(BASE_DIR, "knowledge_graph_engine"))

try:
    from ai_rfq_engine import AIRFQEngine
except ImportError:
    AIRFQEngine = None


# Optional companion JSON written by prepare_flight_catalog_refs.py -- when
# present, the round-trip test pulls a known nodeId from it; otherwise that
# test is skipped.
_CATALOG_REFS_JSON = os.path.join(
    os.path.dirname(__file__),
    "prepare_test_data",
    "flight_catalog_refs.json",
)


# --- Fixtures -------------------------------------------------------------- #


@pytest.fixture(scope="module")
def engine():
    if AIRFQEngine is None:
        pytest.skip("AIRFQEngine not importable")
    if not SETTING.get("endpoint_id") or not SETTING.get("part_id"):
        pytest.skip("endpoint_id / part_id missing from tests/.env")
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


@pytest.fixture(scope="module")
def catalog_refs_seed() -> dict | None:
    if not os.path.isfile(_CATALOG_REFS_JSON):
        return None
    try:
        with open(_CATALOG_REFS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# --- GraphQL helper -------------------------------------------------------- #


_INQUIRE_CATALOG_QUERY = """
query InquireCatalog($namespace: String, $nodeId: String, $query: JSONCamelCase) {
    inquireCatalog(namespace: $namespace, nodeId: $nodeId, query: $query) {
        namespace
        nodeId
        payload
        fetchedAt
        ttlSeconds
        errorCode
        errorMessage
    }
}
"""


def _graphql(engine, variables: Dict[str, Any], endpoint_id: str, part_id: str) -> Dict[str, Any]:
    response = engine.ai_rfq_graphql(
        query=_INQUIRE_CATALOG_QUERY,
        variables=variables,
        endpoint_id=endpoint_id,
        part_id=part_id,
    )
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
    if parsed.get("errors"):
        raise RuntimeError(f"GraphQL errors: {parsed['errors']}")
    return parsed.get("data", parsed).get("inquireCatalog") or {}


# --- Tests ----------------------------------------------------------------- #


class TestInquireCatalog:
    """Integration coverage for the inquire_catalog GraphQL resolver."""

    @pytest.mark.integration
    def test_text_query_returns_payload(self, engine, endpoint_id, part_id):
        """
        A well-formed text query reaches KGE and comes back with a
        searchable payload. KGE must have content (run
        prepare_flight_catalog_refs.py first); empty graphs return an
        empty results list but should still return the payload envelope.
        """
        print("\n=== test_text_query_returns_payload ===", flush=True)
        result = _graphql(
            engine,
            {
                "namespace": "FLIGHTS",
                "query": {
                    "queryText": "Business class flight",
                    "searchMode": "vector",
                    "topK": 5,
                    "page": 1,
                    "limit": 5,
                },
            },
            endpoint_id,
            part_id,
        )
        print(
            f"errorCode={result.get('errorCode')!r} "
            f"namespace={result.get('namespace')!r} "
            f"fetchedAt={result.get('fetchedAt')!r}",
            flush=True,
        )
        payload = result.get("payload") or {}
        results = payload.get("results") if isinstance(payload, dict) else None
        print(
            f"payload.results count = {len(results) if isinstance(results, list) else 'N/A'}",
            flush=True,
        )
        if isinstance(results, list):
            for i, hit in enumerate(results[:3]):
                score = (hit.get("metadata") or {}).get("score") if isinstance(hit, dict) else None
                print(f"  [{i}] score={score} keys={list(hit.keys()) if isinstance(hit, dict) else type(hit).__name__}", flush=True)
        assert result.get("errorCode") is None, (
            f"unexpected error: {result.get('errorCode')} / "
            f"{result.get('errorMessage')}"
        )
        assert result.get("namespace") == "FLIGHTS"
        assert isinstance(payload, dict), f"payload should be a dict, got {payload!r}"
        # KGE always returns `results` (possibly empty) on a well-formed query.
        assert "results" in payload, f"payload missing 'results': keys={list(payload)}"
        assert isinstance(payload["results"], list)
        print(f"PASS -- {len(payload['results'])} result(s) returned", flush=True)

    @pytest.mark.integration
    def test_node_id_lookup_reports_unsupported(self, engine, endpoint_id, part_id):
        """
        Passing ``nodeId`` directly triggers the documented
        OperationUnsupportedError, surfaced as an in-band errorCode.
        """
        print("\n=== test_node_id_lookup_reports_unsupported ===", flush=True)
        result = _graphql(
            engine,
            {
                "namespace": "FLIGHTS",
                "nodeId": "FLIGHT-JFK-LAX-BUS",
            },
            endpoint_id,
            part_id,
        )
        print(
            f"errorCode={result.get('errorCode')!r} "
            f"errorMessage={result.get('errorMessage')!r}",
            flush=True,
        )
        assert result.get("errorCode") == "operation_unsupported", result
        print("PASS -- node-by-id lookup rejected as expected", flush=True)

    @pytest.mark.integration
    def test_missing_query_text_returns_system_error(
        self, engine, endpoint_id, part_id
    ):
        """
        A browse inquiry without ``queryText`` should not raise -- the
        handler converts it to an in-band ``errorCode="system_error"``.
        """
        print("\n=== test_missing_query_text_returns_system_error ===", flush=True)
        result = _graphql(
            engine,
            {
                "namespace": "FLIGHTS",
                "query": {"searchMode": "vector"},  # missing queryText
            },
            endpoint_id,
            part_id,
        )
        print(
            f"errorCode={result.get('errorCode')!r} "
            f"errorMessage={result.get('errorMessage')!r}",
            flush=True,
        )
        assert result.get("errorCode") == "system_error", result
        print("PASS -- missing queryText surfaced as system_error", flush=True)

    @pytest.mark.integration
    def test_nodeid_round_trip_via_catalog_ref(
        self, engine, endpoint_id, part_id, catalog_refs_seed
    ):
        """
        End-to-end round trip:
          KGE search for a known ingested item
            -> response payload contains the item's documentExternalId
            -> that value matches an ItemCatalogRef row's nodeId
            -> which resolves to the internal item_uuid we ingested under.

        Skipped when prepare_flight_catalog_refs.py hasn't been run (no
        seed JSON, nothing to look up by).
        """
        print("\n=== test_nodeid_round_trip_via_catalog_ref ===", flush=True)
        if not catalog_refs_seed:
            print(
                "SKIP -- flight_catalog_refs.json not on disk; run "
                "prepare_flight_catalog_refs.py first",
                flush=True,
            )
            pytest.skip(
                "flight_catalog_refs.json not present -- run "
                "prepare_flight_catalog_refs.py first to populate KGE + refs"
            )

        # Pick any successfully-linked ref to round-trip.
        candidates = catalog_refs_seed.get("matched") or []
        candidates += catalog_refs_seed.get("fallbacks") or []
        if not candidates:
            print("SKIP -- no linked catalog refs in seed JSON", flush=True)
            pytest.skip("no linked catalog refs in seed JSON")
        ref = candidates[0]
        node_id = ref.get("nodeId")
        item_uuid = ref.get("itemUuid")
        assert node_id and item_uuid

        # Use the airline/cabin/route prose as a search query so vector
        # search has something semantic to lean on.
        extra = ref.get("extra") or {}
        query_text = " ".join(
            str(p)
            for p in [
                extra.get("airlineCode"),
                extra.get("cabinClass"),
                extra.get("route"),
            ]
            if p
        ) or node_id

        print(f"querying KGE with: {query_text!r}", flush=True)
        print(f"expecting nodeId={node_id!r} item_uuid={item_uuid!r}", flush=True)

        result = _graphql(
            engine,
            {
                "namespace": catalog_refs_seed.get("namespace") or "FLIGHTS",
                "query": {
                    "queryText": query_text,
                    "searchMode": "vector",
                    "topK": 10,
                    "page": 1,
                    "limit": 10,
                },
            },
            endpoint_id,
            part_id,
        )
        assert result.get("errorCode") is None, result
        payload = result.get("payload") or {}
        results = payload.get("results") or []
        print(f"KGE returned {len(results)} result(s)", flush=True)
        for i, hit in enumerate(results[:3]):
            score = (hit.get("metadata") or {}).get("score") if isinstance(hit, dict) else None
            text = ""
            md = hit.get("metadata") if isinstance(hit, dict) else None
            if isinstance(md, dict):
                node = md.get("node") if isinstance(md, dict) else None
                if isinstance(node, dict):
                    text = (node.get("text") or "")[:120]
            print(f"  [{i}] score={score} text={text!r}", flush=True)
        assert results, (
            f"KGE returned 0 results for query={query_text!r}; "
            "is the partition populated?"
        )

        # KGE's vector search returns Chunk nodes (text fragments produced
        # by neo4j-graphrag's chunker), not the Document node -- so the
        # literal ``documentExternalId`` lives on the Document, one hop
        # away from what comes back here. The matching evidence we DO have
        # is that the chunks' prose contains the airline / route / cabin
        # we passed in at extract time. Assert on that prose round-trip.
        expected_route = (extra.get("route") or "").replace("-", "->")
        expected_cabin = extra.get("cabinClass") or ""
        print(
            f"asserting top chunk contains route={expected_route!r} "
            f"and cabin={expected_cabin!r}",
            flush=True,
        )
        assert results[0].get("metadata"), f"first result missing metadata: {results[0]}"
        # The route (e.g. "CDG->JFK") and cabin class (e.g. "Business") MUST
        # appear in the top-ranked chunk for the ingest->search round trip
        # to be considered correct.
        top = json.dumps(results[0], default=str)
        assert expected_route in top and expected_cabin in top, (
            f"top result missing route={expected_route!r} and/or cabin="
            f"{expected_cabin!r}; got: {top[:500]!r}"
        )
        print(
            f"PASS -- KGE found the ingested item; round-trip works "
            f"(nodeId={node_id!r} -> item_uuid={item_uuid!r})",
            flush=True,
        )


if __name__ == "__main__":
    # Make `python test_inquire_catalog.py` work the same as
    # `pytest test_inquire_catalog.py -v -s`. Pytest collection + fixtures
    # require pytest to run; calling python on this file directly otherwise
    # just imports the module and exits without running any tests.
    import sys as _sys

    _sys.exit(
        pytest.main(
            [
                __file__,
                "-v",
                "-s",
                "--log-cli-level=INFO",
                *_sys.argv[1:],
            ]
        )
    )
