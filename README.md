# AI RFQ Engine

A comprehensive GraphQL-based Request for Quote (RFQ) management system built with Python, DynamoDB, and AWS Lambda. This engine provides intelligent quote generation, pricing management, and supplier relationship tools for B2B procurement workflows.

## 🚀 Features

### Core Functionality
- **Item Management**: Catalog management with support for multiple item types, specifications, and units of measure
- **Provider Management**: Supplier onboarding with item catalogs, pricing tiers, and batch tracking
- **RFQ Processing**: Automated quote request distribution and response collection
- **Quote Generation**: AI-powered quote generation with pricing optimization
- **Installment Planning**: Flexible payment scheduling and financial planning
- **File Management**: Document attachment and management for RFQ processes

### Advanced Features
- **Tiered Pricing**: Volume-based pricing with configurable tiers
- **Discount Rules**: Automated discount calculation based on business rules
- **Batch Tracking**: Lot/batch management for inventory control
- **Segment Management**: Customer segmentation for targeted pricing
- **Multi-Provider Support**: Competitive bidding across multiple suppliers

## 🏗️ Architecture

### Technology Stack
- **Backend**: Python 3.8+
- **Database**: Amazon DynamoDB
- **API**: GraphQL with Graphene
- **Cloud**: AWS Lambda (Serverless)
- **Framework**: SilvaEngine (Custom framework)

### Project Structure
```
ai_rfq_engine/
├── ai_rfq_engine/           # Main package
│   ├── handlers/            # Configuration and handlers
│   ├── models/              # Data models and business logic
│   ├── mutations/           # GraphQL mutations
│   ├── queries/             # GraphQL queries
│   ├── types/               # GraphQL type definitions
│   ├── tests/               # Test suite
│   ├── main.py              # Entry point and deployment config
│   └── schema.py            # GraphQL schema definition
├── pyproject.toml           # Project configuration
├── LICENSE                  # MIT License
└── README.md                # This file
```

## 📊 Data Model

### Core Entities

#### Items
- **Purpose**: Product/service catalog management
- **Key Fields**: `item_uuid`, `item_type`, `item_name`, `uom`, `item_description`
- **Features**: Hierarchical categorization, specification management

#### Providers & Provider Items
- **Purpose**: Supplier management and their product offerings
- **Key Fields**: `provider_item_uuid`, `item_uuid`, `base_price_per_uom`, `item_spec`
- **Features**: Multi-supplier support, competitive pricing

#### Segments & Contacts
- **Purpose**: Customer segmentation and contact management
- **Key Fields**: `segment_uuid`, `segment_name`, `email`
- **Features**: Targeted pricing, relationship management

#### Requests & Quotes
- **Purpose**: RFQ workflow management
- **Key Fields**: `request_uuid`, `quote_uuid`, `items[]`, `total_quote_amount`
- **Features**: Multi-item requests, automated quote generation

#### Pricing & Discounts
- **Purpose**: Dynamic pricing management
- **Key Fields**: `item_price_tier_uuid`, `discount_rule_uuid`, `quantity_ranges`
- **Features**: Volume discounts, rule-based pricing

### Database Schema
The system uses DynamoDB with the following table structure:

- `are-items`: Item catalog
- `are-segments`: Customer segments
- `are-segment-contacts`: Segment-contact relationships
- `are-provider-items`: Provider item catalog
- `are-provider-item-batches`: Batch/lot tracking
- `are-item-price-tiers`: Tiered pricing rules
- `are-discount-rules`: Discount calculation rules
- `are-requests`: RFQ requests
- `are-quotes`: Generated quotes
- `are-quote-items`: Quote line items
- `are-installments`: Payment schedules
- `are-files`: Document attachments

## 🔗 Model Relationships

The AI RFQ Engine implements a sophisticated relational data model using DynamoDB. Understanding these relationships is crucial for effective system usage and integration.

### Relationship Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    RFQ WORKFLOW RELATIONSHIPS                    │
└─────────────────────────────────────────────────────────────────┘

REQUEST (Hub Model)
    │
    ├─── (1:N) ──→ QUOTES
    │                  │
    │                  ├─── (1:N) ──→ QUOTE_ITEMS
    │                  │                  │
    │                  │                  ├─── (N:1) ──→ ITEMS
    │                  │                  │
    │                  │                  └─── (N:1) ──→ PROVIDER_ITEMS
    │                  │
    │                  └─── (1:N) ──→ INSTALLMENTS
    │
    └─── (1:N) ──→ FILES

┌─────────────────────────────────────────────────────────────────┐
│                   CATALOG & PRICING RELATIONSHIPS                │
└─────────────────────────────────────────────────────────────────┘

ITEMS (Core Catalog)
    │
    ├─── (1:N) ──→ PROVIDER_ITEMS
    │                  │
    │                  └─── (1:N) ──→ PROVIDER_ITEM_BATCHES
    │
    ├─── (1:N) ──→ ITEM_PRICE_TIERS
    │                  │
    │                  ├─── (N:1) ──→ SEGMENTS
    │                  │
    │                  └─── (N:1) ──→ PROVIDER_ITEMS
    │
    └─── (1:N) ──→ DISCOUNT_RULES
                       │
                       ├─── (N:1) ──→ SEGMENTS
                       │
                       └─── (N:1) ──→ PROVIDER_ITEMS

┌─────────────────────────────────────────────────────────────────┐
│                 CUSTOMER SEGMENTATION RELATIONSHIPS              │
└─────────────────────────────────────────────────────────────────┘

SEGMENTS
    │
    ├─── (1:N) ──→ SEGMENT_CONTACTS
    │
    ├─── (1:N) ──→ ITEM_PRICE_TIERS
    │
    └─── (1:N) ──→ DISCOUNT_RULES
