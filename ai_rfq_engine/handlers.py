#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import boto3
import pendulum
from graphene import ResolveInfo
from silvaengine_dynamodb_base import (
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import (
    CommentModel,
    FileModel,
    InstallmentModel,
    QuoteItemProductModel,
    QuoteModel,
    QuoteServiceModel,
    RequestModel,
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
    ServiceListType,
    ServiceProviderListType,
    ServiceProviderType,
    ServiceType,
)

functs_on_local = None
funct_on_local_config = None
graphql_documents = None
aws_lambda = None


def handlers_init(logger: logging.Logger, **setting: Dict[str, Any]) -> None:
    global functs_on_local, funct_on_local_config, graphql_documents, aws_lambda
    try:
        functs_on_local = setting.get("functs_on_local", {})
        funct_on_local_config = setting.get("funct_on_local_config", {})
        graphql_documents = setting.get("graphql_documents")

        # Set up AWS credentials in Boto3
        if (
            setting.get("region_name")
            and setting.get("aws_access_key_id")
            and setting.get("aws_secret_access_key")
        ):
            aws_lambda = boto3.client(
                "lambda",
                region_name=setting.get("region_name"),
                aws_access_key_id=setting.get("aws_access_key_id"),
                aws_secret_access_key=setting.get("aws_secret_access_key"),
            )
        else:
            aws_lambda = boto3.client(
                "lambda",
            )
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def invoke_funct_on_local(
    logger: logging.Logger, funct: str, **params: Dict[str, Any]
) -> Dict[str, Any]:
    try:
        funct_on_local = functs_on_local.get(funct)
        assert funct_on_local is not None, f"Function ({funct}) not found."
        assert funct_on_local_config is not None, "funct_on_local_config is not set."

        result = Utility.json_loads(
            Utility.invoke_funct_on_local(
                logger, funct, funct_on_local, funct_on_local_config, **params
            )
        )
        if result.get("errors"):
            raise Exception(result["errors"])

        return result["data"]
    except Exception as e:
        log = traceback.format_exc()
        logger.error(log)
        raise e


def execute_graphql_query(
    logger: logging.Logger,
    endpoint_id: str,
    funct: str,
    operation_name: str,
    variables: Dict[str, Any] = {},
) -> Dict[str, Any]:
    params = {
        "query": graphql_documents[funct],
        "variables": variables,
        "operation_name": operation_name,
    }
    if endpoint_id is None:
        return invoke_funct_on_local(logger, funct, **params)

    result = Utility.invoke_funct_on_aws_lambda(
        logger,
        aws_lambda,
        **{"endpoint_id": endpoint_id, "funct": funct, "params": params},
    )
    return Utility.json_loads(Utility.json_loads(result))["data"]


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_request(user_id: str, request_id: str) -> RequestModel:
    return RequestModel.get(user_id, request_id)


def _get_request(user_id: str, request_id: str) -> Dict[str, Any]:
    request = get_request(user_id, request_id)
    return {
        "user_id": request.user_id,
        "request_id": request.request_id,
        "title": request.title,
        "description": request.description,
        "items": request.items,
        "services": request.services,
        "status": request.status,
        "expired_at": request.expired_at,
        "updated_by": request.updated_by,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def get_request_count(user_id: str, request_id: str) -> int:
    return RequestModel.count(user_id, RequestModel.request_id == request_id)


def get_request_type(info: ResolveInfo, request: RequestModel) -> RequestType:
    request = request.__dict__["attribute_values"]
    return RequestType(**Utility.json_loads(Utility.json_dumps(request)))


def resolve_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return get_request_type(
        info,
        get_request(kwargs.get("user_id"), kwargs.get("request_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["user_id", "request_id"],
    list_type_class=RequestListType,
    type_funct=get_request_type,
)
def resolve_request_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    user_id = kwargs.get("user_id")
    title = kwargs.get("title")
    description = kwargs.get("description")

    args = []
    inquiry_funct = RequestModel.scan
    count_funct = RequestModel.count
    if user_id:
        args = [user_id, None]
        inquiry_funct = RequestModel.query

    the_filters = None  # We can add filters for the query.
    if title:
        the_filters &= RequestModel.title.contains(title)
    if description:
        the_filters &= RequestModel.description.contains(description)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "user_id",
        "range_key": "request_id",
    },
    model_funct=get_request,
    count_funct=get_request_count,
    type_funct=get_request_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    user_id = kwargs.get("user_id")
    request_id = kwargs.get("request_id")
    cols = {
        "title": kwargs["title"],
        "description": kwargs["description"],
        "expired_at": pendulum.now("UTC").add(
            days=kwargs.get("days_until_expiration", 10)
        ),
        "updated_by": kwargs["updated_by"],
        "created_at": pendulum.now("UTC"),
        "updated_at": pendulum.now("UTC"),
    }
    if kwargs.get("items") is not None:
        cols["items"] = kwargs["items"]
    if kwargs.get("services") is not None:
        cols["services"] = kwargs["services"]
    if kwargs.get("status") is not None:
        cols["status"] = kwargs["status"]
    if kwargs.get("entity") is None:
        RequestModel(
            user_id,
            request_id,
            **cols,
        ).save()
        return

    user = kwargs.get("entity")
    actions = [
        RequestModel.updated_by.set(kwargs.get("updated_by")),
        RequestModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("title") is not None:
        actions.append(RequestModel.title.set(kwargs.get("title")))
    if kwargs.get("description") is not None:
        actions.append(RequestModel.description.set(kwargs.get("description")))
    if kwargs.get("items") is not None:
        actions.append(RequestModel.items.set(kwargs.get("items")))
    if kwargs.get("services") is not None:
        actions.append(RequestModel.services.set(kwargs.get("services")))
    if kwargs.get("status") is not None:
        actions.append(RequestModel.status.set(kwargs.get("status")))
    if kwargs.get("days_until_expiration") is not None:
        actions.append(
            RequestModel.expired_at.set(
                pendulum.now("UTC").add(days=kwargs["days_until_expiration"])
            )
        )

    user.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "user_id",
        "range_key": "request_id",
    },
    model_funct=get_request,
)
def delete_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_quote(request_id: str, quote_id: str) -> QuoteModel:
    return QuoteModel.get(request_id, quote_id)


def _get_quote(request_id: str, quote_id: str) -> Dict[str, Any]:
    quote = get_quote(request_id, quote_id)
    return {
        "request_id": quote.request_id,
        "quote_id": quote.quote_id,
        "provider_id": quote.provider_id,
        "customer_id": quote.customer_id,
        "installments": quote.installments,
        "billing_address": quote.billing_address,
        "shipping_address": quote.shipping_address,
        "shipping_method": quote.shipping_method,
        "shipping_amount": quote.shipping_amount,
        "total_amount": quote.total_amount,
        "status": quote.status,
        "updated_by": quote.updated_by,
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
    }


def get_quote_count(request_id: str, quote_id: str) -> int:
    return QuoteModel.count(request_id, QuoteModel.quote_id == quote_id)


def get_quote_type(info: ResolveInfo, quote: QuoteModel) -> QuoteType:
    quote = quote.__dict__["attribute_values"]
    return QuoteType(**Utility.json_loads(Utility.json_dumps(quote)))


def resolve_quote_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
    return get_quote_type(
        info,
        get_quote(kwargs.get("request_id"), kwargs.get("quote_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["request_id", "quote_id", "provider_id", "customer_id"],
    list_type_class=QuoteListType,
    type_funct=get_quote_type,
)
def resolve_quote_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    request_id = kwargs.get("request_id")
    provider_id = kwargs.get("provider_id")
    customer_id = kwargs.get("customer_id")
    shipping_methods = kwargs.get("shipping_methods")
    statuses = kwargs.get("statuses")

    args = []
    inquiry_funct = QuoteModel.scan
    count_funct = QuoteModel.count
    if request_id:
        args = [request_id, None]
        inquiry_funct = QuoteModel.query
        if provider_id:
            args[1] = QuoteModel.provider_id == provider_id
            inquiry_funct = QuoteModel.provider_id_index.query
            count_funct = QuoteModel.provider_id_index.count
        if customer_id:
            args[1] = QuoteModel.customer_id == customer_id
            inquiry_funct = QuoteModel.customer_id_index.query
            count_funct = QuoteModel.customer_id_index.count

    the_filters = None  # We can add filters for the query.
    if shipping_methods:
        the_filters &= QuoteModel.shipping_method.is_in(*shipping_methods)
    if statuses:
        the_filters &= QuoteModel.status.is_in(*statuses)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "quote_id",
    },
    model_funct=get_quote,
    count_funct=get_quote_count,
    type_funct=get_quote_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_quote_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_id = kwargs.get("request_id")
    quote_id = kwargs.get("quote_id")
    cols = {
        "provider_id": kwargs["provider_id"],
        "customer_id": kwargs["customer_id"],
        "updated_by": kwargs["updated_by"],
        "created_at": pendulum.now("UTC"),
        "updated_at": pendulum.now("UTC"),
    }
    if kwargs.get("installments") is not None:
        cols["installments"] = kwargs["installments"]
    if kwargs.get("billing_address") is not None:
        cols["billing_address"] = kwargs["billing_address"]
    if kwargs.get("shipping_address") is not None:
        cols["shipping_address"] = kwargs["shipping_address"]
    if kwargs.get("shipping_method") is not None:
        cols["shipping_method"] = kwargs["shipping_method"]
    if kwargs.get("shipping_amount") is not None:
        cols["shipping_amount"] = kwargs["shipping_amount"]
    if kwargs.get("total_amount") is not None:
        cols["total_amount"] = kwargs["total_amount"]
    if kwargs.get("status") is not None:
        cols["status"] = kwargs["status"]
    if kwargs.get("entity") is None:
        QuoteModel(
            request_id,
            quote_id,
            **cols,
        ).save()
        return

    user = kwargs.get("entity")
    actions = [
        QuoteModel.updated_by.set(kwargs.get("updated_by")),
        QuoteModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("installments") is not None:
        actions.append(QuoteModel.installments.set(kwargs.get("installments")))
    if kwargs.get("billing_address") is not None:
        actions.append(QuoteModel.billing_address.set(kwargs.get("billing_address")))
    if kwargs.get("shipping_address") is not None:
        actions.append(
            QuoteModel.shipping_address.set(kwargs.get("shipping_address")),
        )
    if kwargs.get("shipping_method") is not None:
        actions.append(
            QuoteModel.shipping_method.set(kwargs.get("shipping_method")),
        )
    if kwargs.get("shipping_amount") is not None:
        actions.append(
            QuoteModel.shipping_amount.set(kwargs.get("shipping_amount")),
        )
    if kwargs.get("total_amount") is not None:
        actions.append(QuoteModel.total_amount.set(kwargs.get("total_amount")))
    if kwargs.get("status") is not None:
        actions.append(QuoteModel.status.set(kwargs.get("status")))

    user.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "quote_id",
    },
    model_funct=get_quote,
)
def delete_quote_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_quote_service(quote_id: str, service_id: str) -> QuoteServiceModel:
    return QuoteServiceModel.get(quote_id, service_id)


def _get_quote_service(quote_id: str, service_id: str) -> Dict[str, Any]:
    quote_service = get_quote_service(quote_id, service_id)
    return {
        "quote_id": quote_service.quote_id,
        "service_id": quote_service.service_id,
        "service_type": quote_service.service_type,
        "service_name": quote_service.service_name,
        "request_data": quote_service.request_data,
        "data": quote_service.data,
        "uom": quote_service.uom,
        "price_per_uom": quote_service.price_per_uom,
        "qty": quote_service.qty,
        "subtotal": quote_service.subtotal,
    }


def get_quote_service_count(quote_id: str, service_id: str) -> int:
    return QuoteServiceModel.count(quote_id, QuoteServiceModel.service_id == service_id)


def get_quote_service_type(
    info: ResolveInfo, quote_service: QuoteServiceModel
) -> QuoteServiceType:
    quote_service = quote_service.__dict__["attribute_values"]
    return QuoteServiceType(**Utility.json_loads(Utility.json_dumps(quote_service)))


def resolve_quote_service_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteServiceType:
    return get_quote_service_type(
        info,
        get_quote_service(kwargs.get("quote_id"), kwargs.get("service_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["quote_id", "service_id"],
    list_type_class=QuoteServiceListType,
    type_funct=get_quote_service_type,
)
def resolve_quote_service_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    quote_id = kwargs.get("quote_id")
    service_types = kwargs.get("service_types")
    service_name = kwargs.get("service_name")

    args = []
    inquiry_funct = QuoteServiceModel.scan

    count_funct = QuoteServiceModel.count
    if quote_id:
        args = [quote_id, None]
        inquiry_funct = QuoteServiceModel.query

    the_filters = None  # We can add filters for the query.
    if service_types:
        the_filters &= QuoteServiceModel.service_type.is_in(*service_types)
    if service_name:
        the_filters &= QuoteServiceModel.service_name.contains(service_name)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "service_id",
    },
    range_key_required=True,
    model_funct=get_quote_service,
    count_funct=get_quote_service_count,
    type_funct=get_quote_service_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_quote_service_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> None:
    quote_id = kwargs.get("quote_id")
    service_id = kwargs.get("service_id")
    if kwargs.get("entity") is None:
        cols = {
            "service_type": kwargs["service_type"],
            "service_name": kwargs["service_name"],
            "uom": kwargs["uom"],
            "price_per_uom": kwargs["price_per_uom"],
            "qty": kwargs["qty"],
            "subtotal": kwargs["price_per_uom"] * kwargs["qty"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("request_data") is not None:
            cols["request_data"] = kwargs["request_data"]
        if kwargs.get("data") is not None:
            cols["data"] = kwargs["data"]

        QuoteServiceModel(
            quote_id,
            service_id,
            **cols,
        ).save()
        return

    quote_service = kwargs.get("entity")
    actions = [
        QuoteServiceModel.updated_by.set(kwargs.get("updated_by")),
        QuoteServiceModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("request_data") is not None:
        actions.append(QuoteServiceModel.request_data.set(kwargs.get("request_data")))
    if kwargs.get("data") is not None:
        actions.append(QuoteServiceModel.data.set(kwargs.get("data")))
    if kwargs.get("uom") is not None:
        actions.append(QuoteServiceModel.uom.set(kwargs.get("uom")))
    if kwargs.get("price_per_uom") is not None:
        actions.append(QuoteServiceModel.price_per_uom.set(kwargs.get("price_per_uom")))
    if kwargs.get("qty") is not None:
        actions.append(QuoteServiceModel.qty.set(kwargs.get("qty")))
    if kwargs.get("price_per_uom") is not None and kwargs.get("qty") is not None:
        subtotal = kwargs["price_per_uom"] * kwargs["qty"]
        actions.append(QuoteServiceModel.subtotal.set(subtotal))

    quote_service.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "service_id",
    },
    model_funct=get_quote_service,
)
def delete_quote_service_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_quote_item_product(quote_id: str, item_id: str) -> QuoteItemProductModel:
    return QuoteItemProductModel.get(quote_id, item_id)


def _get_quote_item_product(quote_id: str, item_id: str) -> Dict[str, Any]:
    quote_item_product = get_quote_item_product(quote_id, item_id)
    return {
        "quote_id": quote_item_product.quote_id,
        "item_id": quote_item_product.item_id,
        "item_group": quote_item_product.item_group,
        "item_name": quote_item_product.item_name,
        "request_data": quote_item_product.request_data,
        "product_id": quote_item_product.product_id,
        "product_name": quote_item_product.product_name,
        "sku": quote_item_product.sku,
        "uom": quote_item_product.uom,
        "price_per_uom": quote_item_product.price_per_uom,
        "qty": quote_item_product.qty,
        "subtotal": quote_item_product.subtotal,
    }


def get_quote_item_product_count(quote_id: str, item_id: str) -> int:
    return QuoteItemProductModel.count(
        quote_id, QuoteItemProductModel.item_id == item_id
    )


def get_quote_item_product_type(
    info: ResolveInfo, quote_item_product: QuoteItemProductModel
) -> QuoteItemProductType:
    quote_item_product = quote_item_product.__dict__["attribute_values"]
    return QuoteItemProductType(
        **Utility.json_loads(Utility.json_dumps(quote_item_product))
    )


def resolve_quote_item_product_handler(
    info: ResolveInfo, **kwargs: Any
) -> QuoteItemProductType:
    return get_quote_item_product_type(
        info,
        get_quote_item_product(kwargs.get("quote_id"), kwargs.get("item_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["quote_id", "item_id"],
    list_type_class=QuoteItemProductListType,
    type_funct=get_quote_item_product_type,
)
def resolve_quote_item_product_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    quote_id = kwargs.get("quote_id")
    item_groups = kwargs.get("item_groups")
    item_name = kwargs.get("item_name")
    product_id = kwargs.get("product_id")
    product_name = kwargs.get("product_name")

    args = []
    inquiry_funct = QuoteItemProductModel.scan
    count_funct = QuoteItemProductModel.count
    if quote_id:
        args = [quote_id, None]
        inquiry_funct = QuoteItemProductModel.query

    the_filters = None  # We can add filters for the query.
    if item_groups:
        the_filters &= QuoteItemProductModel.item_group.is_in(*item_groups)
    if item_name:
        the_filters &= QuoteItemProductModel.item_name.contains(item_name)
    if product_id:
        the_filters &= QuoteItemProductModel.product_id == product_id
    if product_name:
        the_filters &= QuoteItemProductModel.product_name.contains(product_name)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "item_id",
    },
    range_key_required=True,
    model_funct=get_quote_item_product,
    count_funct=get_quote_item_product_count,
    type_funct=get_quote_item_product_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_quote_item_product_handler(info: ResolveInfo, **kwargs: Any) -> None:
    quote_id = kwargs.get("quote_id")
    item_id = kwargs.get("item_id")
    if kwargs.get("entity") is None:
        QuoteItemProductModel(
            quote_id,
            item_id,
            **{
                "item_group": kwargs["item_group"],
                "item_name": kwargs["item_name"],
                "request_data": kwargs["request_data"],
                "product_id": kwargs["product_id"],
                "product_name": kwargs["product_name"],
                "sku": kwargs["sku"],
                "uom": kwargs["uom"],
                "price_per_uom": kwargs["price_per_uom"],
                "qty": kwargs["qty"],
                "subtotal": kwargs["subtotal"],
                "updated_by": kwargs["updated_by"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    quote_item_product = kwargs.get("entity")
    actions = [
        QuoteItemProductModel.updated_by.set(kwargs.get("updated_by")),
        QuoteItemProductModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("request_data") is not None:
        actions.append(
            QuoteItemProductModel.request_data.set(kwargs.get("request_data"))
        )
    if kwargs.get("price_per_uom") is not None:
        actions.append(
            QuoteItemProductModel.price_per_uom.set(kwargs.get("price_per_uom"))
        )
    if kwargs.get("qty") is not None:
        actions.append(QuoteItemProductModel.qty.set(kwargs.get("qty")))
    if kwargs.get("subtotal") is not None:
        actions.append(QuoteItemProductModel.subtotal.set(kwargs.get("subtotal")))

    quote_item_product.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "item_id",
    },
    model_funct=get_quote_item_product,
)
def delete_quote_item_product_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_installment(quote_id: str, installment_id: str) -> InstallmentModel:
    return InstallmentModel.get(quote_id, installment_id)


def _get_installment(quote_id: str, installment_id: str) -> Dict[str, Any]:
    installment = get_installment(quote_id, installment_id)
    return {
        "quote_id": installment.quote_id,
        "installment_id": installment.installment_id,
        "request_id": installment.request_id,
        "priority": installment.priority,
        "salesorder_no": installment.salesorder_no,
        "scheduled_date": installment.scheduled_date,
        "installment_ratio": installment.installment_ratio,
        "installment_amount": installment.installment_amount,
        "status": installment.status,
        "updated_by": installment.updated_by,
        "created_at": installment.created_at,
        "updated_at": installment.updated_at,
    }


def get_installment_count(quote_id: str, installment_id: str) -> int:
    return InstallmentModel.count(
        quote_id, InstallmentModel.installment_id == installment_id
    )


def get_installment_type(
    info: ResolveInfo, installment: InstallmentModel
) -> InstallmentType:
    installment = installment.__dict__["attribute_values"]
    return InstallmentType(**Utility.json_loads(Utility.json_dumps(installment)))


def resolve_installment_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentType:
    return get_installment_type(
        info,
        get_installment(kwargs.get("quote_id"), kwargs.get("installment_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["quote_id", "installment_id"],
    list_type_class=InstallmentListType,
    type_funct=get_installment_type,
)
def resolve_installment_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    quote_id = kwargs.get("quote_id")
    request_id = kwargs.get("request_id")
    priorities = kwargs.get("priorities")
    salesorder_nos = kwargs.get("salesorder_nos")
    scheduled_date_from = kwargs.get("scheduled_date_from")
    scheduled_date_to = kwargs.get("scheduled_date_to")
    statuses = kwargs.get("statuses")

    args = []
    inquiry_funct = InstallmentModel.scan
    count_funct = InstallmentModel.count
    if quote_id:
        args = [quote_id, None]
        inquiry_funct = InstallmentModel.query

    the_filters = None  # We can add filters for the query.
    if request_id:
        the_filters &= InstallmentModel.request_id == request_id
    if priorities:
        the_filters &= InstallmentModel.priority.is_in(*priorities)
    if salesorder_nos:
        the_filters &= InstallmentModel.salesorder_no.is_in(*salesorder_nos)
    if scheduled_date_from and scheduled_date_to:
        the_filters &= InstallmentModel.scheduled_date.between(
            scheduled_date_from, scheduled_date_to
        )
    if statuses:
        the_filters &= InstallmentModel.status.is_in(*statuses)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "installment_id",
    },
    model_funct=get_installment,
    count_funct=get_installment_count,
    type_funct=get_installment_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_installment_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> None:
    quote_id = kwargs.get("quote_id")
    installment_id = kwargs.get("installment_id")
    if kwargs.get("entity") is None:
        InstallmentModel(
            quote_id,
            installment_id,
            **{
                "request_id": kwargs["request_id"],
                "priority": kwargs["priority"],
                "salesorder_no": kwargs["salesorder_no"],
                "scheduled_date": kwargs["scheduled_date"],
                "installment_ratio": kwargs["installment_ratio"],
                "installment_amount": kwargs["installment_amount"],
                "status": kwargs["status"],
                "updated_by": kwargs["updated_by"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    installment = kwargs.get("entity")
    actions = [
        InstallmentModel.updated_by.set(kwargs.get("updated_by")),
        InstallmentModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("priority"):
        actions.append(InstallmentModel.priority.set(kwargs.get("priority")))
    if kwargs.get("scheduled_date"):
        actions.append(
            InstallmentModel.scheduled_date.set(kwargs.get("scheduled_date"))
        )
    if kwargs.get("installment_ratio"):
        actions.append(
            InstallmentModel.installment_ratio.set(kwargs.get("installment_ratio"))
        )
    if kwargs.get("installment_amount"):
        actions.append(
            InstallmentModel.installment_amount.set(kwargs.get("installment_amount"))
        )
    if kwargs.get("status"):
        actions.append(InstallmentModel.status.set(kwargs.get("status")))

    installment.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "quote_id",
        "range_key": "installment_id",
    },
    model_funct=get_installment,
)
def delete_installment_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_comment(request_id: str, timestamp: str) -> CommentModel:
    return CommentModel.get(request_id, timestamp)


def _get_comment(request_id: str, timestamp: str) -> Dict[str, Any]:
    comment = get_comment(request_id, timestamp)
    return {
        "request_id": comment.request_id,
        "timestamp": comment.timestamp,
        "user_id": comment.user_id,
        "user_type": comment.user_type,
        "comment": comment.comment,
        "updated_at": comment.updated_at,
    }


def get_comment_count(request_id: str, timestamp: str) -> int:
    return CommentModel.count(request_id, CommentModel.timestamp == timestamp)


def get_comment_type(info: ResolveInfo, comment: CommentModel) -> CommentType:
    comment = comment.__dict__["attribute_values"]
    return CommentType(**Utility.json_loads(Utility.json_dumps(comment)))


def resolve_comment_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> CommentType:
    return get_comment_type(
        info,
        get_comment(kwargs.get("request_id"), kwargs.get("timestamp")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["request_id", "timestamp"],
    list_type_class=CommentListType,
    type_funct=get_comment_type,
)
def resolve_comment_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    request_id = kwargs.get("request_id")
    user_id = kwargs.get("user_id")
    user_types = kwargs.get("user_types")
    comment = kwargs.get("comment")

    args = []
    inquiry_funct = CommentModel.scan
    count_funct = CommentModel.count
    if request_id:
        args = [request_id, None]
        inquiry_funct = CommentModel.query
        if user_id:
            args.append(CommentModel.user_id == user_id)
            inquiry_funct = CommentModel.user_id_index.query
            count_funct = CommentModel.user_id_index.count

    the_filters = None  # We can add filters for the query.
    if user_types:
        the_filters &= CommentModel.user_type.is_in(*user_types)
    if comment:
        the_filters &= CommentModel.comment.contains(comment)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "timestamp",
    },
    model_funct=get_comment,
    count_funct=get_comment_count,
    type_funct=get_comment_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_comment_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_id = kwargs.get("request_id")
    timestamp = kwargs.get("timestamp")
    if kwargs.get("entity") is None:
        CommentModel(
            request_id,
            timestamp,
            **{
                "user_id": kwargs["user_id"],
                "user_type": kwargs["user_type"],
                "comment": kwargs["comment"],
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    comment = kwargs.get("entity")
    actions = [
        CommentModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("comment"):
        actions.append(CommentModel.comment.set(kwargs.get("comment")))

    comment.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "timestamp",
    },
    model_funct=get_comment,
)
def delete_comment_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_file(request_id: str, name: str) -> FileModel:
    return FileModel.get(request_id, name)


def _get_file(request_id: str, name: str) -> Dict[str, Any]:
    file = get_file(request_id, name)
    return {
        "request_id": file.request_id,
        "name": file.name,
        "user_id": file.user_id,
        "user_type": file.user_type,
        "path": file.path,
        "created_at": file.created_at,
        "updated_at": file.updated_at,
    }


def get_file_count(request_id: str, name: str) -> int:
    return FileModel.count(request_id, FileModel.name == name)


def get_file_type(info: ResolveInfo, file: FileModel) -> FileType:
    file = file.__dict__["attribute_values"]
    return FileType(**Utility.json_loads(Utility.json_dumps(file)))


def resolve_file_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
    return get_file_type(
        info,
        get_file(kwargs.get("request_id"), kwargs.get("name")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["request_id", "name"],
    list_type_class=FileListType,
    type_funct=get_file_type,
)
def resolve_file_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    request_id = kwargs.get("request_id")
    user_id = kwargs.get("user_id")
    user_types = kwargs.get("user_types")
    path = kwargs.get("path")

    args = []
    inquiry_funct = FileModel.scan
    count_funct = FileModel.count
    if request_id:
        args = [request_id, None]
        inquiry_funct = FileModel.query
        if user_id:
            args.append(FileModel.user_id == user_id)
            inquiry_funct = FileModel.user_id_index.query
            count_funct = FileModel.user_id_index.count

    the_filters = None  # We can add filters for the query.
    if user_types:
        the_filters &= FileModel.user_type.is_in(*user_types)
    if path:
        the_filters &= FileModel.path.contains(path)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "name",
    },
    model_funct=get_file,
    count_funct=get_file_count,
    type_funct=get_file_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_file_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_id = kwargs.get("request_id")
    name = kwargs.get("name")
    if kwargs.get("entity") is None:
        FileModel(
            request_id,
            name,
            **{
                "user_id": kwargs["user_id"],
                "user_type": kwargs["user_type"],
                "path": kwargs["path"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    comment = kwargs.get("entity")
    actions = [
        FileModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("path"):
        actions.append(FileModel.path.set(kwargs.get("path")))

    comment.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "request_id",
        "range_key": "name",
    },
    model_funct=get_file,
)
def delete_file_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True