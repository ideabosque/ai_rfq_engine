# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict


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