```

### Core Relationship Patterns

#### 1. One-to-Many Relationships

These relationships are implemented via foreign key references (UUID fields) with cascading delete protections.

| Parent Model | Child Model | Foreign Key | Description |
|--------------|-------------|-------------|-------------|
| **Request** | Quote | `request_uuid` | One RFQ request can have multiple quotes from different suppliers |
| **Request** | File | `request_uuid` | One request can have multiple attached documents |
| **Quote** | QuoteItem | `quote_uuid` | One quote contains multiple line items |
| **Quote** | Installment | `quote_uuid` | One quote can have multiple payment installments |
| **Item** | ProviderItem | `item_uuid` | One item can be offered by multiple providers |
| **ProviderItem** | ProviderItemBatch | `provider_item_uuid` | One provider item can have multiple batches/lots |
| **Item** | ItemPriceTier | `item_uuid` | One item can have multiple price tiers |
| **Item** | DiscountRule | `item_uuid` | One item can have multiple discount rules |
| **Segment** | SegmentContact | `segment_uuid` | One segment can contain multiple contacts |
| **Segment** | ItemPriceTier | `segment_uuid` | One segment can have multiple pricing rules |
| **Segment** | DiscountRule | `segment_uuid` | One segment can have multiple discount rules |

**Cascading Delete Protection**: Parent models cannot be deleted if child records exist. For example:
- Cannot delete a `Request` if related `Quotes` exist
- Cannot delete a `ProviderItem` if related `QuoteItems`, `ItemPriceTiers`, or `ProviderItemBatches` exist
- Cannot delete a `Segment` if related `SegmentContacts` exist

#### 2. Many-to-One Relationships

Child models reference their parent via foreign key fields.

| Child Model | Parent Model | Foreign Key Field | Purpose |
|-------------|--------------|-------------------|---------|
| **Quote** | Request | `request_uuid` | Links quote back to originating request |
| **QuoteItem** | Quote | `quote_uuid` | Associates line item with specific quote |
| **QuoteItem** | Item | `item_uuid` | References the catalog item being quoted |
| **QuoteItem** | ProviderItem | `provider_item_uuid` | References supplier's specific item offering |
| **ProviderItem** | Item | `item_uuid` | Links provider offering to catalog item |
| **ProviderItemBatch** | ProviderItem | `provider_item_uuid` | Links batch to provider item |
| **ProviderItemBatch** | Item | `item_uuid` | Direct reference to catalog item |
| **ItemPriceTier** | Item | `item_uuid` | Associates pricing tier with catalog item |
| **ItemPriceTier** | ProviderItem | `provider_item_uuid` | Associates tier with specific provider |
| **ItemPriceTier** | Segment | `segment_uuid` | Applies pricing to specific customer segment |
| **DiscountRule** | Item | `item_uuid` | Associates discount rule with catalog item |
| **DiscountRule** | ProviderItem | `provider_item_uuid` | Associates rule with specific provider |
| **DiscountRule** | Segment | `segment_uuid` | Applies discount to specific customer segment |
| **SegmentContact** | Segment | `segment_uuid` | Links contact to customer segment |
| **File** | Request | `request_uuid` | Associates document with RFQ request |
| **Installment** | Quote | `quote_uuid` | Links payment to specific quote |

### Special Relationship Patterns

#### 3. Hierarchical Tier Relationships

Both **ItemPriceTier** and **DiscountRule** implement a sophisticated linked-list hierarchy where tiers/rules are ordered by their threshold values.

**ItemPriceTier Hierarchy Example**:
```
Tier 1: qty ≥ 0    AND qty < 100   → margin: 25%
Tier 2: qty ≥ 100  AND qty < 500   → margin: 20%  (points to Tier 1)
Tier 3: qty ≥ 500  AND qty < NULL  → margin: 15%  (points to Tier 2)
```

**DiscountRule Hierarchy Example**:
```
Rule 1: subtotal > 1000   AND subtotal < 5000  → max_discount: 5%
Rule 2: subtotal > 5000   AND subtotal < 10000 → max_discount: 10%  (points to Rule 1)
Rule 3: subtotal > 10000  AND subtotal < NULL  → max_discount: 15%  (points to Rule 2)
```

**Key Features**:
- **Auto-Linking**: When a new tier/rule is inserted, the system automatically updates the previous tier's upper bound (`quantity_less_then` or `subtotal_less_than`) to point to the new tier
- **Validation**: The system validates that new tiers maintain proper ordering
- **Gap-Free Coverage**: Ensures continuous coverage across all quantity/subtotal ranges
- **No Upper Limit**: The highest tier can have `NULL` as the upper bound, covering all values above the threshold

**Implementation Methods**:
- `_get_previous_tier()`: Finds the tier immediately below the new tier's threshold
- `_update_previous_tier()`: Updates the previous tier's upper bound to maintain continuity

#### 4. Calculated/Derived Relationships

Some models auto-calculate field values based on related data:

| Model | Calculated Field | Calculation Logic | Triggers |
|-------|------------------|-------------------|----------|
| **ProviderItemBatch** | `total_cost_per_uom` | `cost_per_uom + freight_cost_per_uom + additional_cost_per_uom` | Insert/Update |
| **ProviderItemBatch** | `guardrail_price_per_uom` | `total_cost_per_uom × (1 + guardrail_margin_per_uom/100)` | Insert/Update |
| **QuoteItem** | `price_per_uom` | Queries `ItemPriceTier` based on qty, segment, provider | Insert (auto-calculated) |
| **QuoteItem** | `subtotal` | `price_per_uom × qty` | Insert/Update |
| **QuoteItem** | `final_subtotal` | `subtotal - subtotal_discount` | Insert/Update |
| **Quote** | `total_quote_amount` | Sum of all related QuoteItem `subtotal` values | After QuoteItem change |
| **Quote** | `total_quote_discount` | Sum of all related QuoteItem `subtotal_discount` values | After QuoteItem change |
| **Quote** | `final_total_quote_amount` | `total_quote_amount - total_quote_discount + shipping_amount` | After QuoteItem change |
| **Installment** | `installment_ratio` | `(installment_amount / quote.final_total_quote_amount) × 100` | Insert/Update |

**Key Methods**:
- `QuoteItem.get_price_per_uom()`: Automatically finds the matching price tier and calculates price
- `Quote.update_quote_totals()`: Recalculates all quote totals from related quote items
- `Installment._calculate_installment_ratio()`: Auto-calculates payment ratio

### Composite Key Patterns

All models use DynamoDB's composite key pattern for efficient partitioning and querying:

| Model | Hash Key | Range Key | Purpose |
|-------|----------|-----------|---------|
| **Item** | `endpoint_id` | `item_uuid` | Partition by endpoint, unique items within endpoint |
| **Request** | `endpoint_id` | `request_uuid` | Partition by endpoint, chronological requests |
| **Quote** | `request_uuid` | `quote_uuid` | Partition by request, multiple quotes per request |
| **QuoteItem** | `quote_uuid` | `quote_item_uuid` | Partition by quote, line items per quote |
| **ProviderItem** | `endpoint_id` | `provider_item_uuid` | Partition by endpoint, provider catalog |
| **ProviderItemBatch** | `provider_item_uuid` | `batch_no` | Partition by provider item, batches per item |
| **ItemPriceTier** | `item_uuid` | `item_price_tier_uuid` | Partition by item, tiers per item |
| **DiscountRule** | `item_uuid` | `discount_rule_uuid` | Partition by item, rules per item |
| **Segment** | `endpoint_id` | `segment_uuid` | Partition by endpoint, segments per endpoint |
| **SegmentContact** | `endpoint_id` | `email` | Partition by endpoint, unique email per endpoint |
| **File** | `request_uuid` | `file_name` | Partition by request, unique filename per request |
| **Installment** | `quote_uuid` | `installment_uuid` | Partition by quote, installments per quote |

### Index Patterns

#### Local Secondary Indexes (LSI)
Share the same hash key as the primary table but provide alternative range keys:

| Model | Index Name | Hash Key | Range Key | Use Case |
|-------|------------|----------|-----------|----------|
| **Item** | `item_type-index` | `endpoint_id` | `item_type` | Query items by type |
| **Request** | `email-index` | `endpoint_id` | `email` | Query requests by customer email |
| **Quote** | `provider_corp_external_id-index` | `request_uuid` | `provider_corp_external_id` | Query quotes by provider |
| **QuoteItem** | `provider_item_uuid-index` | `quote_uuid` | `provider_item_uuid` | Query quote items by provider item |
| **QuoteItem** | `item_uuid-index` | `quote_uuid` | `item_uuid` | Query quote items by catalog item |
| **ProviderItem** | `item_uuid-index` | `endpoint_id` | `item_uuid` | Query provider items by catalog item |
| **ItemPriceTier** | `provider_item_uuid-index` | `item_uuid` | `provider_item_uuid` | Query price tiers by provider |
| **ItemPriceTier** | `segment_uuid-index` | `item_uuid` | `segment_uuid` | Query price tiers by segment |
| **DiscountRule** | `provider_item_uuid-index` | `item_uuid` | `provider_item_uuid` | Query discount rules by provider |
| **DiscountRule** | `segment_uuid-index` | `item_uuid` | `segment_uuid` | Query discount rules by segment |
| **Segment** | `provider_corp_external_id-index` | `endpoint_id` | `provider_corp_external_id` | Query segments by provider |
| **SegmentContact** | `segment_uuid-index` | `endpoint_id` | `segment_uuid` | Query contacts by segment |

#### Global Secondary Indexes (GSI)
Have different hash/range keys than the primary table:

| Model | Index Name | Hash Key | Range Key | Use Case |
|-------|------------|----------|-----------|----------|
| **Quote** | `provider_corp_external_id-quote_uuid-index` | `provider_corp_external_id` | `quote_uuid` | Query all quotes for a provider across all requests |
| **QuoteItem** | `item_uuid-provider_item_uuid-index` | `item_uuid` | `provider_item_uuid` | Query quote items by item and provider combination |

#### Updated_at Indexes
Nearly all models include an `updated_at-index` (LSI) for time-based queries and audit trails:

```graphql
# Query recent requests
query {
  requestList(
    fromUpdatedAt: "2024-01-01T00:00:00Z"
    toUpdatedAt: "2024-12-31T23:59:59Z"
    limit: 50
  ) {
    requestList {
      requestUuid
      requestTitle
      updatedAt
    }
  }
}
```

### Relationship Usage Examples

#### Example 1: Creating a Complete RFQ with Quote

```graphql
# Step 1: Create a Request
mutation {
  insertUpdateRequest(
    requestUuid: "req_001"
    email: "buyer@company.com"
    requestTitle: "Q1 2024 Steel Requirements"
    items: [{itemUuid: "item_001", quantity: 1000}]
    updatedBy: "buyer@company.com"
  ) {
    request { requestUuid }
  }
}

# Step 2: Create a Quote (linked via request_uuid)
mutation {
  insertUpdateQuote(
    requestUuid: "req_001"
    quoteUuid: "quote_001"
    providerCorpExternalId: "SUPPLIER_ABC"
    salesRepEmail: "sales@supplier.com"
    updatedBy: "sales@supplier.com"
  ) {
    quote { quoteUuid }
  }
}

# Step 3: Add Quote Items (linked via quote_uuid and item_uuid)
# The price_per_uom is automatically calculated from ItemPriceTiers
mutation {
  insertUpdateQuoteItem(
    quoteUuid: "quote_001"
    quoteItemUuid: "qi_001"
    providerItemUuid: "pi_001"
    itemUuid: "item_001"
    segmentUuid: "seg_premium"
    qty: 1000
    requestUuid: "req_001"
    updatedBy: "sales@supplier.com"
  ) {
    quoteItem {
      quoteItemUuid
      pricePerUom      # Auto-calculated
      subtotal         # Auto-calculated
      finalSubtotal    # Auto-calculated
    }
  }
}

# Step 4: Quote totals are automatically recalculated
# Query to see updated quote totals
query {
  quote(requestUuid: "req_001", quoteUuid: "quote_001") {
    totalQuoteAmount      # Sum of all quote item subtotals
    totalQuoteDiscount    # Sum of all quote item discounts
    finalTotalQuoteAmount # Total with shipping
  }
}

