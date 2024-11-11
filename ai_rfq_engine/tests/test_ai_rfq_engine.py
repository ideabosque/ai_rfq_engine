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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_service(self):
        payload = {
            "query": document,
            "variables": {
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                # "serviceId": "592901047928754671",
                "serviceName": "XXXXXXXXXXXXXXXXXXXX",
                "serviceDescription": "XXXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateService",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_service(self):
        payload = {
            "query": document,
            "variables": {
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "serviceId": "13662447239293833711",
            },
            "operation_name": "deleteService",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_service(self):
        payload = {
            "query": document,
            "variables": {
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "serviceId": "592901047928754671",
            },
            "operation_name": "getService",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_service_list(self):
        payload = {
            "query": document,
            "variables": {
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getServiceList",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_service(self):
        payload = {
            "query": document,
            "variables": {
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "serviceId": "XXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "deleteService",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_service_provider(self):
        payload = {
            "query": document,
            "variables": {
                "serviceId": "592901047928754671",
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "serviceType": "XXXXXXXXXXXXXXXXXXXX",
                "serviceSpec": {},
                "uom": "hr",
                "basePricePerUom": 100,
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateServiceProvider",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_service_provider(self):
        payload = {
            "query": document,
            "variables": {
                "serviceId": "592901047928754671",
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "deleteServiceProvider",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_service_provider(self):
        payload = {
            "query": document,
            "variables": {
                "serviceId": "592901047928754671",
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "getServiceProvider",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_item(self):
        payload = {
            "query": document,
            "variables": {
                "itemType": "XXXXXXXXXXXXXXXXXXXX",
                "itemId": "1688715816992117231",
                "itemName": "XXXXXXXXXXXXXXXXXXXX",
                "itemDescription": "XXXXXXXXXXXXXXXXXXXX",
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateItem",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_item(self):
        payload = {
            "query": document,
            "variables": {
                "itemType": "XXXXXXXXXXXXXXXXXXXX",
                "itemId": "XXXXXXXXXXXXXXXXXXXX",
            },
            "operation_name": "deleteItem",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_item(self):
        payload = {
            "query": document,
            "variables": {
                "itemType": "XXXXXXXXXXXXXXXXXXXX",
                "itemId": "1688715816992117231",
            },
            "operation_name": "getItem",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_item_list(self):
        payload = {
            "query": document,
            "variables": {
                "itemType": "XXXXXXXXXXXXXXXXXXXX",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getItemList",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_product(self):
        payload = {
            "query": document,
            "variables": {
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "productId": "7642515695959085551",
                "sku": "abc",
                "productName": "XXXXXXXXXXXXXXXXXXXX",
                "productDescription": "XXXXXXXXXXXXXXXXXXXX",
                "uom": "kg",
                "basePricePerUom": 100,
                "data": {},
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateProduct",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_delete_product(self):
        payload = {
            "query": document,
            "variables": {
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "productId": "10203797220767175151",
            },
            "operation_name": "deleteProduct",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_product(self):
        payload = {
            "query": document,
            "variables": {
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "productId": "7642515695959085551",
            },
            "operation_name": "getProduct",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_product_list(self):
        payload = {
            "query": document,
            "variables": {
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getProductList",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
    def test_graphql_service_provider_list(self):
        payload = {
            "query": document,
            "variables": {
                "serviceId": "592901047928754671",
                "pageNumber": 1,
                "limit": 10,
            },
            "operation_name": "getServiceProviderList",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    # @unittest.skip("demonstrating skipping")
    def test_graphql_insert_update_quote_service(self):
        payload = {
            "query": document,
            "variables": {
                "quoteId": "10132984814893470191",
                "serviceId": "592901047928754671",
                "providerId": "XXXXXXXXXXXXXXXXXXXX",
                # "requestData": {},
                # "data": {},
                "pricePerUom": 100.0,
                "qty": 10,
                "updatedBy": "XYZ",
            },
            "operation_name": "insertUpdateQuoteService",
        }
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)

    @unittest.skip("demonstrating skipping")
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
        response = self.ai_rfq_engine.ai_rfq_graphql(**payload)
        logger.info(response)


if __name__ == "__main__":
    unittest.main()
