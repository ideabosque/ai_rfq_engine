# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility import Utility


def _initialize_tables(logger: logging.Logger) -> None:
    from .discount_prompt import create_discount_prompt_table
    from .file import create_file_table
    from .installment import create_installment_table
    from .item import create_item_table
    from .item_price_tier import create_item_price_tier_table
    from .provider_item import create_provider_item_table
    from .provider_item_batches import create_provider_item_batch_table
    from .quote import create_quote_table
    from .quote_item import create_quote_item_table
    from .request import create_request_table
    from .segment import create_segment_table
    from .segment_contact import create_segment_contact_table

    create_item_table(logger)
    create_provider_item_table(logger)
    create_provider_item_batch_table(logger)
    create_item_price_tier_table(logger)
    create_segment_table(logger)
    create_segment_contact_table(logger)
    create_quote_table(logger)
    create_quote_item_table(logger)
    create_request_table(logger)
    create_file_table(logger)
    create_installment_table(logger)
    create_discount_prompt_table(logger)
    return


def _get_request(endpoint_id: str, request_uuid: str) -> Dict[str, Any]:
    from .request import get_request, get_request_count

    count = get_request_count(endpoint_id, request_uuid)
    if count == 0:
        return {}

    request = get_request(endpoint_id, request_uuid)

    return {
        "endpoint_id": request.endpoint_id,
        "request_uuid": request.request_uuid,
        "email": request.email,
        "request_title": request.request_title,
        "request_description": request.request_description,
        "billing_address": request.billing_address,
        "shipping_address": request.shipping_address,
        "items": request.items,
        "status": request.status,
        "expired_at": request.expired_at,
    }


def _get_quote(request_uuid: str, quote_uuid: str) -> Dict[str, Any]:
    from .quote import get_quote, get_quote_count

    count = get_quote_count(request_uuid, quote_uuid)
    if count == 0:
        return {}

    quote = get_quote(request_uuid, quote_uuid)

    return {
        "request": _get_request(quote.endpoint_id, quote.request_uuid),
        "quote_uuid": quote.quote_uuid,
        "provider_corp_external_id": quote.provider_corp_external_id,
        "sales_rep_email": quote.sales_rep_email,
        "shipping_method": quote.shipping_method,
        "shipping_amount": quote.shipping_amount,
        "total_quote_amount": quote.total_quote_amount,
        "total_quote_discount": quote.total_quote_discount,
        "final_total_quote_amount": quote.final_total_quote_amount,
        "notes": quote.notes,
        "status": quote.status,
    }


def _validate_item_exists(endpoint_id: str, item_uuid: str) -> bool:
    """Validate if an item exists in the database."""
    from .item import get_item_count

    return get_item_count(endpoint_id, item_uuid) > 0


def _validate_provider_item_exists(endpoint_id: str, provider_item_uuid: str) -> bool:
    """Validate if a provider item exists in the database."""
    from .provider_item import get_provider_item_count

    return get_provider_item_count(endpoint_id, provider_item_uuid) > 0


def _validate_batch_exists(provider_item_uuid: str, batch_no: str) -> bool:
    """Validate if a batch exists for a given provider item."""
    from .provider_item_batches import get_provider_item_batch_count

    return get_provider_item_batch_count(provider_item_uuid, batch_no) > 0


