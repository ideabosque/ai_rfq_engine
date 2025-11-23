import json
import os
import random
import uuid
from datetime import datetime, timedelta

import pendulum
import requests
from dotenv import load_dotenv
try:
    from faker import Faker
    fake = Faker()
except ModuleNotFoundError:
    print("The 'faker' package is not installed. Please install it by running 'pip install faker'")
    exit(1)

# Load .env from current directory (tests folder)
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# --- CONFIGURATION ---
endpoint_id = os.getenv("endpoint_id")
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
UPDATED_BY = "data_loader_script"

NUM_SEGMENTS = 3
NUM_CONTACTS_PER_SEGMENT = 5
NUM_ITEMS = 20
NUM_BATCHES_PER_ITEM = 2
NUM_REQUESTS = 5
NUM_QUOTES_PER_REQUEST = 2
NUM_QUOTE_ITEMS_PER_QUOTE = 3
NUM_INSTALLMENTS_PER_QUOTE = 2
NUM_FILES_PER_REQUEST = 1

# --- INITIALIZATION ---
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def run_graphql_mutation(query, variables):
    """A helper function to execute a GraphQL mutation."""
    payload = json.dumps({"query": query, "variables": variables})
    response = requests.post(
        API_URL.format(endpoint_id=endpoint_id), headers=headers, data=payload
    )
    response.raise_for_status()
    result = response.json()
    if "errors" in result:
        print("GraphQL Error:", json.dumps(result["errors"], indent=2))
        return None
    print(f"  -> Success: {query.strip().splitlines()[0]} ...")
    return result["data"]


