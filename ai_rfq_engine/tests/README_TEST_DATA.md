# AI RFQ Engine Test Data

## Overview

This directory contains the test suite for the AI RFQ Engine. Test data is externalized in a JSON file for easy maintenance and modification.

## Test Data File

**File**: `test_data.json`

This file contains all test data used by the parametrized tests. The data is organized by entity type.

## Structure

```json
{
  "item_test_data": [...],
  "segment_test_data": [...],
  "segment_contact_test_data": [...],
  "provider_item_test_data": [...],
  "provider_item_batch_test_data": [...],
  "item_price_tier_test_data": [...],
  "discount_rule_test_data": [...],
  "request_test_data": [...],
  "quote_test_data": [...],
  "quote_item_test_data": [...],
  "installment_test_data": [...],
  "file_test_data": [...]
}
```

Each key contains an array of test cases. Each array element represents one test scenario that will be run.

## Adding New Test Cases

To add new test cases, simply edit `test_data.json` and add new objects to the appropriate array:

```json
{
  "item_test_data": [
    {
      "itemUuid": "89151803645574004864",
      "itemType": "raw_material",
      "itemName": "Steel Plate",
      ...
    },
    {
      "itemUuid": "12345678901234567890",
      "itemType": "finished_good",
      "itemName": "Widget",
      ...
    }
  ]
}
```

The test will automatically run for each object in the array.

## Test Execution

### Run All Tests
```bash
pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -v
```

### Run Only Unit Tests
```bash
pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -m unit -v
```

### Run Only Integration Tests
```bash
pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -m integration -v
```

### Run Specific Test Function
```bash
pytest ai_rfq_engine/tests/test_ai_rfq_engine.py::test_graphql_insert_update_item_py -v
```

### Run Tests Matching a Pattern
```bash
pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -k "item" -v
```

### Using Environment Variables
```bash
# Run tests matching function name
AI_RFQ_TEST_FUNCTION=item pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -v

# Run tests with specific markers
AI_RFQ_TEST_MARKERS=integration pytest ai_rfq_engine/tests/test_ai_rfq_engine.py -v
```

## Test Data Categories

### Item Test Data
- **Purpose**: Test item CRUD operations
- **Key Fields**: itemUuid, itemType, itemName, itemDescription, uom, itemExternalId

### Segment Test Data
- **Purpose**: Test customer segment management
- **Key Fields**: segmentUuid, segmentName, segmentDescription

### Segment Contact Test Data
- **Purpose**: Test segment-contact associations
- **Key Fields**: segmentUuid, email

### Provider Item Test Data
- **Purpose**: Test provider item configurations
- **Key Fields**: providerItemUuid, itemUuid, basePricePerUom, itemSpec

### Provider Item Batch Test Data
- **Purpose**: Test batch/lot tracking for provider items
- **Key Fields**: providerItemUuid, batchNo, expiredAt, producedAt, costPerUom

### Item Price Tier Test Data
- **Purpose**: Test tiered pricing rules
- **Key Fields**: itemPriceTierUuid, quantityGreaterThen, quantityLessThen, marginPerUom

### Discount Rule Test Data
- **Purpose**: Test discount calculation rules
- **Key Fields**: discountRuleUuid, subtotalGreaterThan, subtotalLessThan, maxDiscountPercentage

### Request Test Data
- **Purpose**: Test RFQ request creation and management
- **Key Fields**: requestUuid, email, requestTitle, billingAddress, shippingAddress, items

### Quote Test Data
- **Purpose**: Test quote generation and management
- **Key Fields**: quoteUuid, requestUuid, providerCorpExternalId, totalQuoteAmount

### Quote Item Test Data
- **Purpose**: Test individual items within quotes
- **Key Fields**: quoteItemUuid, quoteUuid, itemUuid, pricePerUom, qty, subtotal

### Installment Test Data
- **Purpose**: Test payment installment schedules
- **Key Fields**: installmentUuid, quoteUuid, scheduledDate, installmentAmount, paymentMethod
- **Note**: The `installmentRatio` is automatically calculated based on `installmentAmount` and the quote's `finalTotalQuoteAmount`. It cannot be manually set via mutation.

### File Test Data
- **Purpose**: Test file attachments to requests
- **Key Fields**: requestUuid, fileName, email

## Benefits of JSON-Based Test Data

1. **Easy Maintenance**: Non-developers can update test data without touching Python code
2. **Version Control**: Test data changes are tracked separately from code changes
3. **Reusability**: Same test data can be used across different test suites
4. **Scalability**: Easy to add new test scenarios by adding JSON objects
5. **Clarity**: Test data is clearly separated from test logic

## Troubleshooting

### Test Data Not Loading
If you see warnings about missing test data:
```
WARNING - Test data file not found: /path/to/test_data.json
```

Ensure `test_data.json` exists in the same directory as `test_ai_rfq_engine.py`.

### JSON Parse Errors
If you see JSON parsing errors:
```
ERROR - Error parsing test data JSON: ...
```

Validate your JSON using a JSON validator (e.g., jsonlint.com) to ensure proper syntax.

## Logging

The test suite provides comprehensive logging:
- Test start/end with execution time
- GraphQL query being executed
- Test data being used
- Method call details with correlation IDs
- Results and errors

All logs are output to stdout with timestamps and log levels.
