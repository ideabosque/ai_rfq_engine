# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

from promise import Promise

from ..utils.normalization import normalize_to_json


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


def _get_request(partition_key: str, request_uuid: str) -> Dict[str, Any]:
    from .request import get_request, get_request_count

    count = get_request_count(partition_key, request_uuid)
    if count == 0:
        return {}

    request = get_request(partition_key, request_uuid)

    return {
        "partition_key": request.partition_key,
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
        "request": _get_request(quote.partition_key, quote.request_uuid),
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


def _validate_item_exists(partition_key: str, item_uuid: str) -> bool:
    """Validate if an item exists in the database."""
    from .item import get_item_count

    return get_item_count(partition_key, item_uuid) > 0


def _validate_provider_item_exists(partition_key: str, provider_item_uuid: str) -> bool:
    """Validate if a provider item exists in the database."""
    from .provider_item import get_provider_item_count

    return get_provider_item_count(partition_key, provider_item_uuid) > 0


def _validate_batch_exists(provider_item_uuid: str, batch_no: str) -> bool:
    """Validate if a batch exists for a given provider item."""
    from .provider_item_batches import get_provider_item_batch_count

    return get_provider_item_batch_count(provider_item_uuid, batch_no) > 0


def _combine_all_discount_prompts(
    partition_key: str,
    email: str,
    quote_items: List[Dict[str, Any]],
    loaders: Any,
) -> Any:
    """
    Combine discount prompts from all hierarchical scopes and deduplicate.

    This function implements a sophisticated multi-level discount prompt loading strategy:
    1. GLOBAL scope - applies to all quotes for this partition
    2. SEGMENT scope - applies to customers in a specific segment (via email lookup)
    3. ITEM scope - applies to specific catalog items
    4. PROVIDER_ITEM scope - applies to specific provider offerings

    The loading happens in two stages:
    Stage 1: Load segment_contact to get segment_uuid from request email
    Stage 2: Load all discount prompts in parallel and merge

    Args:
        partition_key: The tenant/partition identifier
        email: Customer email for segment lookup (can be None)
        quote_items: List of quote items to determine ITEM and PROVIDER_ITEM scopes
        loaders: RequestLoaders instance containing all batch loaders

    Returns:
        Promise that resolves to combined list of discount prompts
    """

    # Track which prompts we've already added to prevent duplicates
    # (same prompt might be returned by multiple loaders due to hierarchical nature)
    seen_uuids = set()

    # STEP 1: Load GLOBAL prompts (always included)
    # Global prompts apply to all quotes for this partition
    global_promise = loaders.discount_prompt_global_loader.load(partition_key)

    # STEP 2: Look up segment via email
    # email → segment_contact → segment_uuid
    segment_contact_promise = None
    if email:
        # Load segment_contact by (partition_key, email) to get segment_uuid
        segment_contact_promise = loaders.segment_contact_loader.load(
            (partition_key, email)
        )

    # STEP 3: Collect unique items and provider items from quote
    # We'll use these to determine which ITEM and PROVIDER_ITEM prompts to load
    item_promises = []
    provider_item_promises = []
    unique_item_uuids = set()
    unique_provider_items = set()

    if quote_items:
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
                loaders.discount_prompt_by_item_loader.load((partition_key, item_uuid))
            )

        # Load PROVIDER_ITEM scope prompts for each unique provider item
        # Note: ProviderItemLoader automatically includes GLOBAL prompts
        for item_uuid, provider_item_uuid in unique_provider_items:
            provider_item_promises.append(
                loaders.discount_prompt_by_provider_item_loader.load(
                    (partition_key, item_uuid, provider_item_uuid)
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
                (partition_key, segment_uuid)
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


def _combine_all_item_price_tiers(
    partition_key: str,
    email: str,
    quote_items: List[Dict[str, Any]],
    loaders: Any,
) -> Any:
    """
    Combine item price tiers for quote items using batch loaders.

    This function implements a multi-stage loading strategy:
    1. Look up segment_uuid from email via segment_contact_loader
    2. Load price tiers for each item/provider_item combination (filtered by segment at DB level)
    3. Filter tiers based on quantity thresholds
    4. Return tier models for conversion at the query layer

    Args:
        partition_key: The tenant/partition identifier
        email: Customer email for segment lookup (can be None)
        quote_items: List of quote items to determine which price tiers to load
        loaders: RequestLoaders instance containing all batch loaders

    Returns:
        Promise that resolves to list of ItemPriceTierModel instances (as dicts)
    """
    from promise import Promise

    from .item_price_tier import ItemPriceTierModel

    # STEP 1: Load segment_contact to get segment_uuid from email
    def process_with_segment(segment_contact):
        """Process price tiers after segment lookup."""
        seg_uuid = segment_contact.get("segment_uuid") if segment_contact else None

        # STEP 2: Prepare to load price tiers for each quote item
        # Group items by (item_uuid, provider_item_uuid) to avoid duplicate loads
        item_keys = set()
        item_data_map = {}  # Map keys to item data for later processing

        for item in quote_items:
            item_uuid = item.get("item_uuid")
            provider_item_uuid = item.get("provider_item_uuid")

            if item_uuid and provider_item_uuid:
                key = (item_uuid, provider_item_uuid)
                item_keys.add(key)
                # Store item data for quantity filtering
                if key not in item_data_map:
                    item_data_map[key] = []
                item_data_map[key].append(item)

        # STEP 3: Load all price tiers in parallel using batch loader with segment filtering
        tier_promises = []
        key_list = list(item_keys)
        for item_uuid, provider_item_uuid in key_list:
            # Pass segment_uuid to the loader for efficient database-level filtering
            tier_promises.append(
                loaders.item_price_tier_by_provider_item_loader.load(
                    (item_uuid, provider_item_uuid, seg_uuid)
                )
            )

        def process_tiers(all_tier_lists):
            """Process loaded price tiers and apply filtering/pricing logic."""
            result_tiers = []

            # Process each (item_uuid, provider_item_uuid) group
            for idx, tier_list in enumerate(all_tier_lists):
                if not tier_list:
                    continue

                key = key_list[idx]
                items_for_key = item_data_map.get(key, [])

                # Process each item instance for this key
                for item in items_for_key:
                    item_qty = item.get("qty", 0)

                    # STEP 4: Filter tiers by quantity
                    # The segment_uuid filtering is now handled by the batch loader
                    # Find tiers where quantity_greater_then <= item_qty < quantity_less_then
                    for tier_dict in tier_list:
                        qty_greater = tier_dict.get("quantity_greater_then", 0)
                        qty_less = tier_dict.get("quantity_less_then", float("inf"))

                        # Check if this tier applies to the item quantity
                        if qty_greater <= item_qty < qty_less:
                            # STEP 5: Convert dict to model for query layer processing
                            # The query layer will handle conversion to ItemPriceTierType
                            tier_model = ItemPriceTierModel()
                            tier_model.attribute_values = tier_dict
                            result_tiers.append(tier_model)

            return result_tiers

        # If no items to process, return empty list
        if not tier_promises:
            return Promise.resolve([])

        # Load all tiers and process them
        return Promise.all(tier_promises).then(process_tiers)

    # Start by loading segment contact
    if email:
        return loaders.segment_contact_loader.load((partition_key, email)).then(
            process_with_segment
        )
    else:
        # No email, process without segment
        return process_with_segment(None)
