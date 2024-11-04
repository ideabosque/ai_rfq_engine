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
                "rfq_graphql": {
                    "is_static": False,
                    "label": "AI RFQ GraphQL",
                    "query": [
                        {
                            "action": "user",
                            "label": "View User",
                        },
                        {
                            "action": "userList",
                            "label": "View User List",
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
                            "action": "comment",
                            "label": "View Comment",
                        },
                        {
                            "action": "commentList",
                            "label": "View Comment List",
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
                            "action": "insertUpdateUser",
                            "label": "Create Update User",
                        },
                        {
                            "action": "deleteUser",
                            "label": "Delete User",
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
                            "action": "insertUpdateComment",
                            "label": "Create Update Comment",
                        },
                        {
                            "action": "deleteComment",
                            "label": "Delete Comment",
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