# Step 5: Add Installment Plan (linked via quote_uuid)
mutation {
  insertUpdateInstallment(
    quoteUuid: "quote_001"
    installmentUuid: "inst_001"
    priority: 1
    installmentAmount: 10000.00
    scheduledDate: "2024-06-01T00:00:00Z"
    paymentMethod: "bank_transfer"
    updatedBy: "finance@company.com"
  ) {
    installment {
      installmentUuid
      installmentRatio  # Auto-calculated as percentage of quote total
    }
  }
}
```

#### Example 2: Setting Up Tiered Pricing for an Item

```graphql
# Step 1: Create an Item
mutation {
  insertUpdateItem(
    itemUuid: "item_steel_001"
    itemType: "raw_material"
    itemName: "Stainless Steel Sheet"
    uom: "kg"
    updatedBy: "admin@company.com"
  ) {
    item { itemUuid }
  }
}

# Step 2: Create Provider Item (linked via item_uuid)
mutation {
  insertUpdateProviderItem(
    providerItemUuid: "pi_steel_001"
    itemUuid: "item_steel_001"
    providerCorpExternalId: "STEEL_SUPPLIER_001"
    basePricePerUom: 30.00
    updatedBy: "supplier@company.com"
  ) {
    providerItem { providerItemUuid }
  }
}

# Step 3: Create Provider Item Batches (linked via provider_item_uuid)
mutation {
  insertUpdateProviderItemBatch(
    providerItemUuid: "pi_steel_001"
    batchNo: "BATCH_2024_001"
    itemUuid: "item_steel_001"
    costPerUom: 20.00
    freightCostPerUom: 2.00
    additionalCostPerUom: 1.00
    guardrailMarginPerUom: 25.0
    updatedBy: "supplier@company.com"
  ) {
    providerItemBatch {
      totalCostPerUom        # Auto-calculated: 23.00
      guardrailPricePerUom   # Auto-calculated: 28.75
    }
  }
}

# Step 4: Create Customer Segment
mutation {
  insertUpdateSegment(
    segmentUuid: "seg_premium"
    segmentName: "Premium Customers"
    updatedBy: "admin@company.com"
  ) {
    segment { segmentUuid }
  }
}

# Step 5: Create Tiered Pricing (linked via item_uuid, provider_item_uuid, segment_uuid)
# Tier 1: 0-100 kg
mutation {
  insertUpdateItemPriceTier(
    itemUuid: "item_steel_001"
    itemPriceTierUuid: "tier_001"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    quantityGreaterThen: 0
    quantityLessThen: 100
    marginPerUom: 0.30
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    itemPriceTier {
      quantityGreaterThen
      quantityLessThen
      marginPerUom
    }
  }
}

# Tier 2: 100-500 kg
# This automatically updates Tier 1's quantityLessThen to 100
mutation {
  insertUpdateItemPriceTier(
    itemUuid: "item_steel_001"
    itemPriceTierUuid: "tier_002"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    quantityGreaterThen: 100
    quantityLessThen: 500
    marginPerUom: 0.25
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    itemPriceTier {
      quantityGreaterThen
      quantityLessThen
      marginPerUom
    }
  }
}

# Tier 3: 500+ kg (no upper limit)
# This automatically updates Tier 2's quantityLessThen to 500
mutation {
  insertUpdateItemPriceTier(
    itemUuid: "item_steel_001"
    itemPriceTierUuid: "tier_003"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    quantityGreaterThen: 500
    marginPerUom: 0.20
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    itemPriceTier {
      quantityGreaterThen
      quantityLessThen      # Will be null (no upper limit)
      marginPerUom
    }
  }
}

# Step 6: Query Price Tiers for Specific Quantity
# Database-level filtering with quantityValue parameter
query {
  itemPriceTierList(
    itemUuid: "item_steel_001"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    quantityValue: 250.0    # Filters at database level
    status: "active"
  ) {
    itemPriceTierList {
      itemPriceTierUuid
      quantityGreaterThen   # Will return tier_002 (100-500)
      quantityLessThen
      marginPerUom          # 0.25
    }
  }
}

# Step 7: Create Discount Rules (parallel hierarchy to price tiers)
# Rule 1: Subtotal $1,000 - $5,000
mutation {
  insertUpdateDiscountRule(
    itemUuid: "item_steel_001"
    discountRuleUuid: "discount_001"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    subtotalGreaterThan: 1000.0    # Must be > 0
    subtotalLessThan: 5000.0
    maxDiscountPercentage: 5.0
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    discountRule { discountRuleUuid }
  }
}

