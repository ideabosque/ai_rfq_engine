#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from .handlers import (
    resolve_comment_handler,
    resolve_comment_list_handler,
    resolve_file_handler,
    resolve_file_list_handler,
    resolve_installment_handler,
    resolve_installment_list_handler,
    resolve_quote_handler,
    resolve_quote_item_product_handler,
    resolve_quote_item_product_list_handler,
    resolve_quote_list_handler,
    resolve_quote_service_handler,
    resolve_quote_service_list_handler,
    resolve_request_handler,
    resolve_request_list_handler,
)
from .types import (
    CommentListType,
    CommentType,
    FileListType,
    FileType,
    InstallmentListType,
    InstallmentType,
    QuoteItemProductListType,
    QuoteItemProductType,
    QuoteListType,
    QuoteServiceListType,
    QuoteServiceType,
    QuoteType,
    RequestListType,
    RequestType,
)


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


def resolve_comment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> CommentType:
    return resolve_comment_handler(info, **kwargs)


def resolve_comment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> CommentListType:
    return resolve_comment_list_handler(info, **kwargs)


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
    return resolve_file_handler(info, **kwargs)


def resolve_file_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileListType:
    return resolve_file_list_handler(info, **kwargs)
