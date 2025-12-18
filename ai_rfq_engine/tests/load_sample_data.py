import json
import logging
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

import pendulum
from dotenv import load_dotenv

# Load .env from current directory (tests folder) before setting up paths
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Ensure local packages are importable (mirrors conftest.py setup)
BASE_DIR = os.getenv("base_dir") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "silvaengine_utility"))
sys.path.insert(1, os.path.join(BASE_DIR, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(BASE_DIR, "ai_rfq_engine"))

from silvaengine_utility.serializer import Serializer  # noqa: E402

from ai_rfq_engine import AIRFQEngine  # noqa: E402

try:
    from faker import Faker

    fake = Faker()
except ModuleNotFoundError:
    print(
        "The 'faker' package is not installed. Please install it by running 'pip install faker'"
    )
    exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("load_sample_data")

# --- CONFIGURATION ---
endpoint_id = os.getenv("endpoint_id")
part_id = os.getenv("part_id")
UPDATED_BY = "data_loader_script"
TEST_DATA_FILE = os.path.join(os.path.dirname(__file__), "test_data.json")

SETTING = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_rfq_graphql": {
            "module_name": "ai_rfq_engine",
            "class_name": "AIRFQEngine",
        },
    },
    "endpoint_id": endpoint_id,
    "part_id": part_id,
    "execute_mode": os.getenv("execute_mode", "local"),
}

NUM_SEGMENTS = 3
NUM_CONTACTS_PER_SEGMENT = 5
NUM_ITEMS = 20
NUM_BATCHES_PER_ITEM = 2
NUM_REQUESTS = 5
NUM_QUOTES_PER_REQUEST = 2
NUM_QUOTE_ITEMS_PER_QUOTE = 3
NUM_INSTALLMENTS_PER_QUOTE = 2
NUM_FILES_PER_REQUEST = 1


def create_engine():
    """Instantiate AIRFQEngine using environment-driven settings."""
    try:
        engine = AIRFQEngine(logger, **SETTING)
        setattr(engine, "__is_real__", True)
        return engine
    except Exception as exc:
        logger.error(f"Failed to initialize AIRFQEngine: {exc}", exc_info=True)
        raise


def run_graphql_mutation(engine, query, variables):
    """Execute a GraphQL mutation through the local engine."""
    try:
        response = engine.ai_rfq_graphql(
            query=query,
            variables=variables,
            endpoint_id=endpoint_id,
            part_id=part_id,
        )
        parsed = (
            Serializer.json_loads(response)
            if isinstance(response, (str, bytes))
            else response
        )
    except Exception as exc:
        print(f"GraphQL execution failed: {exc}")
        return None

    if parsed.get("errors"):
        print("GraphQL Error:", Serializer.json_dumps(parsed["errors"]))
        return None

    data = parsed.get("data")
    if not data:
        print("GraphQL Error: No data returned.")
        return None

    print(f"  -> Success: {query.strip().splitlines()[0]} ...")
    return data


def persist_test_data(test_data_updates):
    """Override test_data.json with newly generated data."""
    # For each entity type, randomly select one entry for get/list test data
    final_data = {}

    for key, records in test_data_updates.items():
        if not records:
            continue

        # For main test data, include all records
        if not key.endswith("_get_test_data") and not key.endswith("_list_test_data"):
            final_data[key] = records
        # For get/list test data, randomly pick one entry
        else:
            final_data[key] = [random.choice(records)]

    with open(TEST_DATA_FILE, "w") as f:
        json.dump(final_data, f, indent=2)
    print(f"\nTest data written to: {TEST_DATA_FILE}")