# Rule 2: Subtotal $5,000+
# This automatically updates Rule 1's subtotalLessThan to 5000
mutation {
  insertUpdateDiscountRule(
    itemUuid: "item_steel_001"
    discountRuleUuid: "discount_002"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    subtotalGreaterThan: 5000.0
    maxDiscountPercentage: 10.0
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    discountRule {
      subtotalGreaterThan
      subtotalLessThan      # Will be null (no upper limit)
      maxDiscountPercentage
    }
  }
}

# Query Discount Rules for Specific Subtotal
# Database-level filtering with subtotalValue parameter
query {
  discountRuleList(
    itemUuid: "item_steel_001"
    providerItemUuid: "pi_steel_001"
    segmentUuid: "seg_premium"
    subtotalValue: 12500.0  # Filters at database level
    status: "active"
  ) {
    discountRuleList {
      discountRuleUuid
      subtotalGreaterThan   # Will return discount_002 (>$5,000)
      subtotalLessThan
      maxDiscountPercentage # 10.0
    }
  }
}
```

#### Example 3: Querying Related Data Across Models

```graphql
# Find all quotes for a specific request with their items
query {
  quoteList(requestUuid: "req_001") {
    quoteList {
      quoteUuid
      providerCorpExternalId
      totalQuoteAmount
      finalTotalQuoteAmount
      quoteItems {            # Related QuoteItems
        quoteItemUuid
        itemUuid
        qty
        pricePerUom
        subtotal
        item {                # Related Item via item_uuid
          itemName
          itemType
          uom
        }
        providerItem {        # Related ProviderItem via provider_item_uuid
          basePricePerUom
          itemSpec
        }
      }
      installments {          # Related Installments
        installmentUuid
        installmentAmount
        installmentRatio
        scheduledDate
      }
    }
  }
}

# Find all provider items for a specific catalog item
query {
  providerItemList(itemUuid: "item_steel_001") {
    providerItemList {
      providerItemUuid
      providerCorpExternalId
      basePricePerUom
      batches {               # Related ProviderItemBatches
        batchNo
        totalCostPerUom
        guardrailPricePerUom
        inStock
        slowMoveItem
      }
      priceTiers {            # Related ItemPriceTiers
        quantityGreaterThen
        quantityLessThen
        marginPerUom
        pricePerUom
        segment {             # Related Segment
          segmentName
        }
      }
    }
  }
}

# Find all requests for a customer email
query {
  requestList(emails: ["buyer@company.com"]) {
    requestList {
      requestUuid
      requestTitle
      status
      quotes {                # Related Quotes
        quoteUuid
        providerCorpExternalId
        finalTotalQuoteAmount
      }
      files {                 # Related Files
        fileName
        fileSize
        fileType
      }
    }
  }
}

# Find all contacts in a segment
query {
  segmentContactList(segmentUuid: "seg_premium") {
    segmentContactList {
      email
      contactUuid
      consumerCorpExternalId
      segment {               # Related Segment
        segmentName
        segmentDescription
      }
    }
  }
}
```

### Relationship Validation Rules

#### Insert/Update Validation
1. **Foreign Key Existence**: When creating a child record, the system validates that the parent record exists
   - Example: Cannot create a `Quote` without a valid `Request`
   - Example: Cannot create a `QuoteItem` without valid `Quote`, `Item`, and `ProviderItem`

2. **Tier Ordering**: When creating price tiers or discount rules, the system validates proper ordering
   - New tier's `quantity_greater_then` must be greater than existing tiers
   - No overlapping ranges allowed

3. **Segment Assignment**: Price tiers and discount rules must reference valid segments

#### Delete Validation
1. **Cascading Delete Prevention**: Cannot delete parent records if children exist
   - Example: Cannot delete `Request` if `Quotes` exist
   - Example: Cannot delete `ProviderItem` if `QuoteItems` reference it

2. **Orphan Prevention**: System prevents creation of orphaned records

### Best Practices for Working with Relationships

1. **Creating Related Records**: Always create parent records before children
   ```
   Request → Quote → QuoteItem → Installment
   Item → ProviderItem → ProviderItemBatch
   Item → ItemPriceTier (with Segment)
   ```

2. **Querying Related Data**: Use indexes for efficient queries
   - Use LSI for queries within the same partition
   - Use GSI for cross-partition queries
   - Leverage `updated_at` indexes for time-based queries

3. **Updating Calculated Fields**: Let the system handle calculations
   - Don't manually set `total_quote_amount` - it's auto-calculated
   - Don't manually set `installment_ratio` - it's auto-calculated
   - Don't manually set `total_cost_per_uom` - it's auto-calculated

4. **Deleting Records**: Check for dependencies first
   - Query child records before attempting delete
   - Use appropriate delete mutations that check for dependencies

5. **Pricing Queries**: Use database-level filtering for performance
   - Use `quantityValue` parameter in `itemPriceTierList` queries
   - Use `subtotalValue` parameter in `discountRuleList` queries
   - This reduces memory usage and improves response times

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- AWS Account with DynamoDB access
- AWS CLI configured

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ai_rfq_engine
```

2. **Install dependencies**
```bash
pip install -e .
```

3. **Install development dependencies**
```bash
pip install -e ".[dev,test]"
```

### Configuration

1. **Environment Setup**
Create a `.env` file with your AWS credentials:
```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
ENDPOINT_ID=your_endpoint_id
EXECUTE_MODE=local_for_all
```

2. **Database Initialization**
The system automatically creates DynamoDB tables when running in local mode.

### Running the Application

#### Local Development
```bash
# Set environment for local development
export EXECUTE_MODE=local_for_all

# Run tests to verify setup
pytest ai_rfq_engine/tests/ -v
```

