#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Knowledge graph backed catalog inquiry boundary."""
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Optional, TypedDict

import pendulum
from graphene import ResolveInfo
from silvaengine_constants import InvocationType
from silvaengine_utility import Invoker
from silvaengine_utility.serializer import Serializer


class CatalogReference(TypedDict):
    namespace: str
    node_id: Optional[str]


class CatalogResponse(TypedDict, total=False):
    ref: CatalogReference
    payload: Any
    fetched_at: str
    ttl_seconds: Optional[int]


class CatalogHandlerError(Exception):
    code = "system_error"

    def __init__(self, message: str = "", *, details: Optional[dict] = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.details = details or {}


class SystemTimeoutError(CatalogHandlerError):
    code = "system_timeout"


class SystemError(CatalogHandlerError):
    code = "system_error"


class OperationUnsupportedError(CatalogHandlerError):
    code = "operation_unsupported"


_KGE_SEARCH_QUERY = """
query Search(
    $queryText: String!,
    $searchMode: String,
    $indexName: String,
    $retrievalQuery: String,
    $filters: JSONCamelCase,
    $topK: Int,
    $page: Int,
    $limit: Int
) {
    search(
        queryText: $queryText,
        searchMode: $searchMode,
        indexName: $indexName,
        retrievalQuery: $retrievalQuery,
        filters: $filters,
        topK: $topK,
        page: $page,
        limit: $limit
    ) {
        results
        query
        total
        page
        limit
    }
}
"""


def _partition_key(info: ResolveInfo) -> str:
    partition_key = info.context.get("partition_key")
    if not partition_key:
        raise SystemError("partition_key is required for knowledge graph catalog inquiry")
    return partition_key


def _decode_graphql_result(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise SystemError("Knowledge graph invocation returned no response")
    body = response.get("body", response)
    if isinstance(body, (str, bytes)):
        body = Serializer.json_loads(body)
    if not isinstance(body, dict):
        raise SystemError("Knowledge graph invocation returned an invalid response")
    if body.get("errors"):
        raise SystemError(f"Knowledge graph catalog search failed: {body['errors']}")
    data = body.get("data", body)
    result = data.get("search") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        raise SystemError("Knowledge graph invocation did not return search data")
    return result


def _search_inquiry(
    info: ResolveInfo,
    reference: CatalogReference,
    query: dict[str, Any],
) -> CatalogResponse:
    query_text = query.get("query_text")
    if not query_text:
        raise SystemError("Catalog browse inquiry requires query.query_text")
    try:
        invoker = info.context.get("aws_lambda_invoker")
        if not callable(invoker):
            raise SystemError("aws_lambda_invoker is required for catalog inquiry")
        response = invoker(
            invocation_type=InvocationType.REQUEST_RESPONSE,
            payload=Invoker.build_invoker_payload(
                context=info.context,
                module_name="knowledge_graph_engine",
                class_name="KnowledgeGraphEngine",
                function_name="knowledge_graph_graphql",
                parameters={
                    "query": _KGE_SEARCH_QUERY,
                    "variables": {
                        "queryText": query_text,
                        "searchMode": query.get("search_mode", "text2cypher"),
                        "indexName": query.get("index_name", "vector"),
                        "retrievalQuery": query.get("retrieval_query"),
                        "filters": query.get("filters"),
                        "topK": query.get("top_k", 10),
                        "page": query.get("page", 1),
                        "limit": query.get("limit", 10),
                    },
                    "context": info.context,
                },
            ),
        )
        payload = _decode_graphql_result(response)
    except CatalogHandlerError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "timeout" in message or "timed out" in message:
            raise SystemTimeoutError("Knowledge graph catalog search timed out") from exc
        raise SystemError(f"Knowledge graph catalog search failed: {exc}") from exc
    return {
        "ref": reference,
        "payload": payload,
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": None,
    }


def dispatch_inquire(
    info: ResolveInfo,
    *,
    namespace: str = "DEFAULT",
    node_id: Optional[str] = None,
    query: Optional[Any] = None,
) -> CatalogResponse:
    """Inquire through KGE; KGE owns all graph instance configuration."""
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(
        info, operation="inquire", handler="catalog", namespace=namespace
    ):
        _partition_key(info)
        reference: CatalogReference = {
            "namespace": namespace,
            "node_id": node_id,
        }
        if node_id is not None:
            raise OperationUnsupportedError(
                "Node inquiry is not enabled: knowledge_graph_engine does not expose "
                "a public node-by-id query"
            )
        if not isinstance(query, dict):
            raise SystemError("Catalog browse inquiry requires a query object")
        return _search_inquiry(info, reference, query)