def generate_and_load_data(engine):
    """Main function to generate and load all data."""

    # --- DATA STORAGE ---
    # These will map our locally generated IDs to the actual UUIDs returned by the API
    segment_map = {}
    item_map = {}
    provider_item_map = {}
    test_data_updates = {
        "segment_test_data": [],
        "segment_get_test_data": [],
        "segment_list_test_data": [],
        "segment_contact_test_data": [],
        "segment_contact_get_test_data": [],
        "segment_contact_list_test_data": [],
        "item_test_data": [],
        "item_get_test_data": [],
        "item_list_test_data": [],
        "provider_item_test_data": [],
        "provider_item_get_test_data": [],
        "provider_item_list_test_data": [],
        "provider_item_batch_test_data": [],
        "provider_item_batch_get_test_data": [],
        "provider_item_batch_list_test_data": [],
        "item_price_tier_test_data": [],
        "item_price_tier_get_test_data": [],
        "item_price_tier_list_test_data": [],
        "discount_prompt_test_data": [],
        "discount_prompt_get_test_data": [],
        "discount_prompt_list_test_data": [],
    }

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
        result = run_graphql_mutation(engine, mutation, variables)
        if result:
            api_uuid = result["insertUpdateSegment"]["segment"]["segmentUuid"]
            segment_map[segment_data["local_id"]] = api_uuid
            print(f"  -> Success. API UUID: {api_uuid}")
            test_data_updates["segment_test_data"].append(
                {
                    "segmentUuid": api_uuid,
                    "segmentName": segment_data["name"],
                    "segmentDescription": segment_data["description"],
                    "updatedBy": UPDATED_BY,
                }
            )
            test_data_updates["segment_get_test_data"].append({"segmentUuid": api_uuid})
            test_data_updates["segment_list_test_data"].append(
                {"limit": 10, "offset": 0}
            )

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
            result = run_graphql_mutation(engine, mutation, variables)
            if result:
                print(f"  -> Success.")
                contact_uuid = result["insertUpdateSegmentContact"]["segmentContact"][
                    "contactUuid"
                ]
                test_data_updates["segment_contact_test_data"].append(
                    {
                        "segmentUuid": api_uuid,
                        "email": email,
                        "contactUuid": contact_uuid,
                        "consumerCorpExternalId": variables["cid"],
                        "updatedBy": UPDATED_BY,
                    }
                )
                test_data_updates["segment_contact_get_test_data"].append(
                    {"segmentUuid": api_uuid, "email": email}
                )
                test_data_updates["segment_contact_list_test_data"].append(
                    {"segmentUuid": api_uuid, "limit": 10, "offset": 0}
                )

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
        item_result = run_graphql_mutation(engine, mutation, variables)
        if item_result:
            item_api_uuid = item_result["insertUpdateItem"]["item"]["itemUuid"]
            item_map[item_data["local_id"]] = item_api_uuid
            print(f"  -> Item Success. API UUID: {item_api_uuid}")
            test_data_updates["item_test_data"].append(
                {
                    "itemUuid": item_api_uuid,
                    "itemType": variables["type"],
                    "itemName": item_data["name"],
                    "itemDescription": item_data["description"],
                    "uom": item_data["uom"],
                    "updatedBy": UPDATED_BY,
                }
            )
            test_data_updates["item_get_test_data"].append({"itemUuid": item_api_uuid})
            test_data_updates["item_list_test_data"].append({"limit": 10, "offset": 0})

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
            prov_result = run_graphql_mutation(engine, prov_mutation, prov_variables)
            if prov_result:
                prov_api_uuid = prov_result["insertUpdateProviderItem"]["providerItem"][
                    "providerItemUuid"
                ]
                provider_item_map[item_data["local_id"]] = prov_api_uuid
                print(f"    -> Provider Item Success. API UUID: {prov_api_uuid}")
                test_data_updates["provider_item_test_data"].append(
                    {
                        "providerItemUuid": prov_api_uuid,
                        "itemUuid": item_api_uuid,
                        "providerCorpExternalId": prov_variables["provId"],
                        "basePricePerUom": prov_variables["price"],
                        "updatedBy": UPDATED_BY,
                    }
                )
                test_data_updates["provider_item_get_test_data"].append(
                    {"providerItemUuid": prov_api_uuid}
                )
                test_data_updates["provider_item_list_test_data"].append(
                    {"itemUuid": item_api_uuid, "limit": 10, "offset": 0}
                )

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
                produced = (now - timedelta(days=random.randint(10, 100))).isoformat()
                expires = (now + timedelta(days=random.randint(90, 730))).isoformat()
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
                result = run_graphql_mutation(engine, mutation, variables)
                if result:
                    print(f"  -> Success.")
                    test_data_updates["provider_item_batch_test_data"].append(
                        {
                            "providerItemUuid": variables["pid"],
                            "batchNo": batch_no,
                            "itemUuid": variables["iid"],
                            "expiredAt": expires,
                            "producedAt": produced,
                            "costPerUom": variables["cost"],
                            "freightCostPerUom": variables["freightCost"],
                            "additionalCostPerUom": variables["addCost"],
                            "inStock": True,
                            "updatedBy": UPDATED_BY,
                        }
                    )
                    test_data_updates["provider_item_batch_get_test_data"].append(
                        {"providerItemUuid": variables["pid"], "batchNo": batch_no}
                    )
                    test_data_updates["provider_item_batch_list_test_data"].append(
                        {"providerItemUuid": variables["pid"], "limit": 10, "offset": 0}
                    )

    # 5. Item Price Tiers & Discount Prompts
    print(
        "\n--- Loading Item Price Tiers & Discount Prompts ---\n"
    )  # Added newline for better formatting
    if not segment_map:
        print("No segments created, skipping price tiers and discount prompts.")
        persist_test_data(test_data_updates)
        return

    # Use the first created segment for all price tiers and discount prompts
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
                tier_result = run_graphql_mutation(
                    engine, tier_mutation, tier_variables
                )
                if tier_result:
                    print(f"  -> Success.")
                    tier_uuid = tier_result["insertUpdateItemPriceTier"][
                        "itemPriceTier"
                    ]["itemPriceTierUuid"]
                    test_data_updates["item_price_tier_test_data"].append(
                        {
                            "itemUuid": item_api_uuid,
                            "itemPriceTierUuid": tier_uuid,
                            "providerItemUuid": provider_item_api_uuid,
                            "segmentUuid": segment_api_uuid,
                            "quantityGreaterThen": tier_config["qty"],
                            "marginPerUom": tier_config["margin"],
                            "status": "active",
                            "updatedBy": UPDATED_BY,
                        }
                    )
                    test_data_updates["item_price_tier_get_test_data"].append(
                        {"itemUuid": item_api_uuid, "itemPriceTierUuid": tier_uuid}
                    )
                    test_data_updates["item_price_tier_list_test_data"].append(
                        {"itemUuid": item_api_uuid, "limit": 10, "offset": 0}
                    )

            # Create multiple Discount Prompts with different scopes
            prompt_configs = [
                {
                    "scope": "global",
                    "prompt_text": "Apply volume discount for orders over $1000",
                    "tags": [],
                },
                {
                    "scope": "segment",
                    "prompt_text": "Special segment pricing available",
                    "tags": [segment_api_uuid],
                },
                {
                    "scope": "item",
                    "prompt_text": f"Bulk discount available for this item",
                    "tags": [item_api_uuid],
                },
                {
                    "scope": "provider_item",
                    "prompt_text": f"Provider-specific pricing rules apply",
                    "tags": [provider_item_api_uuid],
                },
            ]
            for prompt_config in prompt_configs:
                print(
                    f"Creating Discount Prompt for scope {prompt_config['scope']} (Item {item_api_uuid})..."
                )
                prompt_mutation = """
                mutation InsertUpdateDiscountPrompt($scope: String!, $tags: [String], $prompt: String!, $stat: String, $by: String!) {
                    insertUpdateDiscountPrompt(scope: $scope, tags: $tags, discountPrompt: $prompt, status: $stat, updatedBy: $by) {
                        discountPrompt { discountPromptUuid }
                    }
                }
                """
                prompt_variables = {
                    "scope": prompt_config["scope"],
                    "tags": prompt_config["tags"],
                    "prompt": prompt_config["prompt_text"],
                    "stat": "active",
                    "by": UPDATED_BY,
                }
                prompt_result = run_graphql_mutation(
                    engine, prompt_mutation, prompt_variables
                )
                if prompt_result:
                    print(f"  -> Success.")
                    discount_prompt_uuid = prompt_result["insertUpdateDiscountPrompt"][
                        "discountPrompt"
                    ]["discountPromptUuid"]
                    test_data_updates["discount_prompt_test_data"].append(
                        {
                            "discountPromptUuid": discount_prompt_uuid,
                            "scope": prompt_config["scope"],
                            "tags": prompt_config["tags"],
                            "discountPrompt": prompt_config["prompt_text"],
                            "status": "active",
                            "updatedBy": UPDATED_BY,
                        }
                    )
                    test_data_updates["discount_prompt_get_test_data"].append(
                        {
                            "discountPromptUuid": discount_prompt_uuid,
                        }
                    )
                    test_data_updates["discount_prompt_list_test_data"].append(
                        {"scope": prompt_config["scope"], "limit": 10, "offset": 0}
                    )

    # Persist generated data for tests
    persist_test_data(test_data_updates)


if __name__ == "__main__":
    engine_instance = create_engine()
    generate_and_load_data(engine_instance)
    print("\n--- Data Loading Complete ---")
