#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

from graphene import Schema

from silvaengine_dynamodb_base import BaseModel
from silvaengine_utility import Graphql

from .handlers.config import Config
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
                            "action": "item",
                            "label": "View Item",
                        },
                        {
                            "action": "itemList",
                            "label": "View Item List",
                        },
                        {
                            "action": "segment",
                            "label": "View Segment",
                        },
                        {
                            "action": "segmentList",
                            "label": "View Segment List",
                        },
                        {
                            "action": "segmentContact",
                            "label": "View Segment Contact",
                        },
                        {
                            "action": "segmentContactList",
                            "label": "View Segment Contact List",
                        },
                        {
                            "action": "providerItem",
                            "label": "View Provider Item",
                        },
                        {
                            "action": "providerItemList",
                            "label": "View Provider Item List",
                        },
                        {
                            "action": "providerItemBatch",
                            "label": "View Provider Item Batch",
                        },
                        {
                            "action": "providerItemBatchList",
                            "label": "View Provider Item Batch List",
                        },
                        {
                            "action": "itemPriceTier",
                            "label": "View Item Price Tier",
                        },
                        {
                            "action": "itemPriceTieList",
                            "label": "View Item Price Tier List",
                        },
                        {
                            "action": "discountRule",
                            "label": "View Discount Rule",
                        },
                        {
                            "action": "discountRuleList",
                            "label": "View Discount Rule List",
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
                            "action": "quoteItem",
                            "label": "View Quote Item",
                        },
                        {
                            "action": "quoteItemList",
                            "label": "View Quote Item List",
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
                            "action": "insertUpdateItem",
                            "label": "Create Update Item",
                        },
                        {
                            "action": "deleteItem",
                            "label": "Delete Item",
                        },
                        {
                            "action": "insertUpdateSegment",
                            "label": "Create Update Segment",
                        },
                        {
                            "action": "deleteSegment",
                            "label": "Delete Segment",
                        },
                        {
                            "action": "insertUpdateSegmentContact",
                            "label": "Create Update Segment Contact",
                        },
                        {
                            "action": "deleteSegmentContact",
                            "label": "Delete Segment Contact",
                        },
                        {
                            "action": "insertUpdateProviderItem",
                            "label": "Create Update Provider Item",
                        },
                        {
                            "action": "deleteProviderItem",
                            "label": "Delete Provider Item",
                        },
                        {
                            "action": "insertUpdateProviderItemBatch",
                            "label": "Create Update Provider Item Batch",
                        },
                        {
                            "action": "deleteProviderItemBatch",
                            "label": "Delete Provider Item Batch",
                        },
                        {
                            "action": "insertUpdateItemPriceTier",
                            "label": "Create Update Item Price Tier",
                        },
                        {
                            "action": "deleteItemPriceTier",
                            "label": "Delete Item Price Tier",
                        },
                        {
                            "action": "insertUpdateDiscountRule",
                            "label": "Create Update Discount Rule",
                        },
                        {
                            "action": "deleteDiscountRule",
                            "label": "Delete Discount Rule",
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
                            "action": "insertUpdateQuoteItem",
                            "label": "Create Update Quote Item",
                        },
                        {
                            "action": "deleteQuoteItem",
                            "label": "Delete Quote Item",
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
                    "settings": "beta_core_openai",
                    "disabled_in_resources": True,  # Ignore adding to resource list.
                },
            },
        }
    ]


class AIRFQEngine(Graphql):
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]) -> None:
        Graphql.__init__(self, logger, **setting)

        if (
            setting.get("region_name")
            and setting.get("aws_access_key_id")
            and setting.get("aws_secret_access_key")
        ):
            BaseModel.Meta.region = setting.get("region_name")
            BaseModel.Meta.aws_access_key_id = setting.get("aws_access_key_id")
            BaseModel.Meta.aws_secret_access_key = setting.get("aws_secret_access_key")

        # Initialize configuration via the Config class
        Config.initialize(logger, **setting)

        self.logger = logger
        self.setting = setting

    def _apply_partition_defaults(self, params: Dict[str, Any]) -> None:
        """
        Apply default partition values if not provided in params.

        Args:
            params (Dict[str, Any]): A dictionary of parameters required to build the GraphQL query.
        """
        endpoint_id = params.get("endpoint_id", self.setting.get("endpoint_id"))
        part_id = params.get("metadata", {}).get(
            "part_id",
            params.get("part_id", self.setting.get("part_id")),
        )

        if params.get("context") is None:
            params["context"] = {}

        if "endpoint_id" not in params["context"]:
            params["context"]["endpoint_id"] = endpoint_id
        if "part_id" not in params["context"]:
            params["context"]["part_id"] = part_id
        if "connection_id" not in params:
            params["connection_id"] = self.setting.get("connection_id")

        if "partition_key" not in params["context"]:
            # Validate endpoint_id and part_id before creating partition_key
            if not endpoint_id or not part_id:
                self.logger.error(
                    f"Missing endpoint_id or part_id: endpoint_id={endpoint_id}, part_id={part_id}"
                )
                raise ValueError(
                    "Both 'endpoint_id' and 'part_id' are required to generate 'partition_key'."
                )
            else:
                params["context"]["partition_key"] = f"{endpoint_id}#{part_id}"

        if "logger" in params:
            params.pop("logger")

        if "setting" in params:
            params.pop("setting")

    def ai_rfq_graphql(self, **params: Dict[str, Any]) -> Any:

        self._apply_partition_defaults(params)

        schema = Schema(
            query=Query,
            mutation=Mutations,
            types=type_class(),
        )
        return self.execute(schema, **params)

    @staticmethod
    def build_graphql_schema() -> Schema:
        return Schema(
            query=Query,
            mutation=Mutations,
            types=type_class(),
        )
