#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from .handlers import (
    resolve_file_handler,
    resolve_file_list_handler,
    resolve_installment_handler,
    resolve_installment_list_handler,
    resolve_item_handler,
    resolve_item_list_handler,
    resolve_product_handler,
    resolve_product_list_handler,
    resolve_quote_handler,
    resolve_quote_item_product_handler,
    resolve_quote_item_product_list_handler,
    resolve_quote_list_handler,
    resolve_quote_service_handler,
    resolve_quote_service_list_handler,
    resolve_request_handler,
    resolve_request_list_handler,
    resolve_service_handler,
    resolve_service_list_handler,
    resolve_service_provider_handler,
    resolve_service_provider_list_handler,
)
from .types import (
    FileListType,
    FileType,
    InstallmentListType,
    InstallmentType,
    ItemListType,
    ItemType,
    ProductListType,
    ProductType,
    QuoteItemProductListType,
    QuoteItemProductType,
    QuoteListType,
    QuoteServiceListType,
    QuoteServiceType,
    QuoteType,
    RequestListType,
    RequestType,
    ServiceListType,
    ServiceProviderListType,
    ServiceProviderType,
    ServiceType,
)


def resolve_service(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ServiceType:
    return resolve_service_handler(info, **kwargs)


def resolve_service_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceListType:
    return resolve_service_list_handler(info, **kwargs)


def resolve_service_provider(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceProviderType:
    return resolve_service_provider_handler(info, **kwargs)


def resolve_service_provider_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceProviderListType:
    return resolve_service_provider_list_handler(info, **kwargs)


def resolve_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
    return resolve_item_handler(info, **kwargs)


def resolve_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemListType:
    return resolve_item_list_handler(info, **kwargs)


def resolve_product(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ProductType:
    return resolve_product_handler(info, **kwargs)


def resolve_product_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProductListType:
    return resolve_product_list_handler(info, **kwargs)


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return resolve_request_handler(info, **kwargs)


def resolve_request_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> RequestListType:
    return resolve_request_list_handler(info, **kwargs)


def resolve_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
    return resolve_quote_handler(info, **kwargs)


def resolve_quote_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteListType:
    return resolve_quote_list_handler(info, **kwargs)


def resolve_quote_service(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteServiceType:
    return resolve_quote_service_handler(info, **kwargs)


def resolve_quote_service_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteServiceListType:
    return resolve_quote_service_list_handler(info, **kwargs)


def resolve_quote_item_product(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemProductType:
    return resolve_quote_item_product_handler(info, **kwargs)


def resolve_quote_item_product_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemProductListType:
    return resolve_quote_item_product_list_handler(info, **kwargs)


def resolve_installment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> InstallmentType:
    return resolve_installment_handler(info, **kwargs)


def resolve_installment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentListType:
    return resolve_installment_list_handler(info, **kwargs)


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
    return resolve_file_handler(info, **kwargs)


def resolve_file_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileListType:
    return resolve_file_list_handler(info, **kwargs)
