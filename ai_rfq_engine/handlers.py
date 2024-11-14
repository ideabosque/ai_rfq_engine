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
    FileModel,
    InstallmentModel,
    ItemModel,
    ProductModel,
    QuoteItemProductModel,
    QuoteModel,
    QuoteServiceModel,
    RequestModel,
    ServiceModel,
    ServiceProviderModel,
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
def get_service(service_type: str, service_id: str) -> ServiceModel:
    return ServiceModel.get(service_type, service_id)


def _get_service(service_type: str, service_id: str) -> Dict[str, Any]:
    service = get_service(service_type, service_id)
    return {
        "service_type": service.service_type,
        "service_id": service.service_id,
        "service_name": service.service_name,
        "service_description": service.service_description,
    }


def get_service_count(service_type: str, service_id: str) -> int:
    return ServiceModel.count(service_type, ServiceModel.service_id == service_id)


def get_service_type(info: ResolveInfo, service: ServiceModel) -> ServiceType:
    service = service.__dict__["attribute_values"]
    return ServiceType(**Utility.json_loads(Utility.json_dumps(service)))


def resolve_service_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ServiceType:
    return get_service_type(
        info,
        get_service(kwargs.get("service_type"), kwargs.get("service_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["service_type", "service_id"],
    list_type_class=ServiceListType,
    type_funct=get_service_type,
)
def resolve_service_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    service_type = kwargs.get("service_type")
    service_name = kwargs.get("service_name")
    service_description = kwargs.get("service_description")

    args = []
    inquiry_funct = ServiceModel.scan
    count_funct = ServiceModel.count
    if service_type:
        args = [service_type, None]
        inquiry_funct = ServiceModel.query

    the_filters = None  # We can add filters for the query.
    if service_name:
        the_filters &= ServiceModel.service_name.contains(service_name)
    if service_description:
        the_filters &= ServiceModel.service_description.contains(service_description)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "service_type",
        "range_key": "service_id",
    },
    model_funct=get_service,
    count_funct=get_service_count,
    type_funct=get_service_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_service_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceType:
    service_type = kwargs.get("service_type")
    service_id = kwargs.get("service_id")
    if kwargs.get("entity") is None:
        ServiceModel(
            service_type,
            service_id,
            **{
                "service_name": kwargs["service_name"],
                "service_description": kwargs["service_description"],
                "updated_by": kwargs["updated_by"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    service = kwargs.get("entity")
    actions = [
        RequestModel.updated_by.set(kwargs.get("updated_by")),
        RequestModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("service_name"):
        actions.append(ServiceModel.service_name.set(kwargs.get("service_name")))
    if kwargs.get("service_description"):
        actions.append(
            ServiceModel.service_description.set(kwargs.get("service_description"))
        )

    service.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "service_type",
        "range_key": "service_id",
    },
    model_funct=get_service,
)
def delete_service_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_service_provider(service_id: str, provider_id: str) -> ServiceProviderModel:
    return ServiceProviderModel.get(service_id, provider_id)


def _get_service_provider(service_id: str, provider_id: str) -> Dict[str, Any]:
    service_provider = get_service_provider(service_id, provider_id)
    return {
        "service": _get_service(
            service_provider.service_type, service_provider.service_id
        ),
        "provider_id": service_provider.provider_id,
        "service_spec": service_provider.service_spec,
    }


def get_service_provider_count(service_id: str, provider_id: str) -> int:
    return ServiceProviderModel.count(
        service_id, ServiceProviderModel.provider_id == provider_id
    )


def get_service_provider_type(
    info: ResolveInfo, service_provider: ServiceProviderModel
) -> ServiceProviderType:
    try:
        service = _get_service(
            service_provider.service_type, service_provider.service_id
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    service_provider = service_provider.__dict__["attribute_values"]
    service_provider["service"] = service
    service_provider.pop("service_type")
    service_provider.pop("service_id")
    return ServiceProviderType(
        **Utility.json_loads(Utility.json_dumps(service_provider))
    )


def resolve_service_provider_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceProviderType:
    return get_service_provider_type(
        info,
        get_service_provider(kwargs.get("service_id"), kwargs.get("provider_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["service_id", "provider_id"],
    list_type_class=ServiceProviderListType,
    type_funct=get_service_provider_type,
)
def resolve_service_provider_list_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    service_id = kwargs.get("service_id")
    service_types = kwargs.get("service_types")

    args = []
    inquiry_funct = ServiceProviderModel.scan
    count_funct = ServiceProviderModel.count
    if service_id:
        args = [service_id, None]
        inquiry_funct = ServiceProviderModel.query

    the_filters = None  # We can add filters for the query.
    if service_types:
        the_filters &= ServiceProviderModel.service_type.is_in(service_types)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "service_id",
        "range_key": "provider_id",
    },
    range_key_required=True,
    model_funct=get_service_provider,
    count_funct=get_service_provider_count,
    type_funct=get_service_provider_type,
)
def insert_update_service_provider_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ServiceProviderType:
    service_id = kwargs.get("service_id")
    provider_id = kwargs.get("provider_id")
    if kwargs.get("entity") is None:
        ServiceProviderModel(
            service_id,
            provider_id,
            **{
                "service_type": kwargs["service_type"],
                "service_spec": kwargs["service_spec"],
                "uom": kwargs["uom"],
                "base_price_per_uom": kwargs["base_price_per_uom"],
                "updated_by": kwargs["updated_by"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    service_provider = kwargs.get("entity")
    actions = [
        ServiceProviderModel.updated_by.set(kwargs.get("updated_by")),
        ServiceProviderModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("service_type"):
        actions.append(ServiceProviderModel.service_type.set(kwargs["service_type"]))
    if kwargs.get("service_spec"):
        actions.append(ServiceProviderModel.service_spec.set(kwargs["service_spec"]))
    if kwargs.get("uom"):
        actions.append(ServiceProviderModel.uom.set(kwargs["uom"]))
    if kwargs.get("base_price_per_uom"):
        actions.append(
            ServiceProviderModel.base_price_per_uom.set(kwargs["base_price_per_uom"])
        )

    service_provider.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "service_id",
        "range_key": "provider_id",
    },
    model_funct=get_service_provider,
)
def delete_service_provider_handler(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_item(item_type: str, item_id: str) -> ItemModel:
    return ItemModel.get(item_type, item_id)


def _get_item(item_type: str, item_id: str) -> Dict[str, Any]:
    item = get_item(item_type, item_id)
    return {
        "item_type": item.item_type,
        "item_id": item.item_id,
        "item_name": item.item_name,
        "item_description": item.item_description,
        "uom": item.uom,
    }


def get_item_count(item_type: str, item_id: str) -> int:
    return ItemModel.count(item_type, ItemModel.item_id == item_id)


def get_item_type(info: ResolveInfo, item: ItemModel) -> ItemType:
    item = item.__dict__["attribute_values"]
    return ItemType(**Utility.json_loads(Utility.json_dumps(item)))


def resolve_item_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
    return get_item_type(
        info,
        get_item(kwargs.get("item_type"), kwargs.get("item_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["item_type", "item_id"],
    list_type_class=ItemListType,
    type_funct=get_item_type,
)
def resolve_item_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    item_type = kwargs.get("item_type")
    item_name = kwargs.get("item_name")
    item_description = kwargs.get("item_description")

    args = []
    inquiry_funct = ItemModel.scan

    count_funct = ItemModel.count
    if item_type:
        args = [item_type, None]
        inquiry_funct = ItemModel.query

    the_filters = None  # We can add filters for the query.
    if item_name:
        the_filters &= ItemModel.item_name.contains(item_name)
    if item_description:
        the_filters &= ItemModel.item_description.contains(item_description)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "item_type",
        "range_key": "item_id",
    },
    range_key_required=True,
    model_funct=get_item,
    count_funct=get_item_count,
    type_funct=get_item_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_item_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    item_type = kwargs.get("item_type")
    item_id = kwargs.get("item_id")
    if kwargs.get("entity") is None:
        ItemModel(
            item_type,
            item_id,
            **{
                "item_name": kwargs["item_name"],
                "item_description": kwargs["item_description"],
                "uom": kwargs["uom"],
                "updated_by": kwargs["updated_by"],
                "created_at": pendulum.now("UTC"),
                "updated_at": pendulum.now("UTC"),
            },
        ).save()
        return

    item = kwargs.get("entity")
    actions = [
        ItemModel.updated_by.set(kwargs.get("updated_by")),
        ItemModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("item_name") is not None:
        actions.append(ItemModel.item_name.set(kwargs["item_name"]))
    if kwargs.get("item_description") is not None:
        actions.append(ItemModel.item_description.set(kwargs["item_description"]))
    if kwargs.get("uom") is not None:
        actions.append(ItemModel.uom.set(kwargs["uom"]))

    item.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "item_type",
        "range_key": "item_id",
    },
    model_funct=get_item,
)
def delete_item_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_product(provider_id: str, product_id: str) -> ProductModel:
    return ProductModel.get(provider_id, product_id)


def _get_product(provider_id: str, product_id: str) -> Dict[str, Any]:
    product = get_product(provider_id, product_id)
    return {
        "provider_id": product.provider_id,
        "product_id": product.product_id,
        "sku": product.sku,
        "product_name": product.product_name,
        "product_description": product.product_description,
        "uom": product.uom,
        "base_price_per_uom": product.base_price_per_uom,
        "data": product.data,
    }


def get_product_count(provider_id: str, product_id: str) -> int:
    return ProductModel.count(provider_id, ProductModel.product_id == product_id)


def get_product_type(info: ResolveInfo, product: ProductModel) -> ProductType:
    product = product.__dict__["attribute_values"]
    return ProductType(**Utility.json_loads(Utility.json_dumps(product)))


def resolve_product_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ProductType:
    return get_product_type(
        info,
        get_product(kwargs.get("provider_id"), kwargs.get("product_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["provider_id", "product_id"],
    list_type_class=ProductListType,
    type_funct=get_product_type,
)
def resolve_product_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    provider_id = kwargs.get("provider_id")
    sku = kwargs.get("sku")
    product_name = kwargs.get("product_name")
    product_description = kwargs.get("product_description")

    args = []
    inquiry_funct = ProductModel.scan

    count_funct = ProductModel.count
    if provider_id:
        args = [provider_id, None]
        inquiry_funct = ProductModel.query

    the_filters = None  # We can add filters for the query.
    if sku:
        the_filters &= ProductModel.sku.contains(sku)
    if product_name:
        the_filters &= ProductModel.product_name.contains(product_name)
    if product_description:
        the_filters &= ProductModel.product_description.contains(product_description)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "provider_id",
        "range_key": "product_id",
    },
    model_funct=get_product,
    count_funct=get_product_count,
    type_funct=get_product_type,
)
def insert_update_product_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    provider_id = kwargs.get("provider_id")
    product_id = kwargs.get("product_id")
    if kwargs.get("entity") is None:
        cols = {
            "sku": kwargs["sku"],
            "product_name": kwargs["product_name"],
            "product_description": kwargs["product_description"],
            "uom": kwargs["uom"],
            "base_price_per_uom": kwargs["base_price_per_uom"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("data"):
            cols["data"] = kwargs["data"]
        ProductModel(
            provider_id,
            product_id,
            **cols,
        ).save()
        return

    product = kwargs.get("entity")
    actions = [
        ProductModel.updated_by.set(kwargs.get("updated_by")),
        ProductModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("sku") is not None:
        actions.append(ProductModel.sku.set(kwargs["sku"]))
    if kwargs.get("product_name") is not None:
        actions.append(ProductModel.product_name.set(kwargs["product_name"]))
    if kwargs.get("product_description") is not None:
        actions.append(
            ProductModel.product_description.set(kwargs["product_description"])
        )
    if kwargs.get("uom") is not None:
        actions.append(ProductModel.uom.set(kwargs["uom"]))
    if kwargs.get("base_price_per_uom") is not None:
        actions.append(
            ProductModel.base_price_per_uom.set(kwargs["base_price_per_uom"])
        )
    if kwargs.get("data") is not None:
        actions.append(ProductModel.data.set(kwargs["data"]))

    product.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "provider_id",
        "range_key": "product_id",
    },
    model_funct=get_product,
)
def delete_product_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_request(customer_id: str, request_id: str) -> RequestModel:
    return RequestModel.get(customer_id, request_id)


def _get_request(customer_id: str, request_id: str) -> Dict[str, Any]:
    request = get_request(customer_id, request_id)
    return {
        "customer_id": request.customer_id,
        "request_id": request.request_id,
        "title": request.title,
        "description": request.description,
        "items": request.items,
        "services": request.services,
        "status": request.status,
        "expired_at": request.expired_at,
    }


def get_request_count(customer_id: str, request_id: str) -> int:
    return RequestModel.count(customer_id, RequestModel.request_id == request_id)


def get_request_type(info: ResolveInfo, request: RequestModel) -> RequestType:
    request = request.__dict__["attribute_values"]
    return RequestType(**Utility.json_loads(Utility.json_dumps(request)))


def resolve_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return get_request_type(
        info,
        get_request(kwargs.get("customer_id"), kwargs.get("request_id")),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["customer_id", "request_id"],
    list_type_class=RequestListType,
    type_funct=get_request_type,
)
def resolve_request_list_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    customer_id = kwargs.get("customer_id")
    title = kwargs.get("title")
    description = kwargs.get("description")

    args = []
    inquiry_funct = RequestModel.scan
    count_funct = RequestModel.count
    if customer_id:
        args = [customer_id, None]
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
        "hash_key": "customer_id",
        "range_key": "request_id",
    },
    model_funct=get_request,
    count_funct=get_request_count,
    type_funct=get_request_type,
    # data_attributes_except_for_data_diff=data_attributes_except_for_data_diff,
    # activity_history_funct=None,
)
def insert_update_request_handler(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    customer_id = kwargs.get("customer_id")
    request_id = kwargs.get("request_id")
    if kwargs.get("entity") is None:
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
                customer_id,
                request_id,
                **cols,
            ).save()
            return

    request = kwargs.get("entity")
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

    request.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "customer_id",
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
        "billing_address": quote.billing_address,
        "shipping_address": quote.shipping_address,
        "shipping_method": quote.shipping_method,
        "shipping_amount": quote.shipping_amount,
        "total_amount": quote.total_amount,
        "status": quote.status,
    }


def get_quote_count(request_id: str, quote_id: str) -> int:
    return QuoteModel.count(request_id, QuoteModel.quote_id == quote_id)


def get_quote_type(info: ResolveInfo, quote: QuoteModel) -> QuoteType:
    try:
        request = _get_request(quote.customer_id, quote.request_id)
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    quote = quote.__dict__["attribute_values"]
    quote["request"] = request
    quote.pop("customer_id")
    quote.pop("request_id")
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


def get_quote_service_count(quote_id: str, service_id: str) -> int:
    return QuoteServiceModel.count(quote_id, QuoteServiceModel.service_id == service_id)


def get_quote_service_type(
    info: ResolveInfo, quote_service: QuoteServiceModel
) -> QuoteServiceType:
    try:
        quote = _get_quote(quote_service.request_id, quote_service.quote_id)
        service_provider = _get_service_provider(
            quote_service.service_id, quote_service.provider_id
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    quote_service = quote_service.__dict__["attribute_values"]
    quote_service["quote"] = quote
    quote_service["service_provider"] = service_provider
    quote_service.pop("quote_id")
    quote_service.pop("request_id")
    quote_service.pop("service_id")
    quote_service.pop("provider_id")
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
    service_ids = kwargs.get("service_ids")
    provider_ids = kwargs.get("provider_ids")

    args = []
    inquiry_funct = QuoteServiceModel.scan

    count_funct = QuoteServiceModel.count
    if quote_id:
        args = [quote_id, None]
        inquiry_funct = QuoteServiceModel.query

    the_filters = None  # We can add filters for the query.
    if service_ids:
        the_filters &= QuoteServiceModel.service_id.is_in(*service_ids)
    if provider_ids:
        the_filters &= QuoteServiceModel.provider_id.is_in(*provider_ids)
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
            "provider_id": kwargs["provider_id"],
            "request_id": kwargs["request_id"],
            "price_per_uom": kwargs["price_per_uom"],
            "qty": kwargs["qty"],
            "subtotal": kwargs["price_per_uom"] * kwargs["qty"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("request_data") is not None:
            cols["request_data"] = kwargs["request_data"]

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
    if kwargs.get("request_id") is not None:
        actions.append(QuoteServiceModel.request_id.set(kwargs["request_id"]))
    if kwargs.get("request_data") is not None:
        actions.append(QuoteServiceModel.request_data.set(kwargs["request_data"]))
    if kwargs.get("price_per_uom") is not None:
        actions.append(QuoteServiceModel.price_per_uom.set(kwargs["price_per_uom"]))
    if kwargs.get("qty") is not None:
        actions.append(QuoteServiceModel.qty.set(kwargs["qty"]))
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


def get_quote_item_product_count(quote_id: str, item_id: str) -> int:
    return QuoteItemProductModel.count(
        quote_id, QuoteItemProductModel.item_id == item_id
    )


def get_quote_item_product_type(
    info: ResolveInfo, quote_item_product: QuoteItemProductModel
) -> QuoteItemProductType:
    try:
        quote = _get_quote(quote_item_product.request_id, quote_item_product.quote_id)
        item = _get_item(quote_item_product.item_type, quote_item_product.item_id)
        product = _get_product(
            quote_item_product.provider_id, quote_item_product.product_id
        )
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    quote_item_product = quote_item_product.__dict__["attribute_values"]
    quote_item_product["quote"] = quote
    quote_item_product["item"] = item
    quote_item_product["product"] = product
    quote_item_product.pop("quote_id")
    quote_item_product.pop("request_id")
    quote_item_product.pop("item_type")
    quote_item_product.pop("item_id")
    quote_item_product.pop("provider_id")
    quote_item_product.pop("product_id")
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
    item_types = kwargs.get("item_types")
    product_ids = kwargs.get("product_ids")
    provider_ids = kwargs.get("provider_ids")

    args = []
    inquiry_funct = QuoteItemProductModel.scan
    count_funct = QuoteItemProductModel.count
    if quote_id:
        args = [quote_id, None]
        inquiry_funct = QuoteItemProductModel.query

    the_filters = None  # We can add filters for the query.
    if item_types:
        the_filters &= QuoteItemProductModel.item_type.is_in(*item_types)
    if product_ids:
        the_filters &= QuoteItemProductModel.product_id.is_in(*product_ids)
    if provider_ids:
        the_filters &= QuoteItemProductModel.provider_id.is_in(*provider_ids)
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
                "request_id": kwargs["request_id"],
                "item_type": kwargs["item_type"],
                "request_data": kwargs["request_data"],
                "product_id": kwargs["product_id"],
                "provider_id": kwargs["provider_id"],
                "price_per_uom": kwargs["price_per_uom"],
                "qty": kwargs["qty"],
                "subtotal": kwargs["price_per_uom"] * kwargs["qty"],
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
    if kwargs.get("request_id") is not None:
        actions.append(QuoteItemProductModel.request_id.set(kwargs["request_id"]))
    if kwargs.get("request_data") is not None:
        actions.append(QuoteItemProductModel.request_data.set(kwargs["request_data"]))
    if kwargs.get("price_per_uom") is not None:
        actions.append(QuoteItemProductModel.price_per_uom.set(kwargs["price_per_uom"]))
    if kwargs.get("qty") is not None:
        actions.append(QuoteItemProductModel.qty.set(kwargs["qty"]))
    if kwargs.get("price_per_uom") is not None and kwargs.get("qty") is not None:
        subtotal = kwargs["price_per_uom"] * kwargs["qty"]
        actions.append(QuoteItemProductModel.subtotal.set(subtotal))

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
    try:
        quote = _get_quote(installment.request_id, installment.quote_id)
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    installment = installment.__dict__["attribute_values"]
    installment["quote"] = quote
    installment.pop("request_id")
    installment.pop("quote_id")
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
        cols = {
            "request_id": kwargs["request_id"],
            "priority": kwargs["priority"],
            "salesorder_no": kwargs["salesorder_no"],
            "scheduled_date": kwargs["scheduled_date"],
            "installment_ratio": kwargs["installment_ratio"],
            "installment_amount": kwargs["installment_amount"],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if kwargs.get("status"):
            cols["status"] = kwargs["status"]
        InstallmentModel(
            quote_id,
            installment_id,
            **cols,
        ).save()
        return

    installment = kwargs.get("entity")
    actions = [
        InstallmentModel.updated_by.set(kwargs["updated_by"]),
        InstallmentModel.updated_at.set(pendulum.now("UTC")),
    ]
    if kwargs.get("priority"):
        actions.append(InstallmentModel.priority.set(kwargs["priority"]))
    if kwargs.get("scheduled_date"):
        actions.append(InstallmentModel.scheduled_date.set(kwargs["scheduled_date"]))
    if kwargs.get("installment_ratio"):
        actions.append(
            InstallmentModel.installment_ratio.set(kwargs["installment_ratio"])
        )
    if kwargs.get("installment_amount"):
        actions.append(
            InstallmentModel.installment_amount.set(kwargs["installment_amount"])
        )
    if kwargs.get("status"):
        actions.append(InstallmentModel.status.set(kwargs["status"]))

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