#### AWS Lambda Deployment
The system is designed for serverless deployment on AWS Lambda. Use the `deploy()` function in `main.py` for deployment configuration.

## 📖 API Documentation

### GraphQL Endpoint
The system exposes a single GraphQL endpoint that handles all operations.

#### Authentication
```http
POST /core/{endpoint_id}/ai_rfq_graphql
Content-Type: application/json
x-api-key: your-api-key
```

### Core Operations

#### Ping Test
```graphql
query {
  ping
}
```

#### Items Management
```graphql
# Create/Update Item
mutation {
  insertUpdateItem(
    itemUuid: "123456789"
    itemType: "raw_material"
    itemName: "Steel Plate"
    itemDescription: "High grade steel plate"
    uom: "kg"
    updatedBy: "user@example.com"
  ) {
    item {
      itemUuid
      itemName
      itemType
    }
  }
}

# Query Items
query {
  itemList(itemType: "raw_material", limit: 10) {
    itemList {
      itemUuid
      itemName
      itemType
      uom
    }
    total
  }
}

# Delete Item
mutation {
  deleteItem(itemUuid: "123456789") {
    ok
  }
}
```

#### Segment Management
```graphql
# Create/Update Segment
mutation {
  insertUpdateSegment(
    segmentUuid: "seg_123"
    segmentName: "Premium Customers"
    segmentDescription: "High value customer segment"
    updatedBy: "admin@company.com"
  ) {
    segment {
      segmentUuid
      segmentName
    }
  }
}

# Query Segments
query {
  segmentList(limit: 10) {
    segmentList {
      segmentUuid
      segmentName
      segmentDescription
    }
    total
  }
}
```

#### Provider Item Management
```graphql
# Create/Update Provider Item
mutation {
  insertUpdateProviderItem(
    providerItemUuid: "pi_123"
    itemUuid: "123456789"
    providerCorpExternalId: "SUPPLIER_001"
    basePricePerUom: 25.50
    itemSpec: "Grade A steel specification"
    updatedBy: "supplier@company.com"
  ) {
    providerItem {
      providerItemUuid
      basePricePerUom
      itemSpec
    }
  }
}
```

#### RFQ Management
```graphql
# Create Request
mutation {
  insertUpdateRequest(
    requestUuid: "req_123"
    email: "buyer@company.com"
    requestTitle: "Q1 Steel Requirements"
    items: [
      {
        itemUuid: "123456789"
        quantity: 1000
        specifications: "Grade A steel"
      }
    ]
    updatedBy: "buyer@company.com"
  ) {
    request {
      requestUuid
      requestTitle
      status
    }
  }
}

# Generate Quote
mutation {
  insertUpdateQuote(
    requestUuid: "req_123"
    quoteUuid: "quote_456"
    providerCorpExternalId: "SUPPLIER_001"
    salesRepEmail: "sales@supplier.com"
    updatedBy: "sales@supplier.com"
  ) {
    quote {
      quoteUuid
      totalQuoteAmount
      status
    }
  }
}

# Add Quote Items
# Note: price_per_uom is automatically calculated from item price tiers
# based on qty, segment_uuid, and provider_item_uuid
mutation {
  insertUpdateQuoteItem(
    quoteUuid: "quote_456"
    quoteItemUuid: "qi_789"
    providerItemUuid: "pi_123"
    itemUuid: "123456789"
    segmentUuid: "seg_123"
    qty: 1000
    requestUuid: "req_123"
    updatedBy: "sales@supplier.com"
  ) {
    quoteItem {
      quoteItemUuid
      pricePerUom
      qty
      subtotal
      finalSubtotal
    }
  }
}
```

#### Pricing Management
```graphql
# Create Price Tier
mutation {
  insertUpdateItemPriceTier(
    itemUuid: "123456789"
    itemPriceTierUuid: "tier_001"
    quantityGreaterThen: 100
    quantityLessThen: 500
    marginPerUom: 0.15
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    itemPriceTier {
      itemPriceTierUuid
      marginPerUom
      status
    }
  }
}

# Query Price Tiers with Quantity Filtering
# The quantity_value parameter efficiently filters tiers at the database level
query {
  itemPriceTierList(
    itemUuid: "123456789"
    providerItemUuid: "pi_123"
    segmentUuid: "seg_123"
    quantityValue: 250.0
    status: "active"
  ) {
    itemPriceTierList {
      itemPriceTierUuid
      quantityGreaterThen
      quantityLessThen
      marginPerUom
      pricePerUom
    }
    total
  }
}

# Create Discount Rule
# Note: subtotalGreaterThan must be greater than 0 (cannot be 0)
# The system automatically manages tiered discount rules
mutation {
  insertUpdateDiscountRule(
    itemUuid: "123456789"
    discountRuleUuid: "discount_001"
    providerItemUuid: "pi_123"
    segmentUuid: "seg_123"
    subtotalGreaterThan: 1000.0
    maxDiscountPercentage: 10.0
    status: "active"
    updatedBy: "admin@company.com"
  ) {
    discountRule {
      discountRuleUuid
      subtotalGreaterThan
      subtotalLessThan
      maxDiscountPercentage
      status
    }
  }
}

# Query Discount Rules with Subtotal Filtering
# The subtotal_value parameter efficiently filters rules at the database level
query {
  discountRuleList(
    itemUuid: "123456789"
    providerItemUuid: "pi_123"
    segmentUuid: "seg_123"
    subtotalValue: 12500.0
    status: "active"
  ) {
    discountRuleList {
      discountRuleUuid
      subtotalGreaterThan
      subtotalLessThan
      maxDiscountPercentage
    }
    total
  }
}
```

