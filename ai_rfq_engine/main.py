#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

from graphene import Schema

from silvaengine_dynamodb_base import SilvaEngineDynamoDBBase

from .handlers import handlers_init
from .schema import Mutations, Query, type_class


# Hook function applied to deployment
def deploy() -> List:
    return [
        {
            "service": "AI Assistant",
            "class": "AIRFQEngine",
            "functions": {
                "ai_rfq_graphql": {
                    "is_static": False,
                    "label": "AI RFQ GraphQL",
                    "query": [
                        {
                            "action": "product",
                            "label": "View Product",
                        },
                        {
                            "action": "productList",
                            "label": "View Product List",
                        },
                        {
                            "action": "request",
                            "label": "View Request",
                        },
                        {
                            "action": "requestList",
                            "label": "View Request List",
                        },
                        {
                            "action": "quote",
                            "label": "View Quote",
                        },
                        {
                            "action": "quoteList",
                            "label": "View Quote List",
                        },
                        {
                            "action": "service",
                            "label": "View Service",
                        },
                        {
                            "action": "serviceList",
                            "label": "View Service List",
                        },
                        {
                            "action": "serviceProvider",
                            "label": "View Service Provider",
                        },
                        {
                            "action": "serviceProviderList",
                            "label": "View Service Provider List",
                        },
                        {
                            "action": "quoteService",
                            "label": "View Quote Service",
                        },
                        {
                            "action": "quoteServiceList",
                            "label": "View Quote Service List",
                        },
                        {
                            "action": "quoteItemProduct",
                            "label": "View Quote Item Raw Material",
                        },
                        {
                            "action": "quoteItemProductList",
                            "label": "View Quote Item Raw Material List",
                        },
                        {
                            "action": "installment",
                            "label": "View Installment",
                        },
                        {
                            "action": "installmentList",
                            "label": "View Installment List",
                        },
                        {
                            "action": "item",
                            "label": "View Item",
                        },
                        {
                            "action": "itemList",
                            "label": "View Item List",
                        },
                        {
                            "action": "file",
                            "label": "View File",
                        },
                        {
                            "action": "fileList",
                            "label": "View File List",
                        },
                    ],
                    "mutation": [
                        {
                            "action": "insertUpdateProduct",
                            "label": "Create Update Product",
                        },
                        {
                            "action": "deleteProduct",
                            "label": "Delete Product",
                        },
                        {
                            "action": "insertUpdateRequest",
                            "label": "Create Update Request",
                        },
                        {
                            "action": "deleteRequest",
                            "label": "Delete Request",
                        },
                        {
                            "action": "insertUpdateQuote",
                            "label": "Create Update Quote",
                        },
                        {
                            "action": "deleteQuote",
                            "label": "Delete Quote",
                        },
                        {
                            "action": "insertUpdateService",
                            "label": "Create Update Service",
                        },
                        {
                            "action": "deleteService",
                            "label": "Delete Service",
                        },
                        {
                            "action": "insertUpdateServiceProvider",
                            "label": "Create Update Service Provider",
                        },
                        {
                            "action": "deleteServiceProvider",
                            "label": "Delete Service Provider",
                        },
                        {
                            "action": "insertUpdateQuoteService",
                            "label": "Create Update Quote Service",
                        },
                        {
                            "action": "deleteQuoteService",
                            "label": "Delete Quote Service",
                        },
                        {
                            "action": "insertUpdateQuoteItemProduct",
                            "label": "Create Update Quote Item Raw Material",
                        },
                        {
                            "action": "deleteQuoteItemProduct",
                            "label": "Delete Quote Item Raw Material",
                        },
                        {
                            "action": "insertUpdateInstallment",
                            "label": "Create Update Installment",
                        },
                        {
                            "action": "deleteInstallment",
                            "label": "Delete Installment",
                        },
                        {
                            "action": "insertUpdateItem",
                            "label": "Create Update Item",
                        },
                        {
                            "action": "deleteItem",
                            "label": "Delete Item",
                        },
                        {
                            "action": "insertUpdateFile",
                            "label": "Create Update File",
                        },
                        {
                            "action": "deleteFile",
                            "label": "Delete File",
                        },
                    ],
                    "type": "RequestResponse",
                    "support_methods": ["POST"],
                    "is_auth_required": False,
                    "is_graphql": True,
                    "settings": "ai_rfq_engine",
                    "disabled_in_resources": True,  # Ignore adding to resource list.
                },
            },
        }
    ]


class AIRFQEngine(SilvaEngineDynamoDBBase):
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]) -> None:
        handlers_init(logger, **setting)

        self.logger = logger
        self.setting = setting

        SilvaEngineDynamoDBBase.__init__(self, logger, **setting)

    def ai_rfq_graphql(self, **params: Dict[str, Any]) -> Any:
        schema = Schema(
            query=Query,
            mutation=Mutations,
            types=type_class(),
        )
        return self.graphql_execute(schema, **params)
