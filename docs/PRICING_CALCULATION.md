# Pricing Calculation System Documentation

## Overview

The AI RFQ Engine implements a sophisticated, multi-layered pricing calculation system that connects several interconnected models. The pricing system is segment-based, provider-specific, and supports tiered pricing with batch-level cost variations and margin calculations.

## Table of Contents

1. [Core Models](#core-models)
2. [Diagrams](#diagrams)
   - [Sequence Diagram - Quote Creation Flow](#sequence-diagram---quote-creation-flow)
   - [Activity Diagram - Price Calculation](#activity-diagram---price-calculation)
   - [State Diagram - Quote Lifecycle](#state-diagram---quote-lifecycle)
   - [Entity Relationship Diagram](#entity-relationship-diagram)
   - [Data Flow Diagram - Price Calculation](#data-flow-diagram---price-calculation)
   - [Tier Insertion Sequence Diagram](#tier-insertion-sequence-diagram)
   - [Batch Cost Calculation Diagram](#batch-cost-calculation-diagram)
   - [Discount Prompt Application Sequence Diagram](#discount-prompt-application-sequence-diagram)
   - [Discount Prompt Matching Activity Diagram](#discount-prompt-matching-activity-diagram)
   - [Discount Prompt Priority Resolution Diagram](#discount-prompt-priority-resolution-diagram)
   - [AI Discount Calculation Flow](#ai-discount-calculation-flow)
3. [Pricing Calculation Flow](#pricing-calculation-flow)
4. [Relationships Diagram](#relationships-diagram)
5. [Business Logic Patterns](#business-logic-patterns)
6. [Database Indexing Strategy](#database-indexing-strategy)

---

## Core Models

### 1. SegmentContact Model

**File**: [ai_rfq_engine/models/segment_contact.py](../ai_rfq_engine/models/segment_contact.py)

**Purpose**: Links contacts to pricing segments

```python
class SegmentContactModel(BaseModel):
    table_name = "are-segment_contacts"

    endpoint_id = UnicodeAttribute(hash_key=True)
    email = UnicodeAttribute(range_key=True)
    segment_uuid = UnicodeAttribute()
    contact_uuid = UnicodeAttribute(null=True)
    consumer_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
```

**Role in Pricing**:
- Acts as a **junction/link** between contacts (via email) and pricing segments
- Associates a contact's email address with a specific segment
- Each segment has different pricing rules, tiers, and discount policies
- When pricing is needed, the system identifies which segment a contact belongs to, then applies that segment's pricing configuration
- Does NOT directly store pricing data, but is essential for routing pricing lookups to the correct segment

**Indexes**:
- `segment_uuid_index`: Query contacts by segment (enables segment-based pricing lookups)
- `consumer_corp_external_id_index`: Link to consumer corporations
- `updated_at_index`: Track modifications

---

### 2. Item Model

**File**: [ai_rfq_engine/models/item.py](../ai_rfq_engine/models/item.py)

**Purpose**: Base entity for all pricing operations

```python
class ItemModel(BaseModel):
    table_name = "are-items"

    endpoint_id = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)
    item_type = UnicodeAttribute()
    item_name = UnicodeAttribute()
    item_description = UnicodeAttribute(null=True)
    uom = UnicodeAttribute()  # Unit of Measure (e.g., "pieces", "kg")
    item_external_id = UnicodeAttribute(null=True)
```

**Role in Pricing**:
- The **base entity** for all pricing operations
- Defines the Unit of Measure (UOM) which is essential for per-unit pricing calculations
- Acts as the **parent key** in pricing tier configurations
- Each item can have multiple pricing tiers and discount rules depending on segment and provider
- No direct pricing fields, but all pricing data is indexed by `item_uuid`
- Deletion is prevented if provider items exist (maintains referential integrity)

**Pricing-Related Features**:
- Deletion protection via `delete_item()`: Prevents removal if provider items are attached
- Used as the primary indexing key for ItemPriceTierModel

---

### 3. ProviderItem Model

**File**: [ai_rfq_engine/models/provider_item.py](../ai_rfq_engine/models/provider_item.py)

**Purpose**: Bridges Items to Providers with base pricing

```python
class ProviderItemModel(BaseModel):
    table_name = "are-provider_items"

    endpoint_id = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)
    item_uuid = UnicodeAttribute()                          # Foreign key to Item
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
    provider_item_external_id = UnicodeAttribute(null=True)
    base_price_per_uom = NumberAttribute()                 # KEY PRICING FIELD
    item_spec = MapAttribute(null=True)                    # Additional specs
```

**Core Pricing Responsibility**:
- **Bridges Items to Providers**: Maps each item to a specific provider's offering
- **Base Price**: `base_price_per_uom` is the foundational price per unit
- Acts as the default guardrail price when no batches are available
- Used as the parent key for item price tiers (per-provider pricing variations)

**Key Relationships**:
```
Provider_Item:
├── item_uuid ──→ Item (defines UOM)
├── provider_corp_external_id ──→ Segment
└── base_price_per_uom ──→ Guardrail price
    └── Referenced by ItemPriceTier
    └── Referenced by ProviderItemBatch
```

**Indexes**:
- `item_uuid_index`: Find all providers for an item
- `provider_corp_external_id_index`: Find all items from a provider
- `provider_item_external_id_index`: External ID lookup
- `updated_at_index`: Modification tracking

**Deletion Constraints**:
Prevents deletion if any of these exist:
- ItemPriceTiers
- QuoteItems
- ProviderItemBatches

---

### 4. ProviderItemBatch Model

**File**: [ai_rfq_engine/models/provider_item_batches.py](../ai_rfq_engine/models/provider_item_batches.py)

**Purpose**: Track batch-level costs and dynamic pricing

```python
class ProviderItemBatchModel(BaseModel):
    table_name = "are-provider_item_batches"

    provider_item_uuid = UnicodeAttribute(hash_key=True)
    batch_no = UnicodeAttribute(range_key=True)
    item_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    expired_at = UTCDateTimeAttribute()
    produced_at = UTCDateTimeAttribute()

    # Cost Components
    cost_per_uom = NumberAttribute()
    freight_cost_per_uom = NumberAttribute()
    additional_cost_per_uom = NumberAttribute()
    total_cost_per_uom = NumberAttribute()  # Auto-calculated

    # Guardrail/Safety Pricing
    guardrail_margin_per_uom = NumberAttribute(default=0)
    guardrail_price_per_uom = NumberAttribute()  # Auto-calculated

    # Inventory Status
    slow_move_item = BooleanAttribute(default=False)
    in_stock = BooleanAttribute(default=True)
```

**Batch Pricing Calculations**:

When a new batch is created or updated, the system performs automatic calculations:

```python
# On Insert:
cols["total_cost_per_uom"] = (
    cols.get("cost_per_uom", 0)
    + cols.get("freight_cost_per_uom", 0)
    + cols.get("additional_cost_per_uom", 0)
)

cols["guardrail_price_per_uom"] = cols["total_cost_per_uom"] * (
    1 + cols.get("guardrail_margin_per_uom", 0) / 100
)
```

**Cost Structure**:
1. **Base Costs**: `cost_per_uom`
2. **Freight**: `freight_cost_per_uom`
3. **Additional**: `additional_cost_per_uom`
4. **Total Cost**: Sum of the above three (auto-calculated)
5. **Guardrail Margin**: Safety markup percentage
6. **Guardrail Price**: Cost with margin applied (used as fallback price)

**Batch Status Tracking**:
- `slow_move_item`: Flag for slow-moving inventory (potential dynamic pricing)
- `in_stock`: Availability indicator
- `expired_at` / `produced_at`: Temporal tracking for freshness

**Role in Pricing**:
- Provides **detailed cost breakdown** at the batch level
- Used by ItemPriceTier to calculate `price_per_uom` when `margin_per_uom` is set
- Enables **dynamic pricing** based on batch-specific cost variations
- Guardrail prices serve as **safety floors** for pricing

---

### 5. ItemPriceTier Model

**File**: [ai_rfq_engine/models/item_price_tier.py](../ai_rfq_engine/models/item_price_tier.py)

**Purpose**: Implements quantity-based tiered pricing

```python
class ItemPriceTierModel(BaseModel):
    table_name = "are-item_price_tiers"

    item_uuid = UnicodeAttribute(hash_key=True)
    item_price_tier_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()                # Which provider
    segment_uuid = UnicodeAttribute()                      # Which segment
    endpoint_id = UnicodeAttribute()

    # Tier Range Definition
    quantity_greater_then = NumberAttribute()              # Lower bound (inclusive)
    quantity_less_then = NumberAttribute(null=True)        # Upper bound (exclusive)

    # Pricing Options (Tier can use either approach)
    margin_per_uom = NumberAttribute(null=True)            # Margin to apply to batch costs
    price_per_uom = NumberAttribute(null=True)             # Direct fixed price

    status = UnicodeAttribute(default="in_review")
```

**Tiered Pricing Logic**:

Tiers are **quantity-based ranges**. A tier matches when:
```
quantity_greater_then <= requested_quantity < quantity_less_then
```

**Tier Structure Example**:
```
Tier 1: quantity >= 0,    quantity < 100   → price_per_uom = $10
Tier 2: quantity >= 100,  quantity < 500   → price_per_uom = $9
Tier 3: quantity >= 500,  quantity < NULL  → price_per_uom = $8 (no upper limit)
```

**Tier Insertion Logic**:

When inserting a new tier:
1. Fetch the current "last tier" (where `quantity_less_then = NULL`)
2. Validate that new tier's `quantity_greater_then` > previous tier's `quantity_greater_then`
3. Save the new tier with `quantity_less_then = NULL`
4. Update the previous tier to set its `quantity_less_then = new_tier.quantity_greater_then`

This maintains a **cascading tier structure**.

**Price Determination Methods**:

**Method 1: Direct Price**
```python
IF tier.price_per_uom IS NOT NULL:
    price = tier.price_per_uom
```

**Method 2: Margin-Based Price (from Batches)**
```python
IF tier.margin_per_uom IS NOT NULL:
    FOR each batch in tier.provider_item_batches:
        batch_price = batch.total_cost_per_uom * (1 + margin_per_uom / 100)
    RETURN calculated price from matching batch
```

**GraphQL Type Resolution**:

See [ai_rfq_engine/graphql/item_price_tier/types.py:61-82](../ai_rfq_engine/graphql/item_price_tier/types.py#L61-L82)

```python
def resolve_provider_item_batches(parent, info):
    margin_per_uom = getattr(parent, "margin_per_uom", None)
    if not margin_per_uom:
        return []

    def build_batches(batches):
        result = []
        margin = float(margin_per_uom) / 100
        for batch in batches:
            batch_dict = dict(batch)
            total_cost = float(batch_dict.get("total_cost_per_uom", 0))
            price_per_uom = total_cost * (1 + margin)  # Apply margin
            batch_dict["price_per_uom"] = str(price_per_uom)
            result.append(batch_dict)
        return result

    return loaders.provider_item_batch_list_loader.load(
        provider_item_uuid
    ).then(build_batches)
```

**Indexes**:
- `provider_item_uuid_index`: Find tiers by provider item (enables provider-specific pricing)
- `segment_uuid_index`: Find tiers by segment (segment-specific pricing)
- `updated_at_index`: Modification tracking

**Segment-Based Pricing**:
Each `segment_uuid` can have different pricing for the same item from the same provider, enabling customer-segment-specific pricing.

---

### 6. DiscountPrompt Model

**File**: [ai_rfq_engine/models/discount_prompt.py](../ai_rfq_engine/models/discount_prompt.py)

**Purpose**: AI-driven discount prompts with flexible scoping and tiered discount rules

```python
class DiscountPromptModel(BaseModel):
    table_name = "are-discount_prompts"

    endpoint_id = UnicodeAttribute(hash_key=True)
    discount_prompt_uuid = UnicodeAttribute(range_key=True)
    scope = UnicodeAttribute()                             # global, segment, or item
    tags = ListAttribute()                                 # Flexible tagging system
    discount_prompt = UnicodeAttribute()                   # AI prompt for discount logic
    conditions = ListAttribute()                           # Conditional logic
    discount_rules = ListAttribute(of=MapAttribute)        # Tiered discount rules
    priority = NumberAttribute(default=0)                  # Priority for conflict resolution
    status = UnicodeAttribute(default="in_review")         # in_review, active, inactive
```

**Scope Types**:
- **GLOBAL**: Applies to all items and segments
- **SEGMENT**: Applies to specific segment(s) via tags
- **ITEM**: Applies to specific item(s) via tags

**Discount Logic**:

Discount rules are stored as a list of tier objects with automatic validation:
```python
discount_rules = [
    {"greater_than": 0, "less_than": 1000, "max_discount_percentage": 5},
    {"greater_than": 1000, "less_than": 5000, "max_discount_percentage": 10},
    {"greater_than": 5000, "max_discount_percentage": 15}  # No less_than = open-ended
]
```

**Validation Rules**:
1. Rules are automatically sorted by `greater_than` (low to high)
2. First tier must start at 0
3. Each tier's `less_than` must equal next tier's `greater_than` (no gaps/overlaps)
4. Last tier has no `less_than` (open-ended upper bound)
5. `max_discount_percentage` must INCREASE as tiers increase (higher purchases = better discounts)
6. All percentages must be between 0 and 100

A rule matches when:
```
greater_than <= requested_subtotal < less_than
```

**Priority System**:
When multiple prompts match (e.g., GLOBAL + SEGMENT + ITEM), the highest priority wins. Higher priority numbers take precedence.

---

### 7. QuoteItem Model

**File**: [ai_rfq_engine/models/quote_item.py](../ai_rfq_engine/models/quote_item.py)

**Purpose**: Store line items with calculated pricing

```python
class QuoteItemModel(BaseModel):
    table_name = "are-quote_items"

    quote_uuid = UnicodeAttribute(hash_key=True)
    quote_item_uuid = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    item_uuid = UnicodeAttribute()
    batch_no = UnicodeAttribute(null=True)
    request_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    request_data = MapAttribute(null=True)

    # Pricing Fields (calculated at creation)
    price_per_uom = NumberAttribute()          # From tier lookup
    qty = NumberAttribute()
    subtotal = NumberAttribute()               # price_per_uom * qty
    subtotal_discount = NumberAttribute(null=True)  # Applied discount amount
    final_subtotal = NumberAttribute()         # subtotal - discount
```

**Quote Item Creation Logic**:

See [ai_rfq_engine/models/quote_item.py:247-312](../ai_rfq_engine/models/quote_item.py#L247-L312)

When creating a quote item:

```python
def insert_update_quote_item(info: ResolveInfo, **kwargs):
    if kwargs.get("entity") is None:  # New item
        # Validate required fields
        item_uuid = kwargs.get("item_uuid")
        qty = kwargs.get("qty")
        segment_uuid = kwargs.get("segment_uuid")
        provider_item_uuid = kwargs.get("provider_item_uuid")
        batch_no = kwargs.get("batch_no")

        # Get price from tiers
        price_per_uom = get_price_per_uom(
            info, item_uuid, qty, segment_uuid,
            provider_item_uuid, batch_no
        )

        if price_per_uom is None:
            raise ValueError("No price tier found")

        # Auto-calculate totals
        cols["subtotal"] = float(price_per_uom) * float(qty)
        subtotal_discount = cols.get("subtotal_discount", 0)
        cols["final_subtotal"] = cols["subtotal"] - subtotal_discount

        QuoteItemModel(...).save()

        # Update parent quote totals
        update_quote_totals(info, request_uuid, quote_uuid)
```

**Indexes**:
- `provider_item_uuid_index`: Quote items by provider
- `item_uuid_index`: Quote items by item
- `item_uuid_provider_item_uuid_index`: Global secondary index for combined queries
- `updated_at_index`: Temporal queries

---

### 8. Quote Model

**File**: [ai_rfq_engine/models/quote.py](../ai_rfq_engine/models/quote.py)

**Purpose**: Aggregate totals from quote items

```python
class QuoteModel(BaseModel):
    table_name = "are-quotes"

    request_uuid = UnicodeAttribute(hash_key=True)
    quote_uuid = UnicodeAttribute(range_key=True)
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")

    # Pricing Totals (aggregated from quote items)
    shipping_amount = NumberAttribute(default=0)
    total_quote_amount = NumberAttribute(default=0)           # Sum of subtotals
    total_quote_discount = NumberAttribute(default=0)         # Sum of discounts
    final_total_quote_amount = NumberAttribute(default=0)    # Items + shipping

    rounds = NumberAttribute(default=0)
    status = UnicodeAttribute(default="initial")
```

**Quote Totals Calculation**:

See [ai_rfq_engine/models/quote.py:182-220](../ai_rfq_engine/models/quote.py#L182-L220)

```python
def update_quote_totals(info: ResolveInfo, request_uuid: str, quote_uuid: str):
    quote = get_quote(request_uuid, quote_uuid)
    quote_item_list = resolve_quote_item_list(info, quote_uuid=quote_uuid)

    # Aggregate from all quote items
    total_quote_amount = sum(
        item.subtotal
        for item in quote_item_list.quote_item_list
    )

    total_quote_discount = sum(
        item.subtotal_discount if item.subtotal_discount else 0
        for item in quote_item_list.quote_item_list
    )

    items_final_total = sum(
        item.final_subtotal
        for item in quote_item_list.quote_item_list
    )

    # Add shipping
    shipping_amount = quote.shipping_amount or 0
    final_total_quote_amount = items_final_total + shipping_amount

    # Update quote
    quote.update(actions=[
        QuoteModel.total_quote_amount.set(float(total_quote_amount)),
        QuoteModel.total_quote_discount.set(float(total_quote_discount)),
        QuoteModel.final_total_quote_amount.set(float(final_total_quote_amount)),
        QuoteModel.updated_at.set(pendulum.now("UTC")),
    ])
```

**Quote Calculation Flow**:
```
Quote Total = SUM(QuoteItem.subtotal) + shipping_amount
Quote Discount = SUM(QuoteItem.subtotal_discount)
Final Total = SUM(QuoteItem.final_subtotal) + shipping_amount
```

---

## Diagrams

### Sequence Diagram - Quote Creation Flow

This diagram shows the complete interaction flow when creating a quote with pricing calculation.

```mermaid
sequenceDiagram
    participant User
    participant GraphQL as GraphQL API
    participant QuoteItem as QuoteItemModel
    participant PriceLookup as get_price_per_uom()
    participant ItemPriceTier as ItemPriceTierModel
    participant Batch as ProviderItemBatchModel
    participant Quote as QuoteModel
    participant SegmentContact as SegmentContactModel

    User->>GraphQL: Create Quote Request
    GraphQL->>SegmentContact: Get segment_uuid by email
    SegmentContact-->>GraphQL: Return segment_uuid

    loop For Each Quote Item
        User->>GraphQL: Add Item (item_uuid, qty, provider_item_uuid)
        GraphQL->>QuoteItem: insert_update_quote_item()

        QuoteItem->>PriceLookup: get_price_per_uom(item_uuid, qty, segment_uuid, provider_item_uuid, batch_no?)

        PriceLookup->>ItemPriceTier: Query tiers WHERE<br/>item_uuid, segment_uuid, provider_item_uuid<br/>quantity_greater_then <= qty < quantity_less_then<br/>status = "active"

        alt Tier Found
            ItemPriceTier-->>PriceLookup: Return matching tier

            alt Tier has price_per_uom
                PriceLookup-->>QuoteItem: Return tier.price_per_uom
            else Tier has margin_per_uom
                PriceLookup->>Batch: Load batches for provider_item_uuid
                Batch-->>PriceLookup: Return batches with costs
                PriceLookup->>PriceLookup: Calculate:<br/>price = total_cost_per_uom * (1 + margin/100)

                alt Specific batch_no requested
                    PriceLookup->>PriceLookup: Find matching batch
                    PriceLookup-->>QuoteItem: Return batch.price_per_uom
                else No batch_no specified
                    PriceLookup-->>QuoteItem: Return first_batch.price_per_uom
                end
            end
        else No Tier Found
            PriceLookup-->>QuoteItem: Return None (Error)
            QuoteItem-->>GraphQL: Throw "No price tier found"
            GraphQL-->>User: Error Response
        end

        QuoteItem->>QuoteItem: Calculate:<br/>subtotal = price_per_uom * qty<br/>final_subtotal = subtotal - discount
        QuoteItem->>QuoteItem: Save quote item

        QuoteItem->>Quote: update_quote_totals(request_uuid, quote_uuid)
        Quote->>Quote: Aggregate:<br/>total_quote_amount = SUM(subtotals)<br/>total_quote_discount = SUM(discounts)<br/>final_total = SUM(final_subtotals) + shipping
        Quote->>Quote: Update quote record

        Quote-->>GraphQL: Quote item created
        GraphQL-->>User: Success Response
    end

    User->>GraphQL: Get Quote
    GraphQL->>Quote: Fetch quote with items
    Quote-->>GraphQL: Return quote data
    GraphQL-->>User: Complete Quote with Pricing
```

---

### Activity Diagram - Price Calculation

This diagram illustrates the decision-making process for calculating the price per UOM.

```mermaid
flowchart TD
    Start([Start: Price Calculation Request]) --> Input[/Input:<br/>item_uuid, qty, segment_uuid,<br/>provider_item_uuid, batch_no?/]

    Input --> QueryTier[Query ItemPriceTierModel<br/>WHERE item_uuid, segment_uuid,<br/>provider_item_uuid, status='active'<br/>AND quantity_greater_then <= qty<br/>AND qty < quantity_less_then]

    QueryTier --> TierFound{Tier<br/>Found?}

    TierFound -->|No| NoTier[Return None]
    NoTier --> ErrorEnd([End: Pricing Error])

    TierFound -->|Yes| GetTier[tier = first matching tier]

    GetTier --> HasDirectPrice{tier has<br/>price_per_uom?}

    HasDirectPrice -->|Yes| ReturnDirectPrice[Return tier.price_per_uom]
    ReturnDirectPrice --> SuccessEnd([End: Price Found])

    HasDirectPrice -->|No| HasMargin{tier has<br/>margin_per_uom?}

    HasMargin -->|No| NoPrice[Return None]
    NoPrice --> ErrorEnd

    HasMargin -->|Yes| LoadBatches[Load ProviderItemBatches<br/>for provider_item_uuid]

    LoadBatches --> HasBatches{Batches<br/>Exist?}

    HasBatches -->|No| NoBatch[Return None]
    NoBatch --> ErrorEnd

    HasBatches -->|Yes| BatchNoSpecified{batch_no<br/>specified?}

    BatchNoSpecified -->|Yes| FindBatch[Find batch WHERE<br/>batch_no matches]
    FindBatch --> BatchMatch{Batch<br/>Found?}

    BatchMatch -->|Yes| CalcBatchPrice[Calculate:<br/>price = batch.total_cost_per_uom<br/>* 1 + margin/100]
    CalcBatchPrice --> ReturnBatchPrice[Return calculated price]
    ReturnBatchPrice --> SuccessEnd

    BatchMatch -->|No| NoBatch

    BatchNoSpecified -->|No| UseFirstBatch[Use first available batch]
    UseFirstBatch --> CalcFirstPrice[Calculate:<br/>price = first_batch.total_cost_per_uom<br/>* 1 + margin/100]
    CalcFirstPrice --> ReturnFirstPrice[Return calculated price]
    ReturnFirstPrice --> SuccessEnd

    style Start fill:#e1f5dd
    style SuccessEnd fill:#e1f5dd
    style ErrorEnd fill:#ffebee
    style HasDirectPrice fill:#fff3e0
    style HasMargin fill:#fff3e0
    style TierFound fill:#fff3e0
    style HasBatches fill:#fff3e0
    style BatchNoSpecified fill:#fff3e0
    style BatchMatch fill:#fff3e0
```

---

### State Diagram - Quote Lifecycle

This diagram shows the different states of quotes and price tiers throughout their lifecycle.

```mermaid
stateDiagram-v2
    [*] --> Initial: Create Quote

    state "Quote Status States" as QuoteStates {
        Initial --> InProgress: Add Items
        InProgress --> InProgress: Modify Items/Discounts
        InProgress --> Submitted: Submit to Provider
        Submitted --> Accepted: Provider Accepts
        Submitted --> Rejected: Provider Rejects
        Submitted --> Negotiating: Counter Offer
        Negotiating --> Submitted: Re-submit
        Negotiating --> Cancelled: Cancel Quote
        Accepted --> Fulfilled: Complete Order
        Rejected --> Cancelled: Close Quote
        InProgress --> Cancelled: Cancel Quote

        state InProgress {
            [*] --> CalculatingPrice: Price Lookup
            CalculatingPrice --> ApplyingDiscount: Price Found
            ApplyingDiscount --> UpdatingTotals: Discount Applied
            UpdatingTotals --> [*]: Totals Updated
        }
    }

    state "ItemPriceTier Status States" as TierStates {
        state InReview {
            [*] --> PendingApproval: Tier Created
            PendingApproval --> UnderReview: Review Started
        }
        InReview --> Active: Approve Tier
        InReview --> Rejected_Tier: Reject Tier
        Active --> Inactive: Deactivate
        Inactive --> Active: Reactivate
        Active --> Superseded: New Tier Inserted
        Rejected_Tier --> [*]
        Superseded --> [*]
    }

    state "ProviderItemBatch Status States" as BatchStates {
        [*] --> Available: Batch Created
        Available --> Reserved: Quote Created
        Reserved --> Available: Quote Cancelled
        Reserved --> Allocated: Quote Accepted
        Allocated --> Fulfilled_Batch: Order Completed
        Available --> Expired: Expiration Date Reached
        Expired --> [*]
        Fulfilled_Batch --> [*]

        state Available {
            [*] --> InStock: in_stock = true
            InStock --> OutOfStock: in_stock = false
            OutOfStock --> InStock: Restocked
            InStock --> SlowMoving: slow_move_item = true
            SlowMoving --> InStock: slow_move_item = false
        }
    }

    Fulfilled --> [*]
    Cancelled --> [*]
```

---

### Entity Relationship Diagram

This diagram shows the relationships between all pricing-related entities.

```mermaid
erDiagram
    SEGMENT_CONTACT ||--o{ SEGMENT : "belongs to"
    SEGMENT_CONTACT {
        string endpoint_id PK
        string email PK
        string segment_uuid FK
        string contact_uuid
        string consumer_corp_external_id
    }

    SEGMENT {
        string segment_uuid PK
        string segment_name
        string provider_corp_external_id FK
    }

    ITEM ||--o{ PROVIDER_ITEM : "offered by providers"
    ITEM {
        string endpoint_id PK
        string item_uuid PK
        string item_type
        string item_name
        string uom
        string item_external_id
    }

    PROVIDER_ITEM ||--o{ ITEM_PRICE_TIER : "has pricing tiers"
    PROVIDER_ITEM ||--o{ PROVIDER_ITEM_BATCH : "has batches"
    PROVIDER_ITEM ||--o{ QUOTE_ITEM : "quoted in"
    PROVIDER_ITEM {
        string endpoint_id PK
        string provider_item_uuid PK
        string item_uuid FK
        string provider_corp_external_id FK
        number base_price_per_uom
        string provider_item_external_id
    }

    ITEM_PRICE_TIER }o--|| SEGMENT : "applies to"
    ITEM_PRICE_TIER ||--o{ PROVIDER_ITEM_BATCH : "references for margin pricing"
    ITEM_PRICE_TIER {
        string item_uuid PK,FK
        string item_price_tier_uuid PK
        string provider_item_uuid FK
        string segment_uuid FK
        number quantity_greater_then
        number quantity_less_then
        number price_per_uom
        number margin_per_uom
        string status
    }

    PROVIDER_ITEM_BATCH {
        string provider_item_uuid PK,FK
        string batch_no PK
        string item_uuid FK
        number cost_per_uom
        number freight_cost_per_uom
        number additional_cost_per_uom
        number total_cost_per_uom
        number guardrail_margin_per_uom
        number guardrail_price_per_uom
        boolean slow_move_item
        boolean in_stock
        datetime expired_at
        datetime produced_at
    }

    DISCOUNT_PROMPT {
        string endpoint_id PK
        string discount_prompt_uuid PK
        string scope
        list tags
        string discount_prompt
        list conditions
        list discount_rules
        number priority
        string status
    }

    QUOTE ||--|{ QUOTE_ITEM : "contains"
    QUOTE {
        string request_uuid PK,FK
        string quote_uuid PK
        string provider_corp_external_id FK
        number shipping_amount
        number total_quote_amount
        number total_quote_discount
        number final_total_quote_amount
        number rounds
        string status
    }

    QUOTE_ITEM }o--|| PROVIDER_ITEM : "references"
    QUOTE_ITEM }o--o| PROVIDER_ITEM_BATCH : "optionally references"
    QUOTE_ITEM {
        string quote_uuid PK,FK
        string quote_item_uuid PK
        string provider_item_uuid FK
        string item_uuid FK
        string batch_no FK
        string request_uuid FK
        number price_per_uom
        number qty
        number subtotal
        number subtotal_discount
        number final_subtotal
    }

    REQUEST ||--|{ QUOTE : "has"
    REQUEST {
        string request_uuid PK
        string consumer_corp_external_id
        string status
    }
```

---

### Data Flow Diagram - Price Calculation

This diagram shows how data flows through the pricing calculation system.

```mermaid
flowchart LR
    subgraph Input["Input Data"]
        User[User/Contact<br/>email]
        ItemReq[Item Request<br/>item_uuid, qty]
        ProviderReq[Provider<br/>provider_item_uuid]
        BatchReq[Optional Batch<br/>batch_no]
    end

    subgraph Lookup["Lookup Layer"]
        User --> SegContact[SegmentContact<br/>Lookup]
        SegContact --> Segment[segment_uuid]

        ItemReq --> TierQuery[ItemPriceTier<br/>Query]
        ProviderReq --> TierQuery
        Segment --> TierQuery

        TierQuery --> TierResult{Tier Type?}
    end

    subgraph Calculation["Calculation Layer"]
        TierResult -->|Fixed Price| FixedPrice[Use tier.price_per_uom]
        TierResult -->|Margin Based| MarginCalc[Load Batches]

        BatchReq --> MarginCalc
        MarginCalc --> BatchFilter{Batch<br/>Filtering}

        BatchFilter -->|Specific| SpecBatch[Find batch_no]
        BatchFilter -->|Default| FirstBatch[Use first batch]

        SpecBatch --> CalcMargin[Calculate:<br/>total_cost * 1+margin/100]
        FirstBatch --> CalcMargin
    end

    subgraph Output["Output Layer"]
        FixedPrice --> PriceResult[price_per_uom]
        CalcMargin --> PriceResult

        PriceResult --> QuoteCalc[Quote Item Calculation]
        QuoteCalc --> Subtotal[subtotal =<br/>price_per_uom * qty]

        Subtotal --> DiscountLookup[Discount Prompt<br/>Lookup Optional]
        DiscountLookup --> FinalSubtotal[final_subtotal =<br/>subtotal - discount]

        FinalSubtotal --> QuoteAgg[Quote Aggregation]
        QuoteAgg --> QuoteTotals[Quote Totals:<br/>total_quote_amount<br/>total_quote_discount<br/>final_total_quote_amount]
    end

    style Input fill:#e3f2fd
    style Lookup fill:#fff3e0
    style Calculation fill:#f3e5f5
    style Output fill:#e8f5e9
```

---

### Tier Insertion Sequence Diagram

This diagram shows how the cascading tier structure is maintained when inserting new tiers.

```mermaid
sequenceDiagram
    participant User
    participant API as GraphQL API
    participant Insert as insert_update_item_price_tier()
    participant GetPrev as _get_previous_tier()
    participant UpdatePrev as _update_previous_tier()
    participant DB as Database

    User->>API: Create New Tier<br/>(qty >= 250, price=$8.50)
    API->>Insert: insert_update_item_price_tier(quantity_greater_then=250)

    Insert->>GetPrev: _get_previous_tier(item_uuid, provider_item_uuid, segment_uuid)
    GetPrev->>DB: Query WHERE quantity_less_then IS NULL
    DB-->>GetPrev: Return current last tier<br/>(qty >= 100, qty < NULL, price=$9)
    GetPrev-->>Insert: previous_tier

    Insert->>Insert: Validate:<br/>new qty (250) > previous qty (100) ✓

    Insert->>DB: Save new tier:<br/>qty >= 250, qty < NULL, price=$8.50
    DB-->>Insert: New tier saved

    Insert->>UpdatePrev: _update_previous_tier(previous_tier, new_quantity=250)
    UpdatePrev->>DB: Update previous tier:<br/>SET quantity_less_then = 250<br/>WHERE tier = previous_tier
    DB-->>UpdatePrev: Previous tier updated<br/>(qty >= 100, qty < 250, price=$9)
    UpdatePrev-->>Insert: Update complete

    Insert-->>API: Tier insertion successful
    API-->>User: Success Response

    Note over DB: Final Tier Structure:<br/>Tier 1: qty >= 0, qty < 100 → $10<br/>Tier 2: qty >= 100, qty < 250 → $9<br/>Tier 3: qty >= 250, qty < NULL → $8.50
```

---

### Batch Cost Calculation Diagram

This diagram shows the automatic calculation of batch costs and guardrail pricing.

```mermaid
flowchart TD
    Start([Batch Insert/Update]) --> Input[/Input:<br/>cost_per_uom<br/>freight_cost_per_uom<br/>additional_cost_per_uom<br/>guardrail_margin_per_uom/]

    Input --> CalcTotal[Calculate Total Cost:<br/>total_cost_per_uom =<br/>cost_per_uom +<br/>freight_cost_per_uom +<br/>additional_cost_per_uom]

    CalcTotal --> CalcGuardrail[Calculate Guardrail Price:<br/>guardrail_price_per_uom =<br/>total_cost_per_uom *<br/>1 + guardrail_margin_per_uom/100]

    CalcGuardrail --> SaveBatch[Save Batch with<br/>Calculated Values]

    SaveBatch --> UsedBy{How is this<br/>batch used?}

    UsedBy -->|Direct Selection| QuoteItem[QuoteItem references<br/>specific batch_no]
    UsedBy -->|Margin Pricing| TierMargin[ItemPriceTier with margin_per_uom<br/>uses batch costs]
    UsedBy -->|Guardrail| Fallback[Guardrail price used<br/>as safety floor]

    QuoteItem --> End([End])
    TierMargin --> PriceCalc[Price Calculation:<br/>price_per_uom =<br/>total_cost_per_uom *<br/>1 + tier.margin_per_uom/100]
    PriceCalc --> End
    Fallback --> End

    style Start fill:#e1f5dd
    style End fill:#e1f5dd
    style CalcTotal fill:#bbdefb
    style CalcGuardrail fill:#bbdefb
    style UsedBy fill:#fff3e0
```

---

### Discount Prompt Application Sequence Diagram

This diagram shows how discount prompts are retrieved and applied to quote items.

```mermaid
sequenceDiagram
    participant User
    participant GraphQL as GraphQL API
    participant QuoteItem as QuoteItemModel
    participant DiscountPrompt as DiscountPromptModel
    participant AI as AI Discount Engine
    participant Quote as QuoteModel

    User->>GraphQL: Request to apply discount<br/>(quote_item_uuid, context)
    GraphQL->>QuoteItem: Get quote item details
    QuoteItem-->>GraphQL: Return item_uuid, segment_uuid,<br/>subtotal, provider_item_uuid

    GraphQL->>DiscountPrompt: Query matching prompts<br/>WHERE status = "active"

    par Fetch Global Prompts
        DiscountPrompt->>DiscountPrompt: Query WHERE scope = "global"
        DiscountPrompt-->>GraphQL: Return global prompts
    and Fetch Segment Prompts
        DiscountPrompt->>DiscountPrompt: Query WHERE scope = "segment"<br/>AND tags CONTAINS segment_uuid
        DiscountPrompt-->>GraphQL: Return segment prompts
    and Fetch Item Prompts
        DiscountPrompt->>DiscountPrompt: Query WHERE scope = "item"<br/>AND tags CONTAINS item_uuid
        DiscountPrompt-->>GraphQL: Return item prompts
    end

    GraphQL->>GraphQL: Merge all matching prompts

    alt No Prompts Found
        GraphQL-->>User: No discount available
    else Prompts Found
        GraphQL->>GraphQL: Sort by priority (DESC)
        GraphQL->>GraphQL: Select highest priority prompt

        Note over GraphQL: Evaluate conditions if present

        alt Conditions Exist
            GraphQL->>AI: Evaluate conditions<br/>(prompt.conditions, context)
            AI->>AI: Check condition logic
            AI-->>GraphQL: Return evaluation result

            alt Conditions Failed
                GraphQL->>GraphQL: Try next prompt by priority
            end
        end

        GraphQL->>GraphQL: Find matching tier in discount_rules<br/>WHERE greater_than <= subtotal < less_than

        alt Matching Tier Found
            GraphQL->>GraphQL: Extract max_discount_percentage

            alt AI Prompt Present
                GraphQL->>AI: Calculate dynamic discount<br/>(prompt.discount_prompt, context, max_discount_percentage)
                AI->>AI: Evaluate AI logic<br/>Consider: order history, customer tier,<br/>seasonal factors, inventory levels
                AI-->>GraphQL: Return calculated_discount_percentage<br/>(≤ max_discount_percentage)
            else No AI Prompt
                GraphQL->>GraphQL: Use max_discount_percentage directly
            end

            GraphQL->>GraphQL: Calculate discount_amount:<br/>subtotal * (calculated_discount_percentage / 100)

            GraphQL->>QuoteItem: Update quote item<br/>SET subtotal_discount = discount_amount
            QuoteItem->>QuoteItem: Recalculate:<br/>final_subtotal = subtotal - discount_amount

            QuoteItem->>Quote: update_quote_totals(request_uuid, quote_uuid)
            Quote->>Quote: Aggregate totals

            GraphQL-->>User: Discount applied successfully<br/>(discount_percentage, discount_amount)

        else No Matching Tier
            GraphQL-->>User: Subtotal outside discount tiers
        end
    end
```

---

### Discount Prompt Matching Activity Diagram

This diagram illustrates the decision-making process for matching and applying discount prompts.

```mermaid
flowchart TD
    Start([Start: Apply Discount Request]) --> InputData[/Input:<br/>quote_item_uuid, item_uuid,<br/>segment_uuid, subtotal, context/]

    InputData --> QueryPrompts[Query DiscountPromptModel<br/>WHERE status = 'active']

    QueryPrompts --> FetchGlobal[Fetch GLOBAL prompts<br/>scope = 'global']
    QueryPrompts --> FetchSegment[Fetch SEGMENT prompts<br/>scope = 'segment'<br/>AND tags CONTAINS segment_uuid]
    QueryPrompts --> FetchItem[Fetch ITEM prompts<br/>scope = 'item'<br/>AND tags CONTAINS item_uuid]

    FetchGlobal --> MergePrompts[Merge all matching prompts]
    FetchSegment --> MergePrompts
    FetchItem --> MergePrompts

    MergePrompts --> HasPrompts{Prompts<br/>Found?}

    HasPrompts -->|No| NoDiscount[No discount available]
    NoDiscount --> EndNoDiscount([End: No Discount])

    HasPrompts -->|Yes| SortByPriority[Sort prompts by priority DESC]

    SortByPriority --> SelectPrompt[Select highest priority prompt]

    SelectPrompt --> HasConditions{Prompt has<br/>conditions?}

    HasConditions -->|Yes| EvalConditions[Evaluate conditions<br/>using AI engine]
    EvalConditions --> ConditionPass{Conditions<br/>passed?}

    ConditionPass -->|No| MorePrompts{More<br/>prompts?}
    MorePrompts -->|Yes| SelectPrompt
    MorePrompts -->|No| NoDiscount

    ConditionPass -->|Yes| FindTier[Find matching tier in discount_rules]
    HasConditions -->|No| FindTier

    FindTier --> TierMatch[Check: greater_than <= subtotal < less_than]

    TierMatch --> TierFound{Tier<br/>Found?}

    TierFound -->|No| MorePrompts

    TierFound -->|Yes| ExtractMax[Extract max_discount_percentage<br/>from matching tier]

    ExtractMax --> HasAIPrompt{Prompt has<br/>discount_prompt<br/>field?}

    HasAIPrompt -->|Yes| CallAI[Call AI Discount Engine<br/>with prompt, context,<br/>max_discount_percentage]
    CallAI --> AICalc[AI evaluates:<br/>- Customer history<br/>- Order patterns<br/>- Seasonal factors<br/>- Inventory levels<br/>- Custom logic]
    AICalc --> AIResult[AI returns calculated_discount<br/>≤ max_discount_percentage]
    AIResult --> ApplyDiscount[discount_percentage =<br/>calculated_discount]

    HasAIPrompt -->|No| UseMax[discount_percentage =<br/>max_discount_percentage]
    UseMax --> ApplyDiscount

    ApplyDiscount --> CalcAmount[Calculate:<br/>discount_amount = subtotal *<br/>discount_percentage / 100]

    CalcAmount --> UpdateItem[Update QuoteItem:<br/>subtotal_discount = discount_amount<br/>final_subtotal = subtotal - discount_amount]

    UpdateItem --> UpdateQuote[Update Quote Totals:<br/>Aggregate all item discounts]

    UpdateQuote --> Success[Return discount details]
    Success --> EndSuccess([End: Discount Applied])

    style Start fill:#e1f5dd
    style EndSuccess fill:#e1f5dd
    style EndNoDiscount fill:#ffebee
    style HasPrompts fill:#fff3e0
    style HasConditions fill:#fff3e0
    style ConditionPass fill:#fff3e0
    style TierFound fill:#fff3e0
    style HasAIPrompt fill:#fff3e0
    style MorePrompts fill:#fff3e0
    style CallAI fill:#e1bee7
    style AICalc fill:#e1bee7
    style AIResult fill:#e1bee7
```

---

### Discount Prompt Priority Resolution Diagram

This diagram shows how conflicts are resolved when multiple prompts match.

```mermaid
flowchart TD
    Start([Multiple Prompts Match]) --> Collect[Collect all matching prompts:<br/>- GLOBAL prompts<br/>- SEGMENT prompts matching tags<br/>- ITEM prompts matching tags]

    Collect --> Example[Example Scenario:<br/>Prompt A: GLOBAL, priority=10<br/>Prompt B: SEGMENT, priority=20<br/>Prompt C: ITEM, priority=15<br/>Prompt D: ITEM, priority=25]

    Example --> Sort[Sort by priority DESC]

    Sort --> Sorted[Sorted Order:<br/>1. Prompt D priority=25 ITEM<br/>2. Prompt B priority=20 SEGMENT<br/>3. Prompt C priority=15 ITEM<br/>4. Prompt A priority=10 GLOBAL]

    Sorted --> ProcessD[Try Prompt D priority=25]

    ProcessD --> CondD{Conditions<br/>pass?}
    CondD -->|No| ProcessB
    CondD -->|Yes| TierD{Tier<br/>matches?}
    TierD -->|No| ProcessB
    TierD -->|Yes| UseD[Use Prompt D<br/>Apply ITEM-specific discount]
    UseD --> End([End: Discount Applied])

    ProcessB[Try Prompt B priority=20]
    ProcessB --> CondB{Conditions<br/>pass?}
    CondB -->|No| ProcessC
    CondB -->|Yes| TierB{Tier<br/>matches?}
    TierB -->|No| ProcessC
    TierB -->|Yes| UseB[Use Prompt B<br/>Apply SEGMENT-specific discount]
    UseB --> End

    ProcessC[Try Prompt C priority=15]
    ProcessC --> CondC{Conditions<br/>pass?}
    CondC -->|No| ProcessA
    CondC -->|Yes| TierC{Tier<br/>matches?}
    TierC -->|No| ProcessA
    TierC -->|Yes| UseC[Use Prompt C<br/>Apply ITEM-specific discount]
    UseC --> End

    ProcessA[Try Prompt A priority=10]
    ProcessA --> CondA{Conditions<br/>pass?}
    CondA -->|No| NoMatch[No valid discount found]
    CondA -->|Yes| TierA{Tier<br/>matches?}
    TierA -->|No| NoMatch
    TierA -->|Yes| UseA[Use Prompt A<br/>Apply GLOBAL discount]
    UseA --> End

    NoMatch --> EndFail([End: No Discount])

    style Start fill:#fff3e0
    style End fill:#e1f5dd
    style EndFail fill:#ffebee
    style UseD fill:#c8e6c9
    style UseB fill:#c8e6c9
    style UseC fill:#c8e6c9
    style UseA fill:#c8e6c9
```

---

### AI Discount Calculation Flow

This diagram shows how the AI engine calculates dynamic discounts within the max percentage limits.

```mermaid
flowchart LR
    subgraph Input["Input Data"]
        Prompt[Discount Prompt<br/>AI instructions]
        Context[Context Data<br/>customer_history<br/>order_value<br/>time_of_year<br/>inventory_status]
        MaxDiscount[Max Discount %<br/>from tier rules]
    end

    subgraph AIEngine["AI Discount Engine"]
        Parse[Parse AI Prompt<br/>Extract logic & rules]

        Evaluate[Evaluate Factors]

        subgraph Factors["Evaluation Factors"]
            Customer[Customer Tier<br/>Purchase history<br/>Loyalty status]
            Order[Order Characteristics<br/>Subtotal amount<br/>Item mix]
            Market[Market Conditions<br/>Season<br/>Promotions<br/>Competition]
            Inventory[Inventory Status<br/>Slow-moving items<br/>Stock levels<br/>Expiration dates]
        end

        Calculate[Calculate Recommended<br/>Discount Percentage]
        Constrain[Apply Constraint:<br/>MIN 0%,<br/>MAX max_discount_percentage]
    end

    subgraph Output["Output"]
        FinalDiscount[Final Discount %<br/>to apply]
    end

    Prompt --> Parse
    Context --> Parse
    MaxDiscount --> Parse

    Parse --> Evaluate

    Evaluate --> Customer
    Evaluate --> Order
    Evaluate --> Market
    Evaluate --> Inventory

    Customer --> Calculate
    Order --> Calculate
    Market --> Calculate
    Inventory --> Calculate

    Calculate --> Constrain
    Constrain --> FinalDiscount

    style Input fill:#e3f2fd
    style AIEngine fill:#f3e5f5
    style Factors fill:#fff3e0
    style Output fill:#e8f5e9
```

---

## Pricing Calculation Flow

### Price Lookup Service

**File**: [ai_rfq_engine/models/quote_item.py:152-202](../ai_rfq_engine/models/quote_item.py#L152-L202)

**Primary Function**: `get_price_per_uom()`

```python
def get_price_per_uom(
    info: ResolveInfo,
    item_uuid: str,
    qty: float,
    segment_uuid: str,
    provider_item_uuid: str,
    batch_no: str = None,
) -> float | None:
    """
    Get the price per UOM based on item price tiers for the given quantity.
    """
    from .item_price_tier import resolve_item_price_tier_list

    # Query parameters with quantity-based tier matching
    query_params = {
        "item_uuid": item_uuid,
        "segment_uuid": segment_uuid,
        "provider_item_uuid": provider_item_uuid,
        "quantity_value": qty,  # Database-level tier matching
        "status": "active",
    }

    # Retrieve matching price tier
    price_tier_list = resolve_item_price_tier_list(info, **query_params)

    if price_tier_list.total == 0:
        return None

    tier = price_tier_list.item_price_tier_list[0]

    # If tier has direct price, use it
    if tier.price_per_uom is not None:
        return tier.price_per_uom

    # If tier has margin with batches, calculate from batch
    if hasattr(tier, "provider_item_batches") and tier.provider_item_batches:
        if batch_no:
            for batch in tier.provider_item_batches:
                if batch["batch_no"] == batch_no:
                    return batch["price_per_uom"]
        return tier.provider_item_batches[0]["price_per_uom"]

    return None
```

**Pricing Resolution Order**:
1. Find tier matching the requested quantity
2. If tier has `price_per_uom` → use it directly
3. If tier has `margin_per_uom` → use matching batch's calculated price
4. If `batch_no` specified → find that specific batch
5. Otherwise → use first available batch
6. If no tier or batch found → return None (pricing error)

---

### End-to-End Pricing Flow

```
1. USER INITIATES QUOTE CREATION
   ↓
2. IDENTIFY SEGMENT
   - Get segment_uuid from SegmentContact (via email)
   ↓
3. FOR EACH QUOTE ITEM:
   a) Validate: item_uuid, qty, segment_uuid, provider_item_uuid

   b) FIND MATCHING PRICE TIER
      - Query: ItemPriceTierModel WHERE:
        * item_uuid = requested item
        * provider_item_uuid = requested provider
        * segment_uuid = contact's segment
        * quantity_greater_then ≤ qty < quantity_less_then
        * status = "active"

   c) CALCULATE PRICE FROM TIER
      Option 1: IF tier.price_per_uom IS NOT NULL
         → price_per_uom = tier.price_per_uom

      Option 2: IF tier.margin_per_uom IS NOT NULL
         → Load ProviderItemBatches for tier.provider_item_uuid
         → IF batch_no specified:
              price_per_uom = matching_batch.total_cost_per_uom * (1 + margin/100)
            ELSE:
              price_per_uom = first_batch.total_cost_per_uom * (1 + margin/100)

   d) AUTO-CALCULATE QUOTE ITEM TOTALS
      - subtotal = price_per_uom * qty
      - If subtotal_discount provided:
          final_subtotal = subtotal - discount
        ELSE:
          final_subtotal = subtotal

   e) STORE QUOTE ITEM
      ↓
4. AGGREGATE QUOTE TOTALS
   - total_quote_amount = SUM(all quote_items.subtotal)
   - total_quote_discount = SUM(all quote_items.subtotal_discount)
   - items_final_total = SUM(all quote_items.final_subtotal)
   - final_total_quote_amount = items_final_total + shipping_amount
   ↓
5. APPLY DISCOUNT PROMPTS (Optional - per business logic)
   - Query: DiscountPromptModel WHERE:
     * status = "active"
     * scope matches (global, segment, or item via tags)
     * greater_than ≤ subtotal < less_than
   - Apply highest priority matching prompt
   - Get max_discount_percentage from matching tier
   - User can apply up to this percentage
   ↓
6. RETURN QUOTE TO USER
   - price_per_uom (from tier)
   - qty
   - subtotal
   - subtotal_discount (if applied)
   - final_subtotal
   - guardrail_price_per_uom (from batch or provider_item)
   - slow_move_item (flag from batch)
```

---

## Relationships Diagram

```
Segment (pricing segment)
├── segment_uuid
├── provider_corp_external_id (which provider serves this segment)
└── [segment_contact links contacts to segment]
    └── email → SegmentContact → segment_uuid

Item
├── item_uuid
├── item_type, item_name, uom (Unit of Measure)
└── [Price tiers tied to item]

SegmentContact
├── email (contact identity)
├── segment_uuid (which segment/pricing this contact belongs to)
└── contact_uuid, consumer_corp_external_id

Provider_Item (Item offered by a Provider)
├── provider_item_uuid
├── item_uuid (which item)
├── provider_corp_external_id (which provider)
├── base_price_per_uom (fallback price)
├── [Price tiers for this provider's offering]
└── [Batches with cost details]

Item_Price_Tier
├── item_price_tier_uuid
├── item_uuid (hash key)
├── provider_item_uuid (which provider's pricing)
├── segment_uuid (which segment this tier applies to)
├── quantity_greater_then, quantity_less_then (quantity ranges)
├── price_per_uom OR margin_per_uom
└── [Provider_Item_Batches if margin-based]

Provider_Item_Batch
├── batch_no
├── provider_item_uuid (which provider item)
├── cost_per_uom, freight_cost_per_uom, additional_cost_per_uom
├── total_cost_per_uom (auto-calculated)
├── guardrail_margin_per_uom, guardrail_price_per_uom
├── slow_move_item, in_stock (status flags)
└── [Used by price tiers with margin_per_uom]

Discount_Prompt
├── discount_prompt_uuid
├── endpoint_id (hash key)
├── scope (global, segment, or item)
├── tags (flexible matching via tags)
├── discount_prompt (AI prompt for logic)
├── conditions (conditional logic)
├── discount_rules (list of tier objects)
│   └── [{greater_than, less_than, max_discount_percentage}, ...]
├── priority (conflict resolution)
└── status (in_review, active, inactive)

Quote_Item (Line item in a quote)
├── quote_item_uuid
├── quote_uuid (parent quote)
├── item_uuid, provider_item_uuid, batch_no
├── qty (requested quantity)
├── price_per_uom (looked up from tiers)
├── subtotal = price_per_uom * qty
├── subtotal_discount (manually applied)
└── final_subtotal = subtotal - discount

Quote (Order proposal)
├── quote_uuid
├── request_uuid (parent request)
├── provider_corp_external_id
├── shipping_amount
├── total_quote_amount = SUM(quote_items.subtotal)
├── total_quote_discount = SUM(quote_items.discount)
└── final_total_quote_amount = items_final + shipping
```

---

## Business Logic Patterns

### 1. Cascading Tier Structure

**Implementation**: [ai_rfq_engine/models/item_price_tier.py:40-105](../ai_rfq_engine/models/item_price_tier.py#L40-L105)

When inserting a new tier:
- The "last tier" (where `quantity_less_then = NULL`) is fetched
- New tier's `quantity_greater_then` must be > previous tier's `quantity_greater_then`
- New tier is saved with `quantity_less_then = NULL`
- Previous tier is updated to set its `quantity_less_then = new_tier.quantity_greater_then`

This ensures proper tier sequencing without gaps.

**Applied to**:
- ItemPriceTier (quantity-based tiers)
- DiscountPrompt.discount_rules (subtotal-based tiers within each prompt)

---

### 2. Margin-Based Dynamic Pricing

**Implementation**: [ai_rfq_engine/graphql/item_price_tier/types.py:61-82](../ai_rfq_engine/graphql/item_price_tier/types.py#L61-L82)

Tiers can specify `margin_per_uom` instead of fixed `price_per_uom`:
- Margin is applied to batch's `total_cost_per_uom`
- Allows prices to vary by batch's actual costs
- Formula: `price = total_cost_per_uom * (1 + margin_per_uom / 100)`

**Benefits**:
- Prices automatically adjust to cost fluctuations
- Different batches can have different prices
- Maintains target margin while adapting to market conditions

---

### 3. Segment-Based Pricing

Different segments can have different prices for the same item/provider:
- `segment_uuid` is a key dimension in ItemPriceTier and DiscountRule
- Enables customer-specific or region-specific pricing
- Supports multiple pricing strategies simultaneously

**Example**:
```
Item: "Widget A"
Provider: "Acme Corp"

Segment: "Premium Customers"
  Tier 1: qty >= 0,   qty < 100  → $10/unit
  Tier 2: qty >= 100, qty < NULL → $9/unit

Segment: "Standard Customers"
  Tier 1: qty >= 0,   qty < 100  → $12/unit
  Tier 2: qty >= 100, qty < NULL → $11/unit
```

---

### 4. Guardrail Safety Prices

**Implementation**:
- [ai_rfq_engine/models/provider_item.py:16](../ai_rfq_engine/models/provider_item.py#L16) - `base_price_per_uom`
- [ai_rfq_engine/models/provider_item_batches.py:70-73](../ai_rfq_engine/models/provider_item_batches.py#L70-L73) - `guardrail_price_per_uom`

Two levels of safety pricing:
1. **Provider_Item.base_price_per_uom**: Fallback if no tier matches
2. **ProviderItemBatch.guardrail_price_per_uom**: Batch-level safety floor

**Calculation**:
```python
guardrail_price_per_uom = total_cost_per_uom * (1 + guardrail_margin_per_uom / 100)
```

Prevents unexpected pricing gaps and ensures minimum margins.

---

### 5. Automatic Total Calculation

**Implementation**:
- [ai_rfq_engine/models/quote_item.py:247-312](../ai_rfq_engine/models/quote_item.py#L247-L312) - Quote item totals
- [ai_rfq_engine/models/quote.py:182-220](../ai_rfq_engine/models/quote.py#L182-L220) - Quote totals

**Quote Item Level**:
```python
subtotal = price_per_uom * qty
final_subtotal = subtotal - subtotal_discount
```

**Quote Level**:
```python
total_quote_amount = SUM(quote_items.subtotal)
total_quote_discount = SUM(quote_items.subtotal_discount)
final_total_quote_amount = SUM(quote_items.final_subtotal) + shipping_amount
```

All calculations are performed automatically - no manual intervention required.

---

### 6. Batch-Level Cost Tracking

**Implementation**: [ai_rfq_engine/models/provider_item_batches.py:66-73](../ai_rfq_engine/models/provider_item_batches.py#L66-L73)

Costs are broken down into components:
1. **Product cost**: `cost_per_uom`
2. **Freight**: `freight_cost_per_uom`
3. **Additional costs**: `additional_cost_per_uom`
4. **Total**: Auto-calculated sum

**Auto-Calculation**:
```python
total_cost_per_uom = cost_per_uom + freight_cost_per_uom + additional_cost_per_uom
```

**Benefits**:
- Enables detailed cost analysis
- Supports margin tracking
- Facilitates dynamic pricing based on real costs

---

## Database Indexing Strategy

### ItemPriceTier Indexes
- **provider_item_uuid_index**: Provider-specific tier lookup
- **segment_uuid_index**: Segment-specific tier lookup
- **updated_at_index**: Time-based queries

### ProviderItem Indexes
- **item_uuid_index**: Find all providers offering an item
- **provider_corp_external_id_index**: Find all items from a provider
- **updated_at_index**: Modification tracking

### QuoteItem Indexes
- **provider_item_uuid_index**: Quote items by provider
- **item_uuid_index**: Quote items by item
- **item_uuid_provider_item_uuid_index**: Global secondary index for combined queries
- **updated_at_index**: Temporal queries

### Quote Indexes
- **provider_corp_external_id_index**: Quotes by provider
- **provider_corp_external_id_quote_uuid_index**: Global secondary index
- **updated_at_index**: Temporal queries

---

## Performance Optimization

### Batch Loaders

**Files**:
- [ai_rfq_engine/graphql/batch_loaders/provider_item_batch_list_loader.py](../ai_rfq_engine/graphql/batch_loaders/provider_item_batch_list_loader.py)
- [ai_rfq_engine/graphql/batch_loaders/item_price_tier_by_provider_item_loader.py](../ai_rfq_engine/graphql/batch_loaders/item_price_tier_by_provider_item_loader.py)

**ProviderItemBatchListLoader**:
- Efficiently loads batches for multiple provider items
- Used in ItemPriceTierType.resolve_provider_item_batches()
- Applies margin calculation after loading
- Caches results to reduce database hits

**ItemPriceTierByProviderItemLoader**:
- Loads price tiers by (item_uuid, provider_item_uuid)
- Reduces N+1 query problems
- Implements caching via HybridCacheEngine

**Caching**:
- Configurable TTL via HybridCacheEngine
- Both in-memory and distributed caching support
- Automatic cache invalidation on updates

---

## Summary

The pricing system is a **sophisticated multi-tier architecture** that:

1. **Links contacts to pricing segments** via SegmentContact
2. **Supports dynamic tiered pricing** based on quantity bands
3. **Enables margin-based dynamic pricing** using batch cost data
4. **Implements segment-specific pricing** for different customer groups
5. **Automates calculations** at item, quote, and aggregate levels
6. **Provides safety guardrails** through base prices and margins
7. **Scales efficiently** through batch loaders and caching
8. **Maintains referential integrity** through deletion constraints
9. **Supports AI-driven discount prompts** with flexible scoping and priority-based conflict resolution

The system prioritizes:
- **Efficiency** through database-level tier matching
- **Accuracy** through automated calculations
- **Flexibility** through multiple pricing mechanisms (fixed price, margin-based, dynamic batches)
- **Scalability** through strategic indexing and caching