def generate_and_load_data():
    """Main function to generate and load all data."""

    # --- DATA STORAGE ---
    # These will map our locally generated IDs to the actual UUIDs returned by the API
    segment_map = {}
    item_map = {}
    provider_item_map = {}

    # 1. Segments
    print("--- Loading Segments ---")
    local_segments = []
    for i in range(NUM_SEGMENTS):
        local_segments.append(
            {
                "local_id": str(uuid.uuid4()),
                "name": f"{fake.company()} Tier",
                "description": fake.catch_phrase(),
            }
        )

    for segment_data in local_segments:
        print(f"Creating Segment: {segment_data['name']}...")
        mutation = """
        mutation InsertUpdateSegment($name: String, $desc: String, $by: String!) {
            insertUpdateSegment(segmentName: $name, segmentDescription: $desc, updatedBy: $by) {
                segment { segmentUuid }
            }
        }
        """
        variables = {
            "name": segment_data["name"],
            "desc": segment_data["description"],
            "by": UPDATED_BY,
        }
        result = run_graphql_mutation(mutation, variables)
        if result:
            api_uuid = result["insertUpdateSegment"]["segment"]["segmentUuid"]
            segment_map[segment_data["local_id"]] = api_uuid
            print(f"  -> Success. API UUID: {api_uuid}")

    # 2. Segment Contacts
    print("\n--- Loading Segment Contacts ---")
    for local_id, api_uuid in segment_map.items():
        for _ in range(NUM_CONTACTS_PER_SEGMENT):
            email = fake.email()
            print(f"Creating Contact: {email} for Segment {api_uuid}...")
            mutation = """
            mutation InsertUpdateSegmentContact($sid: String!, $email: String!, $cid: String, $by: String!) {
                insertUpdateSegmentContact(segmentUuid: $sid, email: $email, consumerCorpExternalId: $cid, updatedBy: $by) {
                    segmentContact { contactUuid }
                }
            }
            """
            variables = {
                "sid": api_uuid,
                "email": email,
                "cid": f"CUST-{random.randint(1000, 9999)}",
                "by": UPDATED_BY,
            }
            result = run_graphql_mutation(mutation, variables)
            if result:
                print(f"  -> Success.")

    # 3. Items & Provider Items
    print("\n--- Loading Items & Provider Items ---")
    local_items = []
    for _ in range(NUM_ITEMS):
        local_items.append(
            {
                "local_id": str(uuid.uuid4()),
                "name": fake.bs().title(),
                "description": fake.sentence(),
                "uom": random.choice(["each", "kg", "case", "pallet"]),
            }
        )

    for item_data in local_items:
        print(f"Creating Item: {item_data['name']}...")
        mutation = """
        mutation InsertUpdateItem($type: String, $name: String, $desc: String, $uom: String, $by: String!) {
            insertUpdateItem(itemType: $type, itemName: $name, itemDescription: $desc, uom: $uom, updatedBy: $by) {
                item { itemUuid }
            }
        }
        """
        variables = {
            "type": "product",
            "name": item_data["name"],
            "desc": item_data["description"],
            "uom": item_data["uom"],
            "by": UPDATED_BY,
        }
        item_result = run_graphql_mutation(mutation, variables)
        if item_result:
            item_api_uuid = item_result["insertUpdateItem"]["item"]["itemUuid"]
            item_map[item_data["local_id"]] = item_api_uuid
            print(f"  -> Item Success. API UUID: {item_api_uuid}")

            print(f"  -> Creating corresponding Provider Item...")
            prov_mutation = """
            mutation InsertUpdateProviderItem($itemId: String!, $provId: String, $price: Float, $by: String!) {
                insertUpdateProviderItem(itemUuid: $itemId, providerCorpExternalId: $provId, basePricePerUom: $price, updatedBy: $by) {
                    providerItem { providerItemUuid }
                }
            }
            """
            prov_variables = {
                "itemId": item_api_uuid,
                "provId": f"PROV-{random.randint(100, 999)}",
                "price": round(random.uniform(10.0, 500.0), 2),
                "by": UPDATED_BY,
            }
            prov_result = run_graphql_mutation(prov_mutation, prov_variables)
            if prov_result:
                prov_api_uuid = prov_result["insertUpdateProviderItem"]["providerItem"][
                    "providerItemUuid"
                ]
                provider_item_map[item_data["local_id"]] = prov_api_uuid
                print(f"    -> Provider Item Success. API UUID: {prov_api_uuid}")

    # 4. Provider Item Batches
    print(
        "\n--- Loading Provider Item Batches ---\n"
    )  # Added newline for better formatting
    for local_item_id, item_api_uuid in item_map.items():
        if local_item_id in provider_item_map:
            provider_item_api_uuid = provider_item_map[local_item_id]
            for i in range(NUM_BATCHES_PER_ITEM):
                batch_no = f"B-{random.randint(10000, 99999)}"
                print(
                    f"Creating Batch: {batch_no} for Provider Item {provider_item_api_uuid}..."
                )
                now = pendulum.now("UTC")
                produced = (
                    now - timedelta(days=random.randint(10, 100))
                ).isoformat()
                expires = (
                    now + timedelta(days=random.randint(90, 730))
                ).isoformat()
                mutation = """
                mutation InsertUpdateProviderItemBatch($pid: String!, $iid: String!, $bno: String!, $exp: DateTime, $prod: DateTime, $cost: Float, $addCost: Float, $freightCost: Float, $stock: Boolean, $by: String!) {
                    insertUpdateProviderItemBatch(providerItemUuid: $pid, itemUuid: $iid, batchNo: $bno, expiredAt: $exp, producedAt: $prod, costPerUom: $cost, additionalCostPerUom: $addCost, freightCostPerUom: $freightCost, inStock: $stock, updatedBy: $by) {
                        providerItemBatch { batchNo }
                    }
                }
                """
                variables = {
                    "pid": provider_item_api_uuid,
                    "iid": item_api_uuid,
                    "bno": batch_no,
                    "exp": expires,
                    "prod": produced,
                    "cost": round(random.uniform(5.0, 450.0), 2),
                    "addCost": round(random.uniform(0.5, 50.0), 2),
                    "freightCost": round(random.uniform(0.5, 30.0), 2),
                    "stock": True,
                    "by": UPDATED_BY,
                }
                result = run_graphql_mutation(mutation, variables)
                if result:
                    print(f"  -> Success.")


    # 6. Quotes
    # print("\n--- Loading Quotes ---")
    # for local_req_id, req_api_uuid in request_map.items():
    #     for _ in range(NUM_QUOTES_PER_REQUEST):
    #         local_quote_id = str(uuid.uuid4())
    #         provider_corp_id = f"SUPPLIER-{random.randint(100, 999)}"
    #         sales_rep_email = fake.email()
    #         shipping_method = random.choice(["AIR", "SEA", "LAND"])
    #         shipping_amount = round(random.uniform(50.0, 500.0), 2)

    #         print(f"Creating Quote: {local_quote_id} for Request {req_api_uuid}...")
    #         mutation = """
    #         mutation InsertUpdateQuote($reqId: String!, $quoteId: String!, $provCorpId: String, $salesEmail: String, $shipMethod: String, $shipAmount: Float, $by: String!) {
    #             insertUpdateQuote(requestUuid: $reqId, quoteUuid: $quoteId, providerCorpExternalId: $provCorpId, salesRepEmail: $salesEmail, shippingMethod: $shipMethod, shippingAmount: $shipAmount, updatedBy: $by) {
    #                 quote { quoteUuid }
    #             }
    #         }
    #         """
    #         variables = {
    #             "reqId": req_api_uuid,
    #             "quoteId": local_quote_id,
    #             "provCorpId": provider_corp_id,
    #             "salesEmail": sales_rep_email,
    #             "shipMethod": shipping_method,
    #             "shipAmount": shipping_amount,
    #             "by": UPDATED_BY,
    #         }
    #         result = run_graphql_mutation(mutation, variables)
    #         if result:
    #             api_uuid = result["insertUpdateQuote"]["quote"]["quoteUuid"]
    #             # Store a tuple (request_uuid, quote_uuid) for easier lookup in quote items
    #             quote_map[local_quote_id] = (req_api_uuid, api_uuid)
    #             print(f"  -> Quote Success. API UUID: {api_uuid}")

    # 7. Quote Items
    # print("\n--- Loading Quote Items ---")
    # if not item_map or not provider_item_map or not segment_map:
    #     print("Not enough data to create Quote Items. Skipping.")
    # else:
    #     for local_quote_id, (req_api_uuid, quote_api_uuid) in quote_map.items():
    #         for _ in range(NUM_QUOTE_ITEMS_PER_QUOTE):
    #             local_quote_item_id = str(uuid.uuid4())

    #             # Select a random item, provider item, and segment
    #             random_item_local_id = random.choice(list(item_map.keys()))
    #             item_api_uuid = item_map[random_item_local_id]
    #             provider_item_api_uuid = provider_item_map.get(
    #                 random_item_local_id
    #             )  # ensure it exists
    #             if not provider_item_api_uuid:
    #                 continue  # Skip if no provider item for this item

    #             # Use the same segment for which price tiers and discounts were created
    #             segment_api_uuid = first_segment_api_uuid

    #             qty = random.randint(10, 1000)

    #             print(
    #                 f"Creating Quote Item {local_quote_item_id} for Quote {quote_api_uuid}..."
    #             )
    #             mutation = """
    #             mutation InsertUpdateQuoteItem($quoteId: String!, $quoteItemId: String!, $provItemId: String!, $itemId: String!, $segId: String!, $qty: Float!, $reqId: String!, $by: String!) {
    #                 insertUpdateQuoteItem(quoteUuid: $quoteId, quoteItemUuid: $quoteItemId, providerItemUuid: $provItemId, itemUuid: $itemId, segmentUuid: $segId, qty: $qty, requestUuid: $reqId, updatedBy: $by) {
    #                     quoteItem { quoteItemUuid pricePerUom subtotal finalSubtotal }
    #                 }
    #             }
    #             """
    #             variables = {
    #                 "quoteId": quote_api_uuid,
    #                 "quoteItemId": local_quote_item_id,
    #                 "provItemId": provider_item_api_uuid,
    #                 "itemId": item_api_uuid,
    #                 "segId": segment_api_uuid,
    #                 "qty": float(qty),
    #                 "reqId": req_api_uuid,
    #                 "by": UPDATED_BY,
    #             }
    #             result = run_graphql_mutation(mutation, variables)
    #             if result:
    #                 api_uuid = result["insertUpdateQuoteItem"]["quoteItem"][
    #                     "quoteItemUuid"
    #                 ]
    #                 quote_item_map[local_quote_item_id] = api_uuid
    #                 print(f"  -> Quote Item Success. API UUID: {api_uuid}")

    # 8. Installments
    # print("\n--- Loading Installments ---")
    # for local_quote_id, (req_api_uuid, quote_api_uuid) in quote_map.items():
    #     for i in range(NUM_INSTALLMENTS_PER_QUOTE):
    #         local_installment_id = str(uuid.uuid4())
    #         scheduled_date = (pendulum.now("UTC").add(weeks=i + 1)).isoformat()
    #         payment_method = random.choice(
    #             ["bank_transfer", "credit_card", "net_terms"]
    #         )
    #         installment_amount = round(random.uniform(100.0, 5000.0), 2)

    #         print(
    #             f"Creating Installment {local_installment_id} for Quote {quote_api_uuid}..."
    #         )
    #         mutation = """
    #         mutation InsertUpdateInstallment($quoteId: String!, $instId: String!, $priority: Int!, $scheduledDate: DateTime!, $instAmount: Float!, $payMethod: String!, $by: String!) {
    #             insertUpdateInstallment(quoteUuid: $quoteId, installmentUuid: $instId, priority: $priority, scheduledDate: $scheduledDate, installmentAmount: $instAmount, paymentMethod: $payMethod, updatedBy: $by) {
    #                 installment { installmentUuid installmentRatio }
    #             }
    #         }
    #         """
    #         variables = {
    #             "quoteId": quote_api_uuid,
    #             "instId": local_installment_id,
    #             "priority": i + 1,
    #             "scheduledDate": scheduled_date,
    #             "instAmount": installment_amount,
    #             "payMethod": payment_method,
    #             "by": UPDATED_BY,
    #         }
    #         result = run_graphql_mutation(mutation, variables)
    #         if result:
    #             api_uuid = result["insertUpdateInstallment"]["installment"][
    #                 "installmentUuid"
    #             ]
    #             installment_map[local_installment_id] = api_uuid
    #             print(f"  -> Installment Success. API UUID: {api_uuid}")


    # 10. Item Price Tiers & Discount Rules
    print(
        "\n--- Loading Item Price Tiers & Discount Rules ---\n"
    )  # Added newline for better formatting
    if not segment_map:
        print("No segments created, skipping price tiers and discount rules.")
        return

    # Use the first created segment for all price tiers and discount rules
    first_segment_api_uuid = list(segment_map.values())[0]

    for local_item_id, item_api_uuid in item_map.items():
        if local_item_id in provider_item_map:
            # Use the first segment for this item
            segment_api_uuid = first_segment_api_uuid
            provider_item_api_uuid = provider_item_map[local_item_id]

            # Create multiple Price Tiers with increasing quantity thresholds
            tier_configs = [
                {
                    "qty": 0,
                    "margin": round(random.uniform(15.0, 20.0), 2),
                },  # Base tier\
                {
                    "qty": 100,
                    "margin": round(random.uniform(12.0, 15.0), 2),
                },  # Mid tier\
                {
                    "qty": 500,
                    "margin": round(random.uniform(10.0, 12.0), 2),
                },  # High tier\
                {
                    "qty": 1000,
                    "margin": round(random.uniform(8.0, 10.0), 2),
                },  # Bulk tier\
            ]
            for tier_config in tier_configs:
                print(
                    f"Creating Price Tier for Item {item_api_uuid} (qty > {tier_config['qty']}) in Segment {segment_api_uuid}..."
                )
                tier_mutation = """
                mutation InsertUpdateItemPriceTier($iid: String!, $pid: String, $sid: String, $qty: Float, $margin: Float, $stat: String, $by: String!) {
                    insertUpdateItemPriceTier(itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid, quantityGreaterThen: $qty, marginPerUom: $margin, status: $stat, updatedBy: $by) {
                        itemPriceTier { itemPriceTierUuid }
                    }
                }
                """
                tier_variables = {
                    "iid": item_api_uuid,
                    "pid": provider_item_api_uuid,
                    "sid": segment_api_uuid,
                    "qty": float(tier_config["qty"]),
                    "margin": tier_config["margin"],
                    "stat": "active",
                    "by": UPDATED_BY,
                }
                tier_result = run_graphql_mutation(tier_mutation, tier_variables)
                if tier_result:
                    print(f"  -> Success.")

            # Create multiple Discount Rules with increasing subtotal thresholds
            discount_configs = [
                {
                    "subtotal": 100,
                    "discount": round(random.uniform(2.0, 5.0), 1),
                },  # Small orders\
                {
                    "subtotal": 1000,
                    "discount": round(random.uniform(5.0, 10.0), 1),
                },  # Medium orders\
                {
                    "subtotal": 5000,
                    "discount": round(random.uniform(10.0, 15.0), 1),
                },  # Large orders\
                {
                    "subtotal": 10000,
                    "discount": round(random.uniform(15.0, 20.0), 1),
                },  # VIP orders\
                {
                    "subtotal": 25000,
                    "discount": round(random.uniform(20.0, 25.0), 1),
                },  # Enterprise orders\
            ]
            for discount_config in discount_configs:
                print(
                    f"Creating Discount Rule for Item {item_api_uuid} (subtotal > {discount_config['subtotal']}) in Segment {segment_api_uuid}..."
                )
                rule_mutation = """
                mutation InsertUpdateDiscountRule($iid: String!, $pid: String, $sid: String, $subtotal: Float, $perc: Float, $stat: String, $by: String!) {
                    insertUpdateDiscountRule(itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid, subtotalGreaterThan: $subtotal, maxDiscountPercentage: $perc, status: $stat, updatedBy: $by) {
                        discountRule { discountRuleUuid }
                    }
                }
                """
                rule_variables = {
                    "iid": item_api_uuid,
                    "pid": provider_item_api_uuid,
                    "sid": segment_api_uuid,
                    "subtotal": float(discount_config["subtotal"]),
                    "perc": discount_config["discount"],
                    "stat": "active",
                    "by": UPDATED_BY,
                }
                rule_result = run_graphql_mutation(rule_mutation, rule_variables)
                if rule_result:
                    print(f"  -> Success.")


if __name__ == "__main__":
    generate_and_load_data()
    print("\n--- Data Loading Complete ---")
