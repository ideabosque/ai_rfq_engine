#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import (
    Boolean,
    DateTime,
    Decimal,
    Field,
    Float,
    Int,
    List,
    ObjectType,
    String,
)
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON


class ServiceType(ObjectType):
    service_type = String()
    service_id = String()
    service_name = String()
    service_description = String()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class ServiceProviderType(ObjectType):
    service = JSON()
    provider_id = String()
    service_spec = JSON()
    uom = String()
    base_price_per_uom = Float()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class ItemType(ObjectType):
    item_type = String()
    item_id = String()
    item_name = String()
    item_description = String()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class ProductType(ObjectType):
    provider_id = String()
    product_id = String()
    sku = String()
    product_name = String()
    product_description = String()
    uom = String()
    base_price_per_uom = Float()
    data = JSON()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class RequestType(ObjectType):
    customer_id = String()
    request_id = String()
    title = String()
    description = String()
    items = List(JSON)
    services = List(JSON)
    status = String()
    expired_at = DateTime()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class QuoteType(ObjectType):
    request = JSON()
    quote_id = String()
    provider_id = String()
    billing_address = JSON()
    shipping_address = JSON()
    shipping_method = String()
    shipping_amount = Float()
    total_amount = Float()
    status = String()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class QuoteServiceType(ObjectType):
    quote_id = String()
    service_provider = JSON()
    request_data = JSON()
    data = JSON()
    price_per_uom = Float()
    qty = Float()
    subtotal = Float()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class QuoteItemProductType(ObjectType):
    quote_id = String()
    item = JSON()
    request_data = JSON()
    product = JSON()
    price_per_uom = Float()
    qty = Float()
    subtotal = Float()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class InstallmentType(ObjectType):
    quote = JSON()
    installment_id = String()
    priority = String()
    salesorder_no = String()
    scheduled_date = DateTime()
    installment_ratio = Float()
    installment_amount = Float()
    status = String()
    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()


class CommentType(ObjectType):
    request_id = String()
    timestamp = String()
    user_id = String()
    user_type = String()
    comment = String()
    updated_at = DateTime()


class FileType(ObjectType):
    request_id = String()
    name = String()
    user_id = String()
    user_type = String()
    path = String()
    created_at = DateTime()
    updated_at = DateTime()


class ServiceListType(ListObjectType):
    service_list = List(ServiceType)


class ServiceProviderListType(ListObjectType):
    service_provider_list = List(ServiceProviderType)


class ItemListType(ListObjectType):
    item_list = List(ItemType)


class ProductListType(ListObjectType):
    product_list = List(ProductType)


class RequestListType(ListObjectType):
    request_list = List(RequestType)


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)


class QuoteServiceListType(ListObjectType):
    quote_service_list = List(QuoteServiceType)


class QuoteItemProductListType(ListObjectType):
    quote_item_product_list = List(QuoteItemProductType)


class InstallmentListType(ListObjectType):
    installment_list = List(InstallmentType)


class CommentListType(ListObjectType):
    comment_list = List(CommentType)


class FileListType(ListObjectType):
    file_list = List(FileType)