def _combine_all_discount_prompts(
    endpoint_id: str,
    email: str,
    quote_items: List[Dict[str, Any]],
    loaders: Any,
) -> Any:
    """
    Combine discount prompts from all hierarchical scopes and deduplicate.

    This function implements a sophisticated multi-level discount prompt loading strategy:
    1. GLOBAL scope - applies to all quotes for this endpoint
    2. SEGMENT scope - applies to customers in a specific segment (via email lookup)
    3. ITEM scope - applies to specific catalog items
    4. PROVIDER_ITEM scope - applies to specific provider offerings

    The loading happens in two stages:
    Stage 1: Load segment_contact to get segment_uuid from request email
    Stage 2: Load all discount prompts in parallel and merge

    Args:
        endpoint_id: The tenant/endpoint identifier
        email: Customer email for segment lookup (can be None)
        quote_items: List of quote items to determine ITEM and PROVIDER_ITEM scopes
        loaders: RequestLoaders instance containing all batch loaders

    Returns:
        Promise that resolves to combined list of discount prompts
    """

    def normalize_to_json(obj):
        """Normalize object to JSON-serializable dict."""
        return Utility.json_normalize(obj) if obj else {}

    # Track which prompts we've already added to prevent duplicates
    # (same prompt might be returned by multiple loaders due to hierarchical nature)
    seen_uuids = set()

    # STEP 1: Load GLOBAL prompts (always included)
    # Global prompts apply to all quotes for this endpoint
    global_promise = loaders.discount_prompt_global_loader.load(endpoint_id)

    # STEP 2: Look up segment via email
    # email → segment_contact → segment_uuid
    segment_contact_promise = None
    if email:
        # Load segment_contact by (endpoint_id, email) to get segment_uuid
        segment_contact_promise = loaders.segment_contact_loader.load(
            (endpoint_id, email)
        )

    # STEP 3: Collect unique items and provider items from quote
    # We'll use these to determine which ITEM and PROVIDER_ITEM prompts to load
    item_promises = []
    provider_item_promises = []
    if quote_items:
        unique_item_uuids = set()
        unique_provider_items = set()

        # Single pass through quote items to collect unique identifiers
        for qi in quote_items:
            item_uuid = qi.get("item_uuid")
            provider_item_uuid = qi.get("provider_item_uuid")

            # Track unique items for ITEM scope prompts
            if item_uuid:
                unique_item_uuids.add(item_uuid)

            # Track unique (item, provider) pairs for PROVIDER_ITEM scope prompts
            if item_uuid and provider_item_uuid:
                unique_provider_items.add((item_uuid, provider_item_uuid))

        # Load ITEM scope prompts for each unique item in the quote
        # Note: ItemLoader automatically includes GLOBAL prompts (via dependency injection)
        for item_uuid in unique_item_uuids:
            item_promises.append(
                loaders.discount_prompt_by_item_loader.load((endpoint_id, item_uuid))
            )

        # Load PROVIDER_ITEM scope prompts for each unique provider item
        # Note: ProviderItemLoader automatically includes GLOBAL prompts
        for item_uuid, provider_item_uuid in unique_provider_items:
            provider_item_promises.append(
                loaders.discount_prompt_by_provider_item_loader.load(
                    (endpoint_id, item_uuid, provider_item_uuid)
                )
            )

    def load_segment_prompts_and_merge(segment_contact):
        """
        After segment_contact is loaded, load segment prompts and merge all scopes.

        This nested function is called as a Promise callback after segment_contact
        is resolved. It conditionally loads SEGMENT prompts if a segment_uuid exists,
        then combines all prompts from all scopes and deduplicates.

        Args:
            segment_contact: Dict with segment_uuid, or None if no segment found

        Returns:
            Promise that resolves to merged and deduplicated prompt list
        """
        # Start with GLOBAL prompts (always included)
        promises_to_resolve = [global_promise]

        # STEP 4: Conditionally load SEGMENT prompts
        # Only if we found a segment_contact and it has a segment_uuid
        if segment_contact and segment_contact.get("segment_uuid"):
            segment_uuid = segment_contact["segment_uuid"]
            # Load SEGMENT scope prompts (includes GLOBAL via dependency injection)
            segment_promise = loaders.discount_prompt_by_segment_loader.load(
                (endpoint_id, segment_uuid)
            )
            promises_to_resolve.append(segment_promise)

        # STEP 5: Add ITEM and PROVIDER_ITEM scope promises
        # These were prepared earlier based on quote items
        promises_to_resolve.extend(item_promises)
        promises_to_resolve.extend(provider_item_promises)

        def merge_prompts(prompt_lists):
            """
            Merge all prompt lists and deduplicate by discount_prompt_uuid.

            Each loader may return overlapping prompts due to hierarchical nature
            (e.g., ItemLoader includes GLOBAL prompts). We deduplicate to ensure
            each prompt appears only once in the final result.

            Args:
                prompt_lists: List of lists, where each inner list is prompts
                             from one scope (GLOBAL, SEGMENT, ITEM, PROVIDER_ITEM)

            Returns:
                Deduplicated list of normalized prompt dicts
            """
            merged = []
            # Iterate through all prompt lists (one per scope)
            for prompt_list in prompt_lists:
                # Handle None/empty lists gracefully
                for prompt in prompt_list or []:
                    prompt_uuid = prompt.get("discount_prompt_uuid")
                    # Only add if we haven't seen this prompt before
                    if prompt_uuid and prompt_uuid not in seen_uuids:
                        seen_uuids.add(prompt_uuid)
                        # Normalize to ensure consistent JSON format
                        merged.append(normalize_to_json(prompt))
            return merged

        # Load all scopes in parallel (GLOBAL, SEGMENT, ITEM, PROVIDER_ITEM)
        # then merge and deduplicate the results
        return Promise.all(promises_to_resolve).then(merge_prompts)

    # STEP 6: Chain promises - segment lookup THEN prompt loading
    # We need segment_uuid before we can load SEGMENT prompts, so we chain:
    # segment_contact_promise.then(load_segment_prompts_and_merge)
    if segment_contact_promise:
        # Chain: resolve segment_contact first, then load prompts
        return segment_contact_promise.then(load_segment_prompts_and_merge)
    else:
        # No email in request, skip segment lookup and proceed directly
        return load_segment_prompts_and_merge(None)
