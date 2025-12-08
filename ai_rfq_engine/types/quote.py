#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, Int, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON

from ..models.batch_loaders import get_loaders
from ..utils.normalization import normalize_to_json


class QuoteType(ObjectType):
    request_uuid = String()  # keep raw id
    quote_uuid = String()
    endpoint_id = String()
    provider_corp_external_id = String()
    sales_rep_email = String()
    rounds = Int()
    shipping_method = String()
    shipping_amount = String()
    total_quote_amount = String()
    total_quote_discount = String()
    final_total_quote_amount = String()
    notes = String()
    status = String()
    expired_at = DateTime()

    # Nested resolvers: strongly-typed nested relationship
    request = Field(lambda: RequestType)

    # Nested resolvers: strongly-typed nested relationships
    quote_items = List(JSON)
    installments = List(JSON)

    discount_prompts = List(JSON)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_request(parent, info):
        """Resolve nested Request for this quote using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "request", None)
        if isinstance(existing, dict):
            return RequestType(**existing)
        if isinstance(existing, RequestType):
            return existing

        # Case 1: need to fetch using DataLoader
        endpoint_id = info.context.get("endpoint_id")
        request_uuid = getattr(parent, "request_uuid", None)
        if not endpoint_id or not request_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.request_loader.load((endpoint_id, request_uuid)).then(
            lambda request_dict: RequestType(**request_dict) if request_dict else None
        )

    def resolve_quote_items(parent, info):
        """Resolve nested QuoteItems for this quote."""
        # Check if already embedded
        existing = getattr(parent, "quote_items", None)
        if isinstance(existing, list):
            return [normalize_to_json(qi) for qi in existing]

        # Fetch quote items for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.quote_item_list_loader.load(quote_uuid).then(
            lambda q_items: [normalize_to_json(qi) for qi in (q_items or [])]
        )

    def resolve_installments(parent, info):
        """Resolve nested Installments for this quote."""
        # Check if already embedded
        existing = getattr(parent, "installments", None)
        if isinstance(existing, list):
            return [normalize_to_json(inst) for inst in existing]

        # Fetch installments for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.installment_list_loader.load(quote_uuid).then(
            lambda insts: [normalize_to_json(inst) for inst in (insts or [])]
        )

    def resolve_discount_prompts(parent, info):
        """
        Resolve discount prompts for this quote with hierarchical scopes.

        Loads prompts from:
        - GLOBAL scope (always)
        - SEGMENT scope (from request)
        - ITEM scope (for all unique items in quote_items)
        - PROVIDER_ITEM scope (for all unique provider items in quote_items)
        """
        from promise import Promise

        # Check if already embedded
        existing = getattr(parent, "discount_prompts", None)
        if isinstance(existing, list):
            return [normalize_to_json(dp) for dp in existing]

        endpoint_id = info.context.get("endpoint_id")
        if not endpoint_id:
            return []

        quote_uuid = getattr(parent, "quote_uuid", None)
        request_uuid = getattr(parent, "request_uuid", None)
        if not quote_uuid or not request_uuid:
            return []

        loaders = get_loaders(info.context)

        def combine_all_prompts(results):
            """Combine prompts from all loaded scopes and deduplicate."""
            request_dict, quote_items = results

            seen_uuids = set()

            # Load GLOBAL prompts
            global_promise = loaders.discount_prompt_global_loader.load(endpoint_id)

            # Load SEGMENT prompts if request has segment_uuid
            segment_promise = None
            segment_uuid = request_dict.get("segment_uuid") if request_dict else None
            if segment_uuid:
                segment_promise = loaders.discount_prompt_by_segment_loader.load(
                    (endpoint_id, segment_uuid)
                )

            # Load ITEM and PROVIDER_ITEM prompts for all unique items in quote_items
            item_promises = []
            provider_item_promises = []
            if quote_items:
                unique_item_uuids = set()
                unique_provider_items = set()

                for qi in quote_items:
                    item_uuid = qi.get("item_uuid")
                    provider_item_uuid = qi.get("provider_item_uuid")

                    if item_uuid:
                        unique_item_uuids.add(item_uuid)

                    if item_uuid and provider_item_uuid:
                        unique_provider_items.add((item_uuid, provider_item_uuid))

                # Load ITEM prompts
                for item_uuid in unique_item_uuids:
                    item_promises.append(
                        loaders.discount_prompt_by_item_loader.load((endpoint_id, item_uuid))
                    )

                # Load PROVIDER_ITEM prompts
                for item_uuid, provider_item_uuid in unique_provider_items:
                    provider_item_promises.append(
                        loaders.discount_prompt_by_provider_item_loader.load(
                            (endpoint_id, item_uuid, provider_item_uuid)
                        )
                    )

            # Combine all promises
            promises_to_resolve = [global_promise]
            if segment_promise:
                promises_to_resolve.append(segment_promise)
            promises_to_resolve.extend(item_promises)
            promises_to_resolve.extend(provider_item_promises)

            def merge_prompts(prompt_lists):
                """Merge all prompt lists and deduplicate by discount_prompt_uuid."""
                merged = []
                for prompt_list in prompt_lists:
                    for prompt in (prompt_list or []):
                        prompt_uuid = prompt.get("discount_prompt_uuid")
                        if prompt_uuid and prompt_uuid not in seen_uuids:
                            seen_uuids.add(prompt_uuid)
                            merged.append(normalize_to_json(prompt))
                return merged

            return Promise.all(promises_to_resolve).then(merge_prompts)

        # Load request and quote_items in parallel, then combine all prompts
        return Promise.all([
            loaders.request_loader.load((endpoint_id, request_uuid)),
            loaders.quote_item_list_loader.load(quote_uuid)
        ]).then(combine_all_prompts)


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)


# Bottom imports - imported after class definitions to avoid circular imports
from .request import RequestType
