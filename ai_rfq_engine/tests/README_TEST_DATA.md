# Test Data Generation

This directory contains scripts for generating comprehensive test data for the AI RFQ Engine.

## Quick Start

### Basic Test Data (Without Quote Items)

```bash
python ai_rfq_engine/tests/load_sample_data.py
```

This creates:
- 3 segments
- 15 segment contacts (5 per segment)
- 20 items with corresponding provider items
- 40 provider item batches (2 per provider item)
- 80 item price tiers (4 tiers × 20 items)
- 80 discount prompts (4 scopes × 20 items)
- 5 requests
- 10 quotes (2 per request)
- 20 installments (2 per quote)

**Total: ~293 records**

### Full Test Data (Including Quote Items)

Due to DynamoDB eventual consistency, quote items must be created separately:

```bash
# Step 1: Create base test data
python ai_rfq_engine/tests/load_sample_data.py

# Step 2: Wait 2-3 minutes for DynamoDB to propagate

# Step 3: Create quote items
python ai_rfq_engine/tests/create_quote_items.py
```

This adds:
- 30 quote items (3 per quote × 10 quotes)

**Total: ~323 records**

## Why Two Scripts?

### DynamoDB Eventual Consistency Issue

Quote item creation has a chicken-and-egg problem with DynamoDB's eventual consistency:

1. **Quote items require price tiers**: When creating a quote item, the system must query price tiers to calculate pricing
2. **Price tier queries use GSI**: The price tier query uses a Global Secondary Index for efficient filtering
3. **GSI reads are eventually consistent**: GSIs cannot use consistent reads and may take 30-180 seconds to reflect new data
4. **Single-script delays are impractical**: Even with 90-120 second delays, quote item creation still fails

### The Solution

By splitting the process into two scripts:
- `load_sample_data.py` creates all base data including price tiers
- User waits 2-3 minutes for DynamoDB eventual consistency
- `create_quote_items.py` creates quote items using now-available price tiers

This ensures reliable test data generation without requiring 3+ minute delays in a single script run.

## Test Data Output

Both scripts save data to `ai_rfq_engine/tests/test_data.json` which contains:
- UUIDs of all created entities
- Test parameters for GraphQL queries
- Structured data for automated testing

## Configuration

### Customizing Data Volume

Edit `load_sample_data.py` to change these constants:

```python
NUM_SEGMENTS = 3  # Number of customer segments
NUM_CONTACTS_PER_SEGMENT = 5  # Contacts per segment
NUM_ITEMS = 20  # Catalog items
NUM_BATCHES_PER_PROVIDER_ITEM = 2  # Inventory batches
NUM_REQUESTS = 5  # RFQ requests
NUM_QUOTES_PER_REQUEST = 2  # Quotes per request
NUM_INSTALLMENTS_PER_QUOTE = 2  # Payment installments per quote
```

Edit `create_quote_items.py` to change:

```python
NUM_QUOTE_ITEMS_PER_QUOTE = 3  # Line items per quote
```

### Partition Key

Both scripts use `partition_key = "TENANT001"`. Change this in the Engine initialization if needed:

```python
engine = Engine(
    name="AI RFQ Engine",
    engine_type="graphql",
    event={},
    metadata={
        "partition_key": "YOUR_TENANT_ID",  # Change this
        "endpoint_id": "ENDPOINT001",
        "part_id": "MAIN",
    },
)
```

## Troubleshooting

### Quote Items Still Failing After 3 Minutes

If `create_quote_items.py` still reports failures:

1. **Wait longer**: DynamoDB eventual consistency can occasionally take 5+ minutes
2. **Check price tiers exist**: Verify price tiers were created in the first script
3. **Verify segment UUID matches**: Ensure both scripts use the same first segment UUID
4. **Run again**: Simply re-run `create_quote_items.py` after waiting

### No Segments/Items/Quotes Found

This means `test_data.json` is missing or incomplete. Run `load_sample_data.py` first.

### Permission Errors

Ensure the IAM role/user has DynamoDB permissions for:
- PutItem
- GetItem
- Query
- Scan
- UpdateItem

## Architecture Notes

### Partition Key Migration

This test data generation uses the new `partition_key` approach:
- All models use `partition_key` as the hash key (not `endpoint_id`)
- `endpoint_id` and `part_id` are maintained as regular attributes for backward compatibility
- All utility functions in `models/utils.py` use `partition_key` for lookups

### Price Tier Calculation

Price tiers are created with:
- 4 quantity tiers per item: 0, 100, 500, 1000 units
- Decreasing margins for higher quantities (bulk discounts)
- All tiers assigned to the first segment for consistency
- Both margin-based and batch-cost-based pricing supported

### Discount Prompts

Four hierarchical scopes are created:
- **GLOBAL**: Applies to all quotes in the partition
- **SEGMENT**: Applies to specific customer segments
- **ITEM**: Applies to specific catalog items
- **PROVIDER_ITEM**: Applies to specific provider offerings

## Related Files

- `load_sample_data.py` - Main test data generation script
- `create_quote_items.py` - Quote item creation (run after delay)
- `test_data.json` - Generated test data output
- `test_graphql_*.py` - Test files that use this data

## Migration from endpoint_id

If you have existing test data created with `endpoint_id`:

1. The new scripts create data with `partition_key = "TENANT001"`
2. Old data with different endpoint_ids will not conflict
3. Update test queries to use the new partition_key value
4. Consider archiving or deleting old test data to avoid confusion
