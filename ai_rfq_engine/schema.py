#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import time
from typing import Any, Dict

from graphene import (
    Boolean,
    DateTime,
    Field,
    Int,
    List,
    ObjectType,
    ResolveInfo,
    String,
)

from .mutations import (
    DeleteComment,
    DeleteFile,
    DeleteInstallment,
    DeleteItem,
    DeleteProduct,
    DeleteQuote,
    DeleteQuoteItemProduct,
    DeleteQuoteService,
    DeleteRequest,
    DeleteService,
    DeleteServiceProvider,
    InsertUpdateComment,
    InsertUpdateFile,
    InsertUpdateInstallment,
    InsertUpdateItem,
    InsertUpdateProduct,
    InsertUpdateQuote,
    InsertUpdateQuoteItemProduct,
    InsertUpdateQuoteService,
    InsertUpdateRequest,
    InsertUpdateService,
    InsertUpdateServiceProvider,
)
from .queries import (
    resolve_comment,
    resolve_comment_list,
    resolve_file,
    resolve_file_list,
    resolve_installment,
    resolve_installment_list,
    resolve_item,
    resolve_item_list,
    resolve_product,
    resolve_product_list,
    resolve_quote,
    resolve_quote_item_product,
    resolve_quote_item_product_list,
    resolve_quote_list,
    resolve_quote_service,
    resolve_quote_service_list,
    resolve_request,
    resolve_request_list,
    resolve_service,
    resolve_service_list,
    resolve_service_provider,
    resolve_service_provider_list,
)
from .types import (
    CommentListType,
    CommentType,
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


def type_class():
    return [
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
        ServiceListType,
        ServiceProviderListType,
        ServiceProviderType,
        ServiceType,
    ]


class Query(ObjectType):
    ping = String()

    service = Field(
        ServiceType,
        service_type=String(required=True),
        service_id=String(required=True),
    )

    service_list = Field(
        ServiceListType,
        page_number=Int(),
        limit=Int(),
        service_type=String(),
        service_name=String(),
        service_description=String(),
    )

    service_provider = Field(
        ServiceProviderType,
        service_id=String(required=True),
        provider_id=String(required=True),
    )

    service_provider_list = Field(
        ServiceProviderListType,
        page_number=Int(),
        limit=Int(),
        service_id=String(),
        service_types=List(String),
    )

    item = Field(
        ItemType,
        item_type=String(required=True),
        item_id=String(required=True),
    )

    item_list = Field(
        ItemListType,
        page_number=Int(),
        limit=Int(),
        item_type=String(),
        item_name=String(),
        item_description=String(),
    )

    product = Field(
        ProductType,
        provider_id=String(required=True),
        product_id=String(required=True),
    )

    product_list = Field(
        ProductListType,
        page_number=Int(),
        limit=Int(),
        provider_id=String(),
        sku=String(),
        product_name=String(),
        product_description=String(),
    )

    request = Field(
        RequestType,
        required=True,
        customer_id=String(required=True),  # user_id of the requestor
        request_id=String(required=True),
    )

    request_list = Field(
        RequestListType,
        page_number=Int(),
        limit=Int(),
        customer_id=String(),
        title=String(),
        description=String(),
    )

    quote = Field(
        QuoteType,
        required=True,
        request_id=String(required=True),  # request_id of the quote
        quote_id=String(required=True),
    )

    quote_list = Field(
        QuoteListType,
        page_number=Int(),
        limit=Int(),
        request_id=String(),
        provider_id=String(),
        customer_id=String(),
        shipping_methods=List(String),
        statuses=List(String),
    )

    quote_service = Field(
        QuoteServiceType,
        required=True,
        quote_id=String(required=True),  # quote_id of the quote
        service_id=String(required=True),
    )

    quote_service_list = Field(
        QuoteServiceListType,
        page_number=Int(),
        limit=Int(),
        quote_id=String(),
        service_ids=List(String),
        service_types=List(String),
    )

    quote_item_product = Field(
        QuoteItemProductType,
        required=True,
        quote_id=String(required=True),  # quote_id of the quote
        item_id=String(required=True),
    )

    quote_item_product_list = Field(
        QuoteItemProductListType,
        page_number=Int(),
        limit=Int(),
        quote_id=String(),
        item_types=List(String),
        product_ids=List(String),
        provider_ids=List(String),
    )

    installment = Field(
        InstallmentType,
        required=True,
        quote_id=String(required=True),  # quote_id of the quote
        installment_id=String(required=True),
    )

    installment_list = Field(
        InstallmentListType,
        page_number=Int(),
        limit=Int(),
        quote_id=String(),
        request_id=String(),
        priorities=List(String),
        salesorder_nos=List(String),
        scheduled_date_from=DateTime(),
        scheduled_date_to=DateTime(),
        statuses=List(String),
    )

    comment = Field(
        CommentType,
        required=True,
        request_id=String(required=True),
        timestamp=String(required=True),
    )

    comment_list = Field(
        CommentListType,
        page_number=Int(),
        limit=Int(),
        request_id=String(),
        user_id=String(),
        user_types=List(String),
        comment=String(),
    )

    file = Field(
        FileType,
        required=True,
        request_id=String(required=True),
        name=String(required=True),
    )

    file_list = Field(
        FileListType,
        page_number=Int(),
        limit=Int(),
        request_id=String(),
        user_id=String(),
        user_types=List(String),
        path=String(),
    )

    def resolve_ping(self, info: ResolveInfo) -> str:
        return f"Hello at {time.strftime('%X')}!!"

    def resolve_service(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ServiceType:
        return resolve_service(info, **kwargs)

    def resolve_service_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ServiceListType:
        return resolve_service_list(info, **kwargs)

    def resolve_service_provider(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ServiceProviderType:
        return resolve_service_provider(info, **kwargs)

    def resolve_service_provider_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ServiceProviderListType:
        return resolve_service_provider_list(info, **kwargs)

    def resolve_item(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
        return resolve_item(info, **kwargs)

    def resolve_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemListType:
        return resolve_item_list(info, **kwargs)

    def resolve_product(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProductType:
        return resolve_product(info, **kwargs)

    def resolve_product_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProductListType:
        return resolve_product_list(info, **kwargs)

    def resolve_request(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestType:
        return resolve_request(info, **kwargs)

    def resolve_request_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestListType:
        return resolve_request_list(info, **kwargs)

    def resolve_quote(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
        return resolve_quote(info, **kwargs)

    def resolve_quote_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteListType:
        return resolve_quote_list(info, **kwargs)

    def resolve_quote_service(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteServiceType:
        return resolve_quote_service(info, **kwargs)

    def resolve_quote_service_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteServiceListType:
        return resolve_quote_service_list(info, **kwargs)

    def resolve_quote_item_product(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemProductType:
        return resolve_quote_item_product(info, **kwargs)

    def resolve_quote_item_product_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemProductListType:
        return resolve_quote_item_product_list(info, **kwargs)

    def resolve_installment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentType:
        return resolve_installment(info, **kwargs)

    def resolve_installment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentListType:
        return resolve_installment_list(info, **kwargs)

    def resolve_comment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> CommentType:
        return resolve_comment(info, **kwargs)

    def resolve_comment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> CommentListType:
        return resolve_comment_list(info, **kwargs)

    def resolve_file(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
        return resolve_file(info, **kwargs)

    def resolve_file_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FileListType:
        return resolve_file_list(info, **kwargs)


class Mutations(ObjectType):
    insert_update_service = InsertUpdateService.Field()
    delete_service = DeleteService.Field()
    insert_update_service_provider = InsertUpdateServiceProvider.Field()
    delete_service_provider = DeleteServiceProvider.Field()
    insert_update_item = InsertUpdateItem.Field()
    delete_item = DeleteItem.Field()
    insert_update_product = InsertUpdateProduct.Field()
    delete_product = DeleteProduct.Field()
    insert_update_request = InsertUpdateRequest.Field()
    delete_request = DeleteRequest.Field()
    insert_update_quote = InsertUpdateQuote.Field()
    delete_quote = DeleteQuote.Field()
    insert_update_quote_service = InsertUpdateQuoteService.Field()
    delete_quote_service = DeleteQuoteService.Field()
    insert_update_quote_item_product = InsertUpdateQuoteItemProduct.Field()
    delete_quote_item_product = DeleteQuoteItemProduct.Field()
    insert_update_installment = InsertUpdateInstallment.Field()
    delete_installment = DeleteInstallment.Field()
    insert_update_comment = InsertUpdateComment.Field()
    delete_comment = DeleteComment.Field()
    insert_update_file = InsertUpdateFile.Field()
    delete_file = DeleteFile.Field()
