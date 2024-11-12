#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Float, Int, List, Mutation, String
from silvaengine_utility import JSON

from .handlers import (
    delete_file_handler,
    delete_installment_handler,
    delete_item_handler,
    delete_product_handler,
    delete_quote_handler,
    delete_quote_item_product_handler,
    delete_quote_service_handler,
    delete_request_handler,
    delete_service_handler,
    delete_service_provider_handler,
    insert_update_file_handler,
    insert_update_installment_handler,
    insert_update_item_handler,
    insert_update_product_handler,
    insert_update_quote_handler,
    insert_update_quote_item_product_handler,
    insert_update_quote_service_handler,
    insert_update_request_handler,
    insert_update_service_handler,
    insert_update_service_provider_handler,
)
from .types import (
    FileType,
    InstallmentType,
    ItemType,
    ProductType,
    QuoteItemProductType,
    QuoteServiceType,
    QuoteType,
    RequestType,
    ServiceProviderType,
    ServiceType,
)


class InsertUpdateService(Mutation):
    service = Field(ServiceType)

    class Arguments:
        service_type = String(required=True)
        service_id = String(required=False)
        service_name = String(required=False)
        service_description = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateService":
        try:
            service = insert_update_service_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateService(service=service)


class DeleteService(Mutation):
    ok = Boolean()

    class Arguments:
        service_type = String(required=True)
        service_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteService":
        try:
            ok = delete_service_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteService(ok=ok)


class InsertUpdateServiceProvider(Mutation):
    service_provider = Field(ServiceProviderType)

    class Arguments:
        service_id = String(required=True)
        provider_id = String(required=True)
        service_type = String(required=False)
        service_spec = JSON(required=False)
        uom = String(required=False)
        base_price_per_uom = Float(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateServiceProvider":
        try:
            service_provider = insert_update_service_provider_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateServiceProvider(service_provider=service_provider)


class DeleteServiceProvider(Mutation):
    ok = Boolean()

    class Arguments:
        service_id = String(required=True)
        provider_id = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteServiceProvider":
        try:
            ok = delete_service_provider_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteServiceProvider(ok=ok)


class InsertUpdateItem(Mutation):
    item = Field(ItemType)

    class Arguments:
        item_type = String(required=True)
        item_id = String(required=False)
        item_name = String(required=False)
        item_description = String(required=False)
        uom = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateItem":
        try:
            item = insert_update_item_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateItem(item=item)


class DeleteItem(Mutation):
    ok = Boolean()

    class Arguments:
        item_type = String(required=True)
        item_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteItem":
        try:
            ok = delete_item_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteItem(ok=ok)


class InsertUpdateProduct(Mutation):
    product = Field(ProductType)

    class Arguments:
        provider_id = String(required=True)
        product_id = String(required=False)
        sku = String(required=False)
        product_name = String(required=False)
        product_description = String(required=False)
        uom = String(required=False)
        base_price_per_uom = Float(required=False)
        data = JSON(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateProduct":
        try:
            product = insert_update_product_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateProduct(product=product)


class DeleteProduct(Mutation):
    ok = Boolean()

    class Arguments:
        provider_id = String(required=True)
        product_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteProduct":
        try:
            ok = delete_product_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteProduct(ok=ok)


class InsertUpdateRequest(Mutation):
    request = Field(RequestType)

    class Arguments:
        customer_id = String(required=True)
        request_id = String()
        title = String(required=False)
        description = String(required=False)
        items = List(JSON, required=False)
        services = List(JSON, required=False)
        status = String(required=False)
        days_until_expiration = Int(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateRequest":
        try:
            request = insert_update_request_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateRequest(request=request)


class DeleteRequest(Mutation):
    ok = Boolean()

    class Arguments:
        customer_id = String(required=True)
        request_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteRequest":
        try:
            ok = delete_request_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteRequest(ok=ok)


class InsertUpdateQuote(Mutation):
    quote = Field(QuoteType)

    class Arguments:
        request_id = String(required=True)
        quote_id = String()
        provider_id = String(required=False)
        customer_id = String(required=False)
        billing_address = JSON(required=False)
        shipping_address = JSON(required=False)
        shipping_method = String(required=False)
        shipping_amount = Float(required=False)
        total_amount = Float(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateQuote":
        try:
            quote = insert_update_quote_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateQuote(quote=quote)


class DeleteQuote(Mutation):
    ok = Boolean()

    class Arguments:
        request_id = String(required=True)
        quote_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteQuote":
        try:
            ok = delete_quote_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteQuote(ok=ok)


class InsertUpdateQuoteService(Mutation):
    quote_service = Field(QuoteServiceType)

    class Arguments:
        quote_id = String(required=True)
        service_id = String(required=True)
        provider_id = String(required=False)
        request_id = String(required=False)
        request_data = JSON(required=False)
        price_per_uom = Float(required=False)
        qty = Float(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateQuoteService":
        try:
            quote_service = insert_update_quote_service_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateQuoteService(quote_service=quote_service)


class DeleteQuoteService(Mutation):
    ok = Boolean()

    class Arguments:
        quote_id = String(required=True)
        service_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteQuoteService":
        try:
            ok = delete_quote_service_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteQuoteService(ok=ok)


class InsertUpdateQuoteItemProduct(Mutation):
    quote_item_product = Field(QuoteItemProductType)

    class Arguments:
        quote_id = String(required=True)
        item_id = String(required=True)
        request_id = String(required=False)
        item_type = String(required=False)
        request_data = JSON(required=False)
        product_id = String(required=False)
        provider_id = String(required=False)
        price_per_uom = Float(required=False)
        qty = Float(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateQuoteItemProduct":
        try:
            quote_item_product = insert_update_quote_item_product_handler(
                info, **kwargs
            )
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateQuoteItemProduct(quote_item_product=quote_item_product)


class DeleteQuoteItemProduct(Mutation):
    ok = Boolean()

    class Arguments:
        quote_id = String(required=True)
        item_id = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteQuoteItemProduct":
        try:
            ok = delete_quote_item_product_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteQuoteItemProduct(ok=ok)


class InsertUpdateInstallment(Mutation):
    installment = Field(InstallmentType)

    class Arguments:
        quote_id = String(required=True)
        installment_id = String()
        request_id = String(required=True)
        priority = String(required=False)
        salesorder_no = String(required=False)
        scheduled_date = DateTime(required=False)
        installment_ratio = Float(required=False)
        installment_amount = Float(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateInstallment":
        try:
            installment = insert_update_installment_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateInstallment(installment=installment)


class DeleteInstallment(Mutation):
    ok = Boolean()

    class Arguments:
        quote_id = String(required=True)
        installment_id = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteInstallment":
        try:
            ok = delete_installment_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteInstallment(ok=ok)


class InsertUpdateFile(Mutation):
    file = Field(FileType)

    class Arguments:
        request_id = String(required=True)
        name = String(required=True)
        user_id = String(required=True)
        user_type = String(required=True)
        path = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateFile":
        try:
            file = insert_update_file_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateFile(file=file)


class DeleteFile(Mutation):
    ok = Boolean()

    class Arguments:
        request_id = String(required=True)
        name = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteFile":
        try:
            ok = delete_file_handler(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteFile(ok=ok)
