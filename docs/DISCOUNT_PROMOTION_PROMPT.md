# Product Pricing & Promotion Prompt System

## Overview

The AI RFQ Engine implements a **two-stage pricing and discount system**. In the first stage, a structured pricing engine calculates a `price_per_uom` for each quote line item using quantity-based tiers, batch cost data, and margin rules. In the second stage, a hierarchical AI-native promotion system overlays discount logic on top of those prices — storing both machine-readable `discount_rules` and a human-readable `discount_prompt` string that are surfaced to Claude or another LLM to make intelligent, context-aware discount decisions.

This document covers both stages end-to-end.

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Pricing Structure](#2-pricing-structure)
   - [2.1 Data Models Involved in Pricing](#21-data-models-involved-in-pricing)
   - [2.2 Price Tier Mechanics](#22-price-tier-mechanics)
   - [2.3 Batch Cost & Guardrail Pricing](#23-batch-cost--guardrail-pricing)
   - [2.4 Slow-Move Item Pricing](#24-slow-move-item-pricing)
   - [2.5 get_price_per_uom() — Full Algorithm](#25-get_price_per_uom--full-algorithm)
   - [2.6 Price Tier Insertion & Validation](#26-price-tier-insertion--validation)
3. [DiscountPrompt Data Model](#3-discountprompt-data-model)
4. [Discount Rule Validation](#4-discount-rule-validation)
5. [Scope Hierarchy](#5-scope-hierarchy)
6. [Prompt Assembly Flow (combine_all_discount_prompts)](#6-prompt-assembly-flow)
7. [Applying Discounts to Quote Items](#7-applying-discounts-to-quote-items)
8. [How AI Uses Discount Prompts](#8-how-ai-uses-discount-prompts)
9. [GraphQL Interface](#9-graphql-interface)
10. [Batch Loader Architecture](#10-batch-loader-architecture)
11. [End-to-End Data Flow](#11-end-to-end-data-flow)
12. [Key Files Reference](#12-key-files-reference)

---

## 1. System Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│              COMPLETE PRICING & PROMOTION PIPELINE                    │
│                                                                       │
│  STAGE 1 — PRICE CALCULATION                                          │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  Item + Segment + ProviderItem + Qty                          │    │
│  │     └──► Match ItemPriceTier  ──────────────────────────────┐ │    │
│  │              ├── price_per_uom (fixed)  ──────────────────► │ │    │
│  │              └── margin_per_uom (dynamic)                   │ │    │
│  │                     └──► ProviderItemBatch costs            │ │    │
│  │                               ├── slow_move? → guardrail    │ │    │
│  │                               └── normal → cost × (1+margin)│ │    │
│  │                                                    price_per_uom   │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  STAGE 2 — DISCOUNT / PROMOTION PROMPT                                │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │  GLOBAL → SEGMENT → ITEM → PROVIDER_ITEM prompts merged       │    │
│  │     └──► Passed to Claude / LLM with discount_rules           │    │
│  │              └──► AI returns subtotal_discount per item       │    │
│  │                       └──► final_subtotal recalculated        │    │
│  └───────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

**Key design principles:**

| Principle | Detail |
|---|---|
| Pricing is deterministic | `price_per_uom` is always resolved from tiers + batch data before AI involvement |
| Discounts are AI-driven | Claude receives structured rules AND natural-language prompts to decide `subtotal_discount` |
| Guardrail protects margin | `guardrail_price_per_uom` is a hard floor; slow-move items always use it |
| Scope hierarchy is additive | All applicable prompts at all scopes are merged and given to the AI |

---

## 2. Pricing Structure

### 2.1 Data Models Involved in Pricing

Pricing is calculated from a chain of four models:

```
Item  ──(item_uuid)──►  ProviderItem  ──(provider_item_uuid)──►  ProviderItemBatch
 │                           │                                         │
 │  defines UOM              │  base_price_per_uom (fallback)          │  batch-level costs
 │                           │                                         │  guardrail_price_per_uom
 └───────────────────────────┴──────────────────────────────────────────┘
                             │
                     ItemPriceTier
                       (item_uuid + provider_item_uuid + segment_uuid + qty range)
                       ├── price_per_uom  (fixed price path)
                       └── margin_per_uom (dynamic cost-plus path)
```

#### Item Model
**File**: [ai_rfq_engine/models/item.py](../ai_rfq_engine/models/item.py)  
**Table**: `are-items`

The base catalog entity. Defines the Unit of Measure (`uom`) used throughout all per-unit price calculations. No direct pricing fields — it is the root key under which all price tiers are indexed.

```python
item_uuid        # hash key — primary reference in price tiers
item_type        # category of item
item_name
uom              # "pieces", "kg", "liter" — referenced in price display
```

#### ProviderItem Model
**File**: [ai_rfq_engine/models/provider_item.py](../ai_rfq_engine/models/provider_item.py)  
**Table**: `are-provider_items`

Bridges a catalog item to a specific provider's offering. Holds a `base_price_per_uom` that acts as a reference/fallback price.

```python
provider_item_uuid           # range key
item_uuid                    # foreign key to Item
provider_corp_external_id    # identifies the provider
base_price_per_uom           # baseline price — used as fallback / reference
item_spec                    # provider-specific specification map
```

#### ProviderItemBatch Model
**File**: [ai_rfq_engine/models/provider_item_batches.py](../ai_rfq_engine/models/provider_item_batches.py)  
**Table**: `are-provider_item_batches`

Tracks a specific physical batch or lot of a provider item, with detailed cost breakdown and computed guardrail price. This is where dynamic, cost-based pricing originates.

```python
provider_item_uuid           # hash key
batch_no                     # range key — lot/batch identifier
cost_per_uom                 # product cost
freight_cost_per_uom         # inbound shipping cost
additional_cost_per_uom      # other costs (duties, handling, etc.)
total_cost_per_uom           # auto-calculated: cost + freight + additional
guardrail_margin_per_uom     # minimum acceptable margin (as decimal, e.g. 0.20)
guardrail_price_per_uom      # auto-calculated: total_cost × (1 + guardrail_margin)
slow_move_item               # boolean — slow-moving inventory flag
in_stock                     # boolean — availability
expired_at / produced_at     # batch lifecycle dates
```

#### ItemPriceTier Model
**File**: [ai_rfq_engine/models/item_price_tier.py](../ai_rfq_engine/models/item_price_tier.py)  
**Table**: `are-item_price_tiers`

The central pricing configuration. Each tier defines a quantity range for a specific `(item, provider_item, segment)` combination and specifies either a fixed price or a margin to apply to batch costs.

```python
item_uuid                    # hash key
item_price_tier_uuid         # range key
provider_item_uuid           # which provider this tier applies to
segment_uuid                 # which customer segment this tier applies to
quantity_greater_then        # lower bound of quantity range (inclusive)
quantity_less_then           # upper bound of quantity range (exclusive); null = open-ended
price_per_uom                # Option A: fixed direct price
margin_per_uom               # Option B: margin multiplier applied to batch total_cost_per_uom
status                       # "in_review" | "active" | "inactive"
```

---

### 2.2 Price Tier Mechanics

A tier is selected at query time by matching the requested `qty` against the tier's quantity range:

```
tier matches when:
  quantity_greater_then <= qty  AND  (quantity_less_then > qty  OR  quantity_less_then IS NULL)
```

This filter is applied **at the DynamoDB level** using a filter expression, so only the one matching tier is returned.

#### Tier Range Examples

```
Segment: "enterprise"  |  ProviderItem: "pi_widget_001"
──────────────────────────────────────────────────────────
Tier 1:  qty >= 0    and qty < 50    →  price_per_uom = $12.00
Tier 2:  qty >= 50   and qty < 200   →  price_per_uom = $10.50
Tier 3:  qty >= 200  and qty < 500   →  margin_per_uom = 0.25  (cost + 25%)
Tier 4:  qty >= 500  (open-ended)    →  margin_per_uom = 0.20  (cost + 20%)
```

#### Two Pricing Paths

| Path | Field Used | Calculation |
|---|---|---|
| **Fixed price** | `price_per_uom` | Return directly — no batch lookup needed |
| **Cost-plus (margin)** | `margin_per_uom` | Load batches → compute `total_cost × (1 + margin)` per batch |

---

### 2.3 Batch Cost & Guardrail Pricing

When a batch is created or updated, the engine auto-computes two derived fields:

```python
# Batch creation (insert_update_provider_item_batch)
total_cost_per_uom = cost_per_uom + freight_cost_per_uom + additional_cost_per_uom

guardrail_price_per_uom = total_cost_per_uom * (1 + guardrail_margin_per_uom)
```

**On update**, the same formula recalculates both fields using the latest values of all three cost components and the guardrail margin.

#### Cost Breakdown Example

```
Batch: BATCH-2024-Q3-001
──────────────────────────────────────────
cost_per_uom            = $30.00  (product)
freight_cost_per_uom    =  $5.00  (inbound shipping)
additional_cost_per_uom =  $2.00  (duties)
──────────────────────────────────────────
total_cost_per_uom      = $37.00  (auto-calculated)

guardrail_margin_per_uom = 0.15   (15% minimum margin)
guardrail_price_per_uom  = $37.00 × 1.15 = $42.55  (auto-calculated floor)
```

The `guardrail_price_per_uom` is the **hard price floor** — no quote should be created below this price.

---

### 2.4 Slow-Move Item Pricing

When `slow_move_item = True` on a batch, the pricing engine **ignores** the tier's `margin_per_uom` and substitutes the pre-computed `guardrail_price_per_uom` instead.

```python
# In get_price_per_uom() — quote_item.py
if batch.slow_move_item is True:
    price = batch.guardrail_price_per_uom   # fixed floor for slow-movers
else:
    price = batch.total_cost_per_uom * (1 + float(tier.margin_per_uom))
```

**Why:** Slow-moving inventory carries higher holding costs. Using the guardrail price rather than a potentially low margin-based price ensures the company does not take a loss when trying to move aged stock.

---

### 2.5 get_price_per_uom() — Full Algorithm

**File**: [ai_rfq_engine/models/quote_item.py:36](../ai_rfq_engine/models/quote_item.py#L36)

```python
def get_price_per_uom(
    info,
    item_uuid,
    qty,
    segment_uuid,
    provider_item_uuid,
    batch_no=None        # optional: pin to a specific batch
) -> float | None:
```

```
INPUT: item_uuid, qty, segment_uuid, provider_item_uuid, [batch_no]
  │
  ▼
Query ItemPriceTierModel
  WHERE item_uuid        = item_uuid
  AND   provider_item_uuid = provider_item_uuid
  AND   segment_uuid     = segment_uuid
  AND   status           = "active"
  AND   quantity_greater_then <= qty
  AND   (quantity_less_then > qty OR quantity_less_then IS NULL)
  │
  ├── No match found → return None
  │
  └── Match found → tier
        │
        ├── tier.price_per_uom is not None
        │     └── return tier.price_per_uom            ← FIXED PRICE PATH
        │
        └── tier.margin_per_uom is not None
              │
              ▼
              Load all ProviderItemBatch where provider_item_uuid = provider_item_uuid
                │
                For each batch:
                  ├── slow_move_item = True  → price = guardrail_price_per_uom
                  └── slow_move_item = False → price = total_cost_per_uom × (1 + margin_per_uom)
                │
                ├── batch_no specified → return price for that batch
                └── batch_no not specified → return price of first batch
```

#### Example Walkthrough

```
Request: item_uuid="item_001", qty=150, segment="enterprise", provider_item="pi_001"

Step 1 — Tier query:
  Tiers for (item_001, pi_001, enterprise):
    Tier A: qty >= 0   < 50    price_per_uom = 12.00
    Tier B: qty >= 50  < 200   margin_per_uom = 0.25   ← matches qty=150
    Tier C: qty >= 200         margin_per_uom = 0.20

Step 2 — Selected tier: Tier B (margin_per_uom = 0.25)
  No price_per_uom → take the margin path

Step 3 — Load batches for pi_001:
  Batch "B-2024-001": total_cost=$40.00, slow_move=False → price = 40 × 1.25 = $50.00
  Batch "B-2024-002": total_cost=$45.00, slow_move=True  → price = guardrail = $52.00

Step 4 — No batch_no specified → use first batch
  → return $50.00
```

---

### 2.6 Price Tier Insertion & Validation

**File**: [ai_rfq_engine/models/item_price_tier.py:484](../ai_rfq_engine/models/item_price_tier.py#L484)

Tiers are maintained as a **linked chain** ordered by `quantity_greater_then`. When a new tier is inserted, the system automatically closes the previous open-ended tier:

```
Before insert:
  Tier 1: qty >= 0  (quantity_less_then = NULL)  ← current last tier

Insert new tier: quantity_greater_then = 100

After insert:
  Tier 1: qty >= 0  and qty < 100  ← quantity_less_then auto-set to 100
  Tier 2: qty >= 100 (quantity_less_then = NULL)  ← new last tier
```

#### Validation Rules

```
1. quantity_greater_then must be >= 0
2. provider_item_uuid is required
3. segment_uuid is required
4. New tier's quantity_greater_then must be GREATER than the current last tier's
   quantity_greater_then (i.e., tiers can only extend upward)
5. Exactly one of price_per_uom or margin_per_uom should be set per tier
6. status defaults to "in_review" until activated
```

#### Tier Insertion Sequence

```
InsertUpdateItemPriceTier mutation called
    │
    ▼
_get_previous_tier()
  → query for current last tier (quantity_less_then IS NULL)
  → validate new qty_greater_then > previous qty_greater_then
    │
    ▼
Save new ItemPriceTierModel(quantity_less_then=None)
    │
    ▼
_update_previous_tier()
  → update previous tier: quantity_less_then = new tier's quantity_greater_then
```

---

## 3. DiscountPrompt Data Model

**File**: [ai_rfq_engine/models/discount_prompt.py](../ai_rfq_engine/models/discount_prompt.py)

**DynamoDB table**: `are-discount_prompts`

```python
class DiscountPromptModel(BaseModel):
    table_name = "are-discount_prompts"

    partition_key = UnicodeAttribute(hash_key=True)   # endpoint_id (tenant)
    discount_prompt_uuid = UnicodeAttribute(range_key=True)

    scope = UnicodeAttribute()          # "global" | "segment" | "item" | "provider_item"
    tags = UnicodeSetAttribute(null=True)  # UUIDs: segment/item/provider_item identifiers
    priority = NumberAttribute(default=0)  # Conflict resolution — higher wins
    discount_prompt = UnicodeAttribute()   # AI/LLM instruction text
    conditions = ListAttribute(null=True)  # JSON strings: contextual criteria for AI
    discount_rules = ListAttribute(null=True)  # Tiered discount structure (see below)
    status = UnicodeAttribute(default="in_review")  # "in_review" | "active" | "inactive"
```

### Field Details

#### `scope`
Controls which quotes/items this prompt applies to:

| Value | Match Condition |
|---|---|
| `global` | All quotes for the tenant |
| `segment` | Quotes where the buyer's email maps to a `segment_uuid` in `tags` |
| `item` | Quote items where `item_uuid` is in `tags` |
| `provider_item` | Quote items where `provider_item_uuid` is in `tags` |

#### `tags`
A set of UUIDs used for matching:
```python
# SEGMENT scope example
tags = {"seg_vip_001", "seg_enterprise_002"}

# ITEM scope example
tags = {"item_clearance_003"}

# PROVIDER_ITEM scope example
tags = {"pi_acme_widget_007"}
```
For GLOBAL scope, `tags` is not used (all quotes match).

#### `discount_prompt`
Free-form natural language instruction passed to the AI layer. Examples:
```
"Apply a volume discount based on the order total per the discount_rules table."
"Clearance item — apply the maximum discount percentage if the customer is in the VIP segment."
"If this is a repeat customer ordering >10 units, apply 15% off."
```

#### `discount_rules`
Structured tiered discount table:
```python
[
    {"greater_than": 0,     "less_than": 500,  "max_discount_percentage": 5},
    {"greater_than": 500,   "less_than": 2000, "max_discount_percentage": 10},
    {"greater_than": 2000,  "less_than": 5000, "max_discount_percentage": 15},
    {"greater_than": 5000,                     "max_discount_percentage": 20}
    # Note: last tier has no "less_than" — open-ended
]
```

#### `conditions`
Optional list of JSON strings that the AI evaluates before applying the prompt:
```python
conditions = [
    '{"field": "customer_type", "operator": "==", "value": "recurring"}',
    '{"field": "order_frequency", "operator": ">", "value": 5}'
]
```

#### `priority`
Integer used when multiple prompts could apply. Higher priority prompts are considered first by the AI. Recommended convention:
- `0` — GLOBAL (baseline)
- `10` — SEGMENT
- `20` — ITEM
- `30` — PROVIDER_ITEM

---

## 4. Discount Rule Validation

**Function**: `validate_and_normalize_discount_rules()` in [ai_rfq_engine/models/discount_prompt.py](../ai_rfq_engine/models/discount_prompt.py#L37)

Before saving, all `discount_rules` are validated and auto-sorted. The rules enforce a strict, gap-free tiered structure:

### Validation Rules

```
1. First tier MUST have greater_than == 0
   └─ Ensures full coverage from zero

2. For every non-last tier:
   ├─ less_than MUST be present
   └─ less_than > greater_than

3. For the last tier:
   └─ less_than MUST NOT be present (open-ended)

4. Tiers must be contiguous (no gaps, no overlaps):
   └─ rules[i].less_than == rules[i+1].greater_than

5. max_discount_percentage must INCREASE with each higher tier:
   └─ rules[i+1].max_discount_percentage > rules[i].max_discount_percentage
   (Higher orders must yield better discounts)

6. max_discount_percentage must be 0–100 (percent)
```

### Validation Flow

```
Input rules (unsorted, user-provided)
    │
    ▼
Sort by greater_than ASC
    │
    ▼
Check first tier starts at 0
    │
    ▼
For each tier: validate less_than / continuity
    │
    ▼
Check last tier has no less_than
    │
    ▼
Check max_discount_percentage is monotonically increasing
    │
    ▼
Return normalized, sorted rules  ──or──  raise ValueError
```

### Example: Valid vs. Invalid Rules

```python
# VALID: contiguous tiers, increasing discounts
valid_rules = [
    {"greater_than": 0,   "less_than": 1000, "max_discount_percentage": 5},
    {"greater_than": 1000,"less_than": 5000, "max_discount_percentage": 10},
    {"greater_than": 5000,                   "max_discount_percentage": 15},
]

# INVALID: gap between 1000 and 2000
invalid_gap = [
    {"greater_than": 0,   "less_than": 1000, "max_discount_percentage": 5},
    {"greater_than": 2000,                   "max_discount_percentage": 10},
]

# INVALID: discount does not increase (10 → 8)
invalid_decreasing = [
    {"greater_than": 0,    "less_than": 500, "max_discount_percentage": 10},
    {"greater_than": 500,                    "max_discount_percentage": 8},
]
```

---

## 5. Scope Hierarchy

The scope system enables fine-grained promotion targeting. Prompts at multiple scopes can apply simultaneously to the same quote — they are merged and all passed to the AI.

```
GLOBAL
  │  Matches: every quote for the tenant
  │  Used for: universal policies (e.g. "orders >$5k get free shipping")
  │
  ├── SEGMENT
  │     Matches: quotes where buyer email → segment_uuid ∈ tags
  │     Used for: customer tier promotions (VIP, wholesale, reseller)
  │
  │     ├── ITEM
  │     │     Matches: quote items where item_uuid ∈ tags
  │     │     Used for: item-specific campaigns (clearance, seasonal)
  │     │
  │     └── PROVIDER_ITEM
  │           Matches: quote items where provider_item_uuid ∈ tags
  │           Used for: supplier-specific incentives
```

### Scope Matching Logic

```python
# GLOBAL: no tag check needed
scope == "global"

# SEGMENT: look up segment from buyer's email, check if segment_uuid in tags
SegmentContactModel.get(email) → segment_uuid
DiscountPromptModel.tags.contains(segment_uuid)

# ITEM: check if item_uuid appears in tags for any quote item
DiscountPromptModel.tags.contains(item_uuid)

# PROVIDER_ITEM: check if provider_item_uuid appears in tags
DiscountPromptModel.tags.contains(provider_item_uuid)
```

---

## 6. Prompt Assembly Flow

**Function**: `combine_all_discount_prompts()` in [ai_rfq_engine/models/utils.py](../ai_rfq_engine/models/utils.py#L122)

This function is the central aggregation point. It collects discount prompts from all applicable scopes using batch loaders (DataLoader pattern) and merges them into a single deduplicated list for the AI.

### Function Signature

```python
def combine_all_discount_prompts(
    partition_key: str,      # Tenant identifier
    email: str,              # Buyer email — used for segment lookup
    quote_items: List[Dict], # Items in the quote (each has item_uuid, provider_item_uuid)
    loaders: RequestLoaders  # Batch loader container
) -> Promise[List[Dict]]
```

### Step-by-Step Assembly

```
Step 1: Load GLOBAL prompts
────────────────────────────
  loader: DiscountPromptGlobalLoader
  key: partition_key
  query: scope = "global" AND status = "active"
  always included

Step 2: Resolve segment from buyer email
─────────────────────────────────────────
  loader: SegmentContactLoader
  key: (partition_key, email)
  query: SegmentContactModel where email = buyer_email
  result: segment_uuid (or None if no match)

Step 3: Collect item UUIDs from quote items
────────────────────────────────────────────
  Extract unique item_uuid values
  Extract unique (item_uuid, provider_item_uuid) pairs

Step 4: Load SEGMENT prompts (if segment found)
────────────────────────────────────────────────
  loader: DiscountPromptBySegmentLoader
  key: (partition_key, segment_uuid)
  query: scope = "segment" AND tags.contains(segment_uuid) AND status = "active"

Step 5: Batch-load ITEM and PROVIDER_ITEM prompts (parallel)
─────────────────────────────────────────────────────────────
  ITEM:
    loader: DiscountPromptByItemLoader
    keys: [(partition_key, item_uuid) for each unique item]
    query: scope = "item" AND tags.contains(item_uuid) AND status = "active"

  PROVIDER_ITEM:
    loader: DiscountPromptByProviderItemLoader
    keys: [(partition_key, item_uuid, provider_item_uuid) for each pair]
    query: scope = "provider_item" AND tags.contains(provider_item_uuid) AND status = "active"

Step 6: Merge and deduplicate
──────────────────────────────
  Combine all results from steps 1, 4, 5
  Deduplicate by discount_prompt_uuid (first occurrence wins)
  Normalize each entry to JSON dict
  Return merged list
```

### Sequence Diagram

```
Client                utils.py              DB (DynamoDB)
  │                      │                       │
  │  combine_all(...)     │                       │
  │──────────────────────►│                       │
  │                       │ load(partition_key)   │
  │                       │──────────────────────►│ GLOBAL query
  │                       │◄──────────────────────│
  │                       │ load(partition_key,   │
  │                       │      email)           │
  │                       │──────────────────────►│ SegmentContact query
  │                       │◄──────────────────────│ → segment_uuid
  │                       │                       │
  │                       │ [parallel]            │
  │                       │ load(segment_uuid) ──►│ SEGMENT query
  │                       │ load(item_uuid×N) ───►│ ITEM queries
  │                       │ load(pi_uuid×N) ─────►│ PROVIDER_ITEM queries
  │                       │◄──────────────────────│
  │                       │                       │
  │                       │ merge + deduplicate   │
  │◄──────────────────────│                       │
  │  [merged prompt list] │                       │
```

---

## 7. Applying Discounts to Quote Items

Discounts are stored at the quote-item level as `subtotal_discount` and reflected in `final_subtotal`.

### Quote Item Discount Fields

```python
class QuoteItemModel(BaseModel):
    subtotal          = NumberAttribute()   # price_per_uom * qty
    subtotal_discount = NumberAttribute(null=True)  # discount amount in currency
    final_subtotal    = NumberAttribute()   # subtotal - subtotal_discount
```

### Discount Application

**File**: [ai_rfq_engine/models/quote_item.py](../ai_rfq_engine/models/quote_item.py#L437)

```python
# On creation or update:
subtotal = price_per_uom * qty
final_subtotal = subtotal - (subtotal_discount or 0)
```

After any quote item discount change, quote totals are recalculated:

```python
# update_quote_totals() in quote.py
total_quote_amount       = sum(item.subtotal for item in items)
total_quote_discount     = sum(item.subtotal_discount or 0 for item in items)
items_final_total        = sum(item.final_subtotal for item in items)
final_total_quote_amount = items_final_total + shipping_amount
```

### Discount Update Flow

```
AI decides: apply $75 discount to quote item "qi_001"
    │
    ▼
GraphQL mutation: InsertUpdateQuoteItem(
    quote_item_uuid = "qi_001",
    subtotal_discount = 75
)
    │
    ▼
quote_item.subtotal_discount = 75
quote_item.final_subtotal    = quote_item.subtotal - 75
    │
    ▼
update_quote_totals(quote_uuid)  ← recalculates all quote-level fields
    │
    ▼
QuoteModel.total_quote_discount     += 75
QuoteModel.final_total_quote_amount  = (sum of final_subtotals) + shipping
```

---

## 8. How AI Uses Discount Prompts

The assembled prompt list from `combine_all_discount_prompts()` is passed to Claude (or another LLM). The AI receives a context payload that looks like:

### AI Input Payload (conceptual)

```json
{
  "quote_items": [
    {
      "quote_item_uuid": "qi_001",
      "item_uuid": "item_001",
      "provider_item_uuid": "pi_001",
      "qty": 150,
      "price_per_uom": 50.0,
      "subtotal": 7500.0
    }
  ],
  "discount_prompts": [
    {
      "discount_prompt_uuid": "dp_001",
      "scope": "global",
      "priority": 0,
      "discount_prompt": "Apply volume discount for orders over $1000.",
      "discount_rules": [
        {"greater_than": 0,    "less_than": 1000, "max_discount_percentage": 5},
        {"greater_than": 1000, "less_than": 5000, "max_discount_percentage": 10},
        {"greater_than": 5000,                    "max_discount_percentage": 15}
      ],
      "conditions": []
    },
    {
      "discount_prompt_uuid": "dp_003",
      "scope": "segment",
      "priority": 10,
      "discount_prompt": "Preferred customer — apply 10% off total.",
      "discount_rules": [],
      "conditions": ["customer_type == 'preferred'"]
    }
  ]
}
```

### AI Decision Logic

The LLM is expected to:

1. **Read each discount prompt's instruction text** (`discount_prompt`) to understand the policy intent.
2. **Evaluate `conditions`** — determine whether each prompt is applicable given the quote context.
3. **Apply `discount_rules`** — find the correct tier by matching `subtotal` against `greater_than`/`less_than` thresholds.
4. **Respect `priority`** — when two prompts conflict, higher priority wins.
5. **Calculate `subtotal_discount`** — as a currency amount (not percentage), bounded by `max_discount_percentage`.
6. **Output per-item discounts** — for each `quote_item_uuid`, specify the `subtotal_discount` to apply.

### Example AI Reasoning

```
Quote item qi_001 has subtotal = $7,500.

Prompt dp_001 (GLOBAL, priority 0):
  - Rule match: greater_than=5000 (no less_than) → max 15% discount
  - Max discount = 7500 * 0.15 = $1,125

Prompt dp_003 (SEGMENT, priority 10, condition: customer_type == 'preferred'):
  - Customer is 'preferred' → condition met
  - Flat 10% discount = 7500 * 0.10 = $750

Priority resolution: dp_003 (priority 10) > dp_001 (priority 0)
Final discount = $750 (from preferred customer rule)

→ subtotal_discount = 750.0
→ final_subtotal    = 7500.0 - 750.0 = 6750.0
```

---

## 9. GraphQL Interface

### Mutations

**File**: [ai_rfq_engine/mutations/discount_prompt.py](../ai_rfq_engine/mutations/discount_prompt.py)

#### `InsertUpdateDiscountPrompt`

Creates or updates a discount prompt. All `discount_rules` are validated before saving.

```graphql
mutation {
  insertUpdateDiscountPrompt(
    partitionKey: "tenant_001"
    discountPromptUuid: "dp_001"      # omit to auto-generate
    scope: "global"
    priority: 0
    discountPrompt: "Apply volume discount per discount_rules."
    discountRules: [
      { greaterThan: 0,    lessThan: 1000, maxDiscountPercentage: 5  }
      { greaterThan: 1000, lessThan: 5000, maxDiscountPercentage: 10 }
      { greaterThan: 5000,                 maxDiscountPercentage: 15 }
    ]
    conditions: []
    status: "active"
  ) {
    discountPrompt {
      discountPromptUuid
      scope
      priority
      discountRules {
        greaterThan
        lessThan
        maxDiscountPercentage
      }
      status
    }
  }
}
```

#### `DeleteDiscountPrompt`

```graphql
mutation {
  deleteDiscountPrompt(
    partitionKey: "tenant_001"
    discountPromptUuid: "dp_001"
  ) {
    discountPrompt {
      discountPromptUuid
    }
  }
}
```

### Queries

**File**: [ai_rfq_engine/queries/discount_prompt.py](../ai_rfq_engine/queries/discount_prompt.py)

#### List all discount prompts

```graphql
query {
  discountPromptList(
    partitionKey: "tenant_001"
    status: "active"
  ) {
    discountPromptUuid
    scope
    tags
    priority
    discountPrompt
    conditions
    discountRules {
      greaterThan
      lessThan
      maxDiscountPercentage
    }
    status
  }
}
```

#### Get specific prompt

```graphql
query {
  discountPrompt(
    partitionKey: "tenant_001"
    discountPromptUuid: "dp_001"
  ) {
    discountPromptUuid
    scope
    discountPrompt
    discountRules { greaterThan lessThan maxDiscountPercentage }
  }
}
```

---

## 10. Batch Loader Architecture

**File**: [ai_rfq_engine/models/batch_loaders/discount_prompt_by_scope_loaders.py](../ai_rfq_engine/models/batch_loaders/discount_prompt_by_scope_loaders.py)

The system uses the DataLoader pattern (via the `promise` library) to batch and cache DynamoDB reads within a single request. This eliminates N+1 query problems when loading prompts for multiple quote items.

### Four Loaders

| Loader Class | Batch Key | DynamoDB Query |
|---|---|---|
| `DiscountPromptGlobalLoader` | `partition_key` | `scope = "global" AND status = "active"` |
| `DiscountPromptBySegmentLoader` | `(partition_key, segment_uuid)` | `scope = "segment" AND tags.contains(segment_uuid)` |
| `DiscountPromptByItemLoader` | `(partition_key, item_uuid)` | `scope = "item" AND tags.contains(item_uuid)` |
| `DiscountPromptByProviderItemLoader` | `(partition_key, item_uuid, provider_item_uuid)` | `scope = "provider_item" AND tags.contains(provider_item_uuid)` |

### Loader Pattern

Each loader follows the same structure:

```python
class DiscountPromptBySegmentLoader(DataLoader):
    def batch_load_fn(self, keys):
        # keys: list of (partition_key, segment_uuid) tuples
        promises = []
        for (partition_key, segment_uuid) in keys:
            prompts = list(
                DiscountPromptModel.query(
                    partition_key,
                    filter_condition=(
                        (DiscountPromptModel.scope == "segment")
                        & (DiscountPromptModel.status == "active")
                        & DiscountPromptModel.tags.contains(segment_uuid)
                    )
                )
            )
            promises.append(Promise.resolve(prompts))
        return Promise.all(promises)
```

### Request-Scoped Caching

DataLoaders cache results for the lifetime of a single GraphQL request. Multiple resolvers requesting the same `(partition_key, segment_uuid)` key will only trigger one DynamoDB query.

---

## 11. End-to-End Data Flow

### Scenario: Quote with Discount Prompt Application

```
INPUT
└── GraphQL query: load quote "quote_001" with discount prompts
    └── Context: tenant_001, buyer: buyer@company.com
        Quote items:
          - qi_001: item_001 / pi_001 / qty=150 / subtotal=$7,500
          - qi_002: item_002 / pi_002 / qty=30  / subtotal=$900

STEP 1 — Segment Resolution
└── SegmentContactLoader.load(("tenant_001", "buyer@company.com"))
    └── Result: segment_uuid = "seg_vip_001"

STEP 2 — Parallel Prompt Loading
├── GLOBAL:         load("tenant_001")
│     Result: [dp_001 "Volume discount", dp_002 "Free shipping $5k+"]
├── SEGMENT:        load(("tenant_001", "seg_vip_001"))
│     Result: [dp_003 "VIP: 10% off"]
├── ITEM (item_001): load(("tenant_001", "item_001"))
│     Result: [dp_004 "Clearance: up to 20%"]
├── ITEM (item_002): load(("tenant_001", "item_002"))
│     Result: []
├── PI (pi_001):    load(("tenant_001", "item_001", "pi_001"))
│     Result: []
└── PI (pi_002):    load(("tenant_001", "item_002", "pi_002"))
      Result: [dp_005 "Special supplier pricing"]

STEP 3 — Deduplication Merge
└── seen = {}
    Add dp_001 ✓  Add dp_002 ✓  Add dp_003 ✓
    Add dp_004 ✓  Add dp_005 ✓
    Result: [dp_001, dp_002, dp_003, dp_004, dp_005]

STEP 4 — AI Processing
└── Claude receives: quote_items + discount_prompts
    AI evaluates each prompt against each quote item:
    ┌────────────────────────────────────────────────────────────┐
    │ qi_001 (subtotal $7,500):                                  │
    │   dp_001 → tier >$5000 → max 15% → $1,125 max             │
    │   dp_003 → VIP → 10% → $750                               │
    │   dp_004 → clearance on item_001 → max 20% → $1,500 max   │
    │   Priority: dp_004 (item-level, priority 20) wins          │
    │   Discount: $1,125 (15% of $7,500, capped at item max)     │
    │                                                            │
    │ qi_002 (subtotal $900):                                    │
    │   dp_001 → tier $0–$1000 → max 5% → $45 max               │
    │   dp_003 → VIP → 10% → $90                                 │
    │   dp_005 → supplier special on pi_002 → check rules        │
    │   Priority: dp_005 (provider_item-level, priority 30) wins │
    │   Discount: $90                                            │
    └────────────────────────────────────────────────────────────┘

STEP 5 — Discount Application
├── InsertUpdateQuoteItem(qi_001, subtotal_discount=1125)
│     final_subtotal = 7500 - 1125 = 6375
└── InsertUpdateQuoteItem(qi_002, subtotal_discount=90)
      final_subtotal = 900 - 90 = 810

STEP 6 — Quote Totals Recalculation
└── update_quote_totals("quote_001")
    total_quote_amount        = 7500 + 900 = 8400
    total_quote_discount      = 1125 + 90  = 1215
    items_final_total         = 6375 + 810 = 7185
    final_total_quote_amount  = 7185 + 200 (shipping) = 7385

OUTPUT
└── QuoteType
    ├── total_quote_amount:       8400.00
    ├── total_quote_discount:     1215.00
    └── final_total_quote_amount: 7385.00
```

---

## 12. Key Files Reference

| File | Purpose |
|---|---|
| [ai_rfq_engine/models/discount_prompt.py](../ai_rfq_engine/models/discount_prompt.py) | Core model, validation, CRUD functions |
| [ai_rfq_engine/models/utils.py](../ai_rfq_engine/models/utils.py) | `combine_all_discount_prompts()` — hierarchical assembly |
| [ai_rfq_engine/models/quote_item.py](../ai_rfq_engine/models/quote_item.py) | Discount fields, `final_subtotal` calculation |
| [ai_rfq_engine/models/quote.py](../ai_rfq_engine/models/quote.py) | `update_quote_totals()` — quote-level aggregation |
| [ai_rfq_engine/models/batch_loaders/discount_prompt_by_scope_loaders.py](../ai_rfq_engine/models/batch_loaders/discount_prompt_by_scope_loaders.py) | Four DataLoader classes for each scope |
| [ai_rfq_engine/types/discount_prompt.py](../ai_rfq_engine/types/discount_prompt.py) | GraphQL type definitions |
| [ai_rfq_engine/mutations/discount_prompt.py](../ai_rfq_engine/mutations/discount_prompt.py) | GraphQL mutations |
| [ai_rfq_engine/queries/discount_prompt.py](../ai_rfq_engine/queries/discount_prompt.py) | GraphQL queries |

### Key Functions

| Function | File | Description |
|---|---|---|
| `validate_and_normalize_discount_rules()` | `discount_prompt.py:37` | Validates and sorts discount tier rules |
| `get_global_discount_prompts()` | `discount_prompt.py:344` | Fetch GLOBAL scope prompts |
| `get_discount_prompts_by_segment()` | `discount_prompt.py:252` | Fetch SEGMENT scope prompts |
| `get_discount_prompts_by_item()` | `discount_prompt.py:282` | Fetch ITEM scope prompts |
| `get_discount_prompts_by_provider_item()` | `discount_prompt.py:312` | Fetch PROVIDER_ITEM scope prompts |
| `combine_all_discount_prompts()` | `utils.py:122` | Full hierarchical merge for a quote |
| `insert_update_discount_prompt()` | `discount_prompt.py:480` | Create/update with validation |