#### Payment Management
```graphql
# Create Installment
mutation {
  insertUpdateInstallment(
    quoteUuid: "quote_456"
    installmentUuid: "inst_001"
    priority: 1
    scheduledDate: "2024-06-01T00:00:00Z"
    installmentAmount: 5000.00
    paymentMethod: "bank_transfer"
    updatedBy: "finance@company.com"
  ) {
    installment {
      installmentUuid
      installmentRatio
      scheduledDate
    }
  }
}
```

#### File Management
```graphql
# Upload File
mutation {
  insertUpdateFile(
    requestUuid: "req_123"
    fileName: "specifications.pdf"
    email: "buyer@company.com"
    fileContent: "base64_encoded_content"
    fileSize: 1024
    fileType: "application/pdf"
    updatedBy: "buyer@company.com"
  ) {
    file {
      fileName
      fileSize
      fileType
    }
  }
}
```

### Advanced Filtering

Most list operations support advanced filtering:

```graphql
# Advanced Item Search
query {
  itemList(
    itemType: "raw_material"
    itemName: "steel"
    uoms: ["kg", "ton"]
    limit: 20
    pageNumber: 0
  ) {
    itemList {
      itemUuid
      itemName
      itemType
      uom
    }
    total
    pageSize
    pageNumber
  }
}

# Date Range Queries
query {
  requestList(
    fromExpiredAt: "2024-01-01T00:00:00Z"
    toExpiredAt: "2024-12-31T23:59:59Z"
    statuses: ["active", "pending"]
    limit: 50
  ) {
    requestList {
      requestUuid
      requestTitle
      status
      expiredAt
    }
    total
  }
}

# Price Range Filtering
query {
  quoteList(
    minTotalQuoteAmount: 1000.0
    maxTotalQuoteAmount: 50000.0
    statuses: ["submitted", "approved"]
  ) {
    quoteList {
      quoteUuid
      totalQuoteAmount
      finalTotalQuoteAmount
      status
    }
    total
  }
}
```

## 🧪 Testing

### Test Suite
The project includes comprehensive tests covering all major functionality.

```bash
# Run all tests
pytest ai_rfq_engine/tests/ -v

# Run specific test categories
pytest ai_rfq_engine/tests/ -m unit -v          # Unit tests only
pytest ai_rfq_engine/tests/ -m integration -v   # Integration tests only

# Run tests for specific functionality
pytest ai_rfq_engine/tests/ -k "item" -v        # Item-related tests

# Run with coverage
pytest ai_rfq_engine/tests/ --cov=ai_rfq_engine --cov-report=html
```

### Test Data
Tests use externalized JSON data in `ai_rfq_engine/tests/test_data.json` for easy maintenance and modification.

### Environment Variables for Testing
```bash
# Run specific test functions
AI_RFQ_TEST_FUNCTION=item pytest ai_rfq_engine/tests/ -v

# Run with specific markers
AI_RFQ_TEST_MARKERS=integration pytest ai_rfq_engine/tests/ -v
```

## 🚀 Deployment

### Local Development Setup

1. **Environment Configuration**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev,test]"
```

2. **Environment Variables**
```env
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_DEFAULT_REGION=us-east-1
ENDPOINT_ID=your_endpoint_id
EXECUTE_MODE=local_for_all
```

### AWS Lambda Deployment

1. **Package for Deployment**
```bash
# Create deployment package
mkdir deployment
cp -r ai_rfq_engine deployment/
cp requirements.txt deployment/
cd deployment

# Install dependencies
pip install -r requirements.txt -t .

# Create ZIP file
zip -r ai_rfq_engine.zip .
```

2. **Lambda Function Creation**
```bash
# Create Lambda function
aws lambda create-function \
    --function-name ai-rfq-engine \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
    --handler ai_rfq_engine.main.lambda_handler \
    --zip-file fileb://ai_rfq_engine.zip \
    --timeout 300 \
    --memory-size 512
```

3. **Environment Variables**
```bash
aws lambda update-function-configuration \
    --function-name ai-rfq-engine \
    --environment Variables='{
        "ENDPOINT_ID":"your_endpoint_id",
        "SOURCE_EMAIL":"noreply@yourcompany.com",
        "EXECUTE_MODE":"production"
    }'
```

### Database Setup

The system automatically creates DynamoDB tables when running in local mode. For production:

1. **Enable Point-in-Time Recovery**
```bash
aws dynamodb put-backup-policy \
    --table-name are-items \
    --backup-policy PointInTimeRecoveryEnabled=true
```

2. **Create Backup**
```bash
aws dynamodb create-backup \
    --table-name are-items \
    --backup-name are-items-backup-$(date +%Y%m%d)
```

### Monitoring

1. **CloudWatch Logs**
```bash
aws logs put-retention-policy \
    --log-group-name /aws/lambda/ai-rfq-engine \
    --retention-in-days 30
```

2. **Health Check**
```graphql
query {
  ping  # Returns current timestamp if system is healthy
}
```

## 🔧 Development

### Code Quality
The project uses several tools to maintain code quality:

```bash
# Code formatting
black ai_rfq_engine/

# Linting
flake8 ai_rfq_engine/

