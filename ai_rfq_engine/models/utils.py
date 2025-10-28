# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict


def _initialize_tables(logger: logging.Logger) -> None:
    from .discount_rule import create_discount_rule_table
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
    create_discount_rule_table(logger)
    return


def _get_item(endpoint_id: str, item_uuid: str) -> Dict[str, Any]:
    from .item import get_item

    item = get_item(endpoint_id, item_uuid)

    return {
        "endpoint_id": item.endpoint_id,
        "item_uuid": item.item_uuid,
        "item_type": item.item_type,
        "item_name": item.item_name,
        "item_description": item.item_description,
        "uom": item.uom,
    }


def _get_segment(endpoint_id: str, segment_uuid: str) -> Dict[str, Any]:
    from .segment import get_segment

    segment = get_segment(endpoint_id, segment_uuid)

    return {
        "endpoint_id": segment.endpoint_id,
        "segment_uuid": segment.segment_uuid,
        "provider_corp_external_id": segment.provider_corp_external_id,
        "segment_name": segment.segment_name,
        "segment_description": segment.segment_description,
    }


def _get_provider_item(endpoint_id: str, provider_item_uuid: str) -> Dict[str, Any]:
    from .provider_item import get_provider_item

    provider_item = get_provider_item(endpoint_id, provider_item_uuid)

    return {
        "endpoint_id": provider_item.endpoint_id,
        "provider_item_uuid": provider_item.provider_item_uuid,
        "item": _get_item(provider_item.endpoint_id, provider_item.item_uuid),
        "provider_corp_external_id": provider_item.provider_corp_external_id,
        "external_id": provider_item.provider_item_external_id,
        "base_price_per_uom": provider_item.base_price_per_uom,
        "item_spec": provider_item.item_spec,
    }


def _get_request(endpoint_id: str, request_uuid: str) -> Dict[str, Any]:
    from .request import get_request

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
        "total_amount": request.total_amount,
        "total_discount": request.total_discount,
        "final_total_amount": request.final_total_amount,
        "status": request.status,
        "expired_at": request.expired_at,
    }


def _get_quote(request_uuid: str, quote_uuid: str) -> Dict[str, Any]:
    from .quote import get_quote

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
