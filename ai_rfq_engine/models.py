#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import os

from pynamodb.attributes import (
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.indexes import AllProjection, LocalSecondaryIndex

from silvaengine_dynamodb_base import BaseModel


class ServiceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-services"

    service_type = UnicodeAttribute(hash_key=True)
    service_id = UnicodeAttribute(range_key=True)
    service_name = UnicodeAttribute()
    service_description = UnicodeAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class ServiceProviderModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-service_providers"

    service_id = UnicodeAttribute(hash_key=True)
    provider_id = UnicodeAttribute(range_key=True)
    service_type = UnicodeAttribute()
    service_spec = MapAttribute(default={})
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class ItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-items"

    item_type = UnicodeAttribute(hash_key=True)
    item_id = UnicodeAttribute(range_key=True)
    item_name = UnicodeAttribute()
    item_description = UnicodeAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class SkuIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "sku-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    provider_id = UnicodeAttribute(hash_key=True)
    sku = UnicodeAttribute(range_key=True)


class ProductModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-products"

    provider_id = UnicodeAttribute(hash_key=True)
    product_id = UnicodeAttribute(range_key=True)
    sku = UnicodeAttribute()
    product_name = UnicodeAttribute()
    product_description = UnicodeAttribute()
    uom = UnicodeAttribute()
    base_price_per_uom = NumberAttribute()
    data = MapAttribute(default={})
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    sku_index = SkuIndex()


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-requests"

    user_id = UnicodeAttribute(hash_key=True)
    request_id = UnicodeAttribute(range_key=True)
    title = UnicodeAttribute()
    description = UnicodeAttribute()
    items = ListAttribute(default=[])
    services = ListAttribute(default=[])
    status = UnicodeAttribute(default="initial")
    expired_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class ProviderIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "provider_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    request_id = UnicodeAttribute(hash_key=True)
    provider_id = UnicodeAttribute(range_key=True)


class CustomerIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "customer_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    request_id = UnicodeAttribute(hash_key=True)
    customer_id = UnicodeAttribute(range_key=True)


class QuoteModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quotes"

    request_id = UnicodeAttribute(hash_key=True)
    quote_id = UnicodeAttribute(range_key=True)
    provider_id = UnicodeAttribute()
    customer_id = UnicodeAttribute()
    installments = ListAttribute(default=[])
    billing_address = MapAttribute(default={})
    shipping_address = MapAttribute(default={})
    shipping_method = UnicodeAttribute(null=True)
    shipping_amount = NumberAttribute(null=True)
    total_amount = NumberAttribute(null=True)
    status = UnicodeAttribute(default="initial")
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_id_index = ProviderIdIndex()
    customer_id_index = CustomerIdIndex()


class QuoteServiceModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quote_services"

    quote_id = UnicodeAttribute(hash_key=True)
    service_id = UnicodeAttribute(range_key=True)
    service_type = UnicodeAttribute()
    service_name = UnicodeAttribute()
    request_data = MapAttribute(default={})
    data = MapAttribute(default={})
    uom = UnicodeAttribute()
    price_per_uom = NumberAttribute()
    qty = NumberAttribute()
    subtotal = NumberAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class QuoteItemProductModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-quote_items_products"

    quote_id = UnicodeAttribute(hash_key=True)
    item_id = UnicodeAttribute(range_key=True)
    item_type = UnicodeAttribute()
    request_data = MapAttribute(default={})
    product_id = UnicodeAttribute()
    provider_id = UnicodeAttribute()
    price_per_uom = NumberAttribute()
    qty = NumberAttribute()
    subtotal = NumberAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class InstallmentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-installments"

    quote_id = UnicodeAttribute(hash_key=True)
    installment_id = UnicodeAttribute(range_key=True)
    request_id = UnicodeAttribute()
    priority = UnicodeAttribute()
    salesorder_no = UnicodeAttribute()
    scheduled_date = UTCDateTimeAttribute()
    installment_ratio = NumberAttribute()
    installment_amount = NumberAttribute()
    status = UnicodeAttribute()
    updated_by = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()


class CommentUserIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "user_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    request_id = UnicodeAttribute(hash_key=True)
    user_id = UnicodeAttribute(range_key=True)


class CommentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-comments"

    request_id = UnicodeAttribute(hash_key=True)
    timestamp = UnicodeAttribute(range_key=True)
    user_id = UnicodeAttribute()
    user_type = UnicodeAttribute()
    comment = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    user_id_index = CommentUserIdIndex()


class FileUserIdIndex(LocalSecondaryIndex):
    class Meta:
        # index_name is optional, but can be provided to override the default name
        index_name = "user_id-index"
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()

    # This attribute is the hash key for the index
    # Note that this attribute must also exist
    # in the model
    request_id = UnicodeAttribute(hash_key=True)
    user_id = UnicodeAttribute(range_key=True)


class FileModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-files"

    request_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute(range_key=True)
    user_id = UnicodeAttribute()
    user_type = UnicodeAttribute()
    path = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    user_id_index = FileUserIdIndex()
