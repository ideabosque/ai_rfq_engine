#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import json
import logging
import os
import sys
import time
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
setting = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "data_gathering_graphql": {
            "module_name": "data_gathering_engine",
            "class_name": "DataGatheringEngine",
        },
    },
    "funct_on_local_config": {},
    "graphql_documents": {},
}

document = Path(
    os.path.join(os.path.dirname(__file__), "ai_rfq_engine.graphql")
).read_text()
sys.path.insert(0, "/var/www/projects/ai_rfq_engine")
sys.path.insert(1, "/var/www/projects/silvaengine_dynamodb_base")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

from ai_rfq_engine import AIRFQEngine


class AIRFQEngineTest(unittest.TestCase):
    def setUp(self):
        self.ai_rfq_engine = AIRFQEngine(logger, **setting)
        logger.info("Initiate AIRFQEngineTest ...")

    def tearDown(self):
        logger.info("Destory AIRFQEngineTest ...")

    @unittest.skip("demonstrating skipping")
    def test_graphql_ping(self):
        payload = {
            "query": document,
            "variables": {},
            "operation_name": "ping",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_user(self):
        payload = {
            "query": document,
            "variables": {
                "companyId": "XXXXXXXX",
                "userId": "9949609751659483631",
                "email": "XXXXXXXXXXXXX",
                "fullName": "XYZ",
                "data": {},
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateUser",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_user(self):
        payload = {
            "query": document,
            "variables": {
                "companyId": "XXXXXXXX",
                "userId": "8814524378649399791",
            },
            "operation_name": "deleteUser",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_user(self):
        payload = {
            "query": document,
            "variables": {
                "companyId": "XXXXXXXX",
                "userId": "9949609751659483631",
            },
            "operation_name": "getUser",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_user_list(self):
        payload = {
            "query": document,
            "variables": {
                "companyId": "XXXXXXXX",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getUserList",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_request(self):
        payload = {
            "query": document,
            "variables": {
                "userId": "9949609751659483631",
                "requestId": "13556221548218618351",
                "title": "XXXXXXXX",
                "description": "XXXXXXXX",
                "items": [],
                "services": [],
                "status": "initial",
                "daysUntilExpiration": 5,
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateRequest",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_request(self):
        payload = {
            "query": document,
            "variables": {
                "userId": "9949609751659483631",
                "requestId": "2456336509709521391",
            },
            "operation_name": "deleteRequest",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_request(self):
        payload = {
            "query": document,
            "variables": {
                "userId": "9949609751659483631",
                "requestId": "13556221548218618351",
            },
            "operation_name": "getRequest",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_request_list(self):
        payload = {
            "query": document,
            "variables": {
                "userId": "9949609751659483631",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getRequestList",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_quote(self):
        payload = {
            "query": document,
            "variables": {
                "requestId": "13556221548218618351",
                "quoteId": "10132984814893470191",
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "customerId": "9949609751659483631",
                # "installments": [],
                # "billingAddress": {},
                # "shippingAddress": {},
                # "shippingMethod": "",
                # "shippingAmount": "",
                # "totalAmount": "",
                # "status": "initial",
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateQuote",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_quote(self):
        payload = {
            "query": document,
            "variables": {
                "requestId": "13556221548218618351",
                "quoteId": "14813610908167049711",
            },
            "operation_name": "deleteQuote",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_quote(self):
        payload = {
            "query": document,
            "variables": {
                "requestId": "13556221548218618351",
                "quoteId": "10132984814893470191",
            },
            "operation_name": "getQuote",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_quote_list(self):
        payload = {
            "query": document,
            "variables": {
                "requestId": "13556221548218618351",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getQuoteList",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_quote_service(self):
        payload = {
            "query": document,
            "variables": {
                "quoteId": "10132984814893470191",
                "serviceId": "XXXXXXXXXXXXXXXXXXXX",
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "serviceName": "XXXXXXXXXXXXXXXXXXXX",
                # "requestData": {},
                # "data": {},
                "uom": "hr",
                "pricePerUom": 100.0,
                "qty": 10,
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateQuoteService",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_quote_service(self):
        payload = {
            "query": document,
            "variables": {
                "quoteId": "10132984814893470191",
                "serviceId": "XXXXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "deleteQuoteService",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_quote_service(self):
        payload = {
            "query": document,
            "variables": {
                "quoteId": "10132984814893470191",
                "serviceId": "XXXXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "getQuoteService",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)

    # @unittest.skip("demonstrating skipping")
    def test_graphql_quote_service_list(self):
        payload = {
            "query": document,
            "variables": {
                "quoteId": "10132984814893470191",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getQuoteServiceList",
        }
        response = self.ai_rfq_engine.rfq_graphql(**payload)
        logger.info(response)


if __name__ == "__main__":
    unittest.main()