# Type checking
mypy ai_rfq_engine/
```

### Adding New Features

1. **Models**: Add new data models in `ai_rfq_engine/models/`
2. **Types**: Define GraphQL types in `ai_rfq_engine/types/`
3. **Queries**: Add query resolvers in `ai_rfq_engine/queries/`
4. **Mutations**: Add mutation resolvers in `ai_rfq_engine/mutations/`
5. **Tests**: Add corresponding tests in `ai_rfq_engine/tests/`

### Development Workflow

1. **Create Feature Branch**
```bash
git checkout -b feature/your-feature-name
```

2. **Make Changes**
- Write code following style guidelines
- Add tests for new functionality
- Update documentation as needed

3. **Test Changes**
```bash
pytest ai_rfq_engine/tests/ -v
black ai_rfq_engine/
flake8 ai_rfq_engine/
```

4. **Commit and Push**
```bash
git add .
git commit -m "feat: add new feature description"
git push origin feature/your-feature-name
```

## 🤝 Contributing

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation for API changes
- Use type hints where appropriate

### Code Style

```python
# Variables and functions: snake_case
user_name = "john_doe"
def calculate_total_price():
    pass

# Classes: PascalCase
class ItemModel:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Bug Reports

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

## 🔒 Security

### API Key Management
- Generate strong API keys using `openssl rand -hex 32`
- Store keys securely in AWS Secrets Manager
- Rotate keys regularly

### IAM Permissions
Create minimal privilege IAM role for Lambda:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/are-*"
        }
    ]
}
```

### Data Protection
- Enable DynamoDB encryption at rest
- Use HTTPS only for API endpoints
- Implement comprehensive input validation

## 🆘 Troubleshooting

### Common Issues

#### Table Creation Failures
```python
# Check AWS credentials and permissions
import boto3
dynamodb = boto3.client('dynamodb')
try:
    response = dynamodb.list_tables()
    print("DynamoDB access successful")
except Exception as e:
    print(f"DynamoDB access failed: {e}")
```

#### Lambda Timeout Issues
- Increase timeout in Lambda configuration
- Optimize query performance
- Use pagination for large datasets

#### Memory Issues
- Increase memory allocation
- Optimize data processing
- Use streaming for large responses

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
import os
os.environ['LOG_LEVEL'] = 'DEBUG'
```

### Performance Optimization
- Use appropriate DynamoDB indexes
- Implement pagination for large datasets
- Cache frequently accessed data
- Process data in chunks for large operations

## 📚 API Reference

### Postman Collection
A comprehensive Postman collection is available at `ai_rfq_postman_collection.json` with examples for all API operations.

### Error Handling
The API returns standard GraphQL errors with additional context:

```json
{
  "errors": [
    {
      "message": "Item with UUID '123' does not exist",
      "locations": [{"line": 2, "column": 3}],
      "path": ["insertUpdateProviderItem"]
    }
  ],
  "data": null
}
```

### Rate Limiting
- 1000 requests per minute per API key
- Burst limit of 100 requests per second

### Data Types

#### Custom Scalars
- **DateTime**: ISO 8601 formatted date-time strings
- **JSON**: Arbitrary JSON objects for flexible data storage

#### Enums
- **Item Types**: `raw_material`, `finished_good`, `service`, `component`
- **Status**: `initial`, `draft`, `submitted`, `under_review`, `approved`, `rejected`, `expired`
- **Payment Methods**: `credit_card`, `bank_transfer`, `check`, `net_terms`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Changelog

### Recent Updates - Performance Optimization

#### Enhanced
- **Price Tier Filtering**: Optimized item price tier queries to use database-level filtering with `quantityValue` parameter instead of application-level filtering. This significantly improves performance when querying price tiers for specific quantities.
- **Discount Rule Filtering**: Enhanced discount rule queries to use database-level filtering with `subtotalValue` parameter for more efficient rule matching.
- **Quote Item Creation**: Improved automatic price calculation in quote items to leverage the optimized tier filtering for better performance.

#### Changed
- **Item Price Tier Queries**: The `itemPriceTierList` query now supports `quantityValue` parameter that filters tiers at the database level, returning only tiers that match the specified quantity.
- **Discount Rule Queries**: The `discountRuleList` query now supports `subtotalValue` parameter that filters rules at the database level, returning only rules that match the specified subtotal.
- **Quote Item Mutations**: Quote item creation now automatically calculates `pricePerUom` from item price tiers based on quantity, segment, and provider item.

#### Benefits
- Reduced application memory usage by filtering at the database layer
- Faster query response times for pricing lookups
- More scalable pricing engine for high-volume quote generation

### Version 0.0.1 - Initial Release

#### Added
- **Core Features**: Complete GraphQL API with queries and mutations
- **Item Management**: Full CRUD operations for product/service catalog
- **Provider Management**: Supplier onboarding and item catalog management
- **RFQ Processing**: Request for Quote creation and management
- **Quote Generation**: Automated quote creation with line items
- **Pricing Engine**: Tiered pricing and discount rule management
- **Payment Scheduling**: Installment planning and management
- **File Management**: Document attachment system for RFQ processes

#### Technical Details
- **Database**: DynamoDB integration with auto table creation
- **Authentication**: API key-based authentication
- **Testing**: Comprehensive test suite with parametrized data
- **Deployment**: AWS Lambda deployment configuration
- **Monitoring**: CloudWatch integration and health checks

#### Dependencies
- `graphene>=3.0`: GraphQL framework
- `pendulum>=2.0`: Date/time handling
- `tenacity>=8.0`: Retry mechanisms
- `SilvaEngine-DynamoDB-Base`: Custom DynamoDB framework
- `SilvaEngine-Utility`: Utility functions

## 🆘 Support

### Documentation
- Complete API examples in this README
- Test data documentation in `ai_rfq_engine/tests/README_TEST_DATA.md`
- Postman collection for API testing

### Getting Help
1. Check this documentation for common solutions
2. Review the test examples for usage patterns
3. Use the Postman collection for API testing
4. Check GitHub Issues for known problems

### Contact
- **Author**: Idea Bosque
- **Email**: ideabosque@gmail.com
- **Issues**: Use GitHub Issues for bug reports and feature requests

---

**Built with ❤️ using Python and AWS**