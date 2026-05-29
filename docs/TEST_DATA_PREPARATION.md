# Test Data Preparation Guide

> **Audience**: Engineers preparing seed data for local development, integration tests, or QA environments.
> **Authoritative seed script**: [ai_rfq_engine/tests/load_sample_data.py](../ai_rfq_engine/tests/load_sample_data.py) — drives the same GraphQL mutations described here and writes the resulting UUIDs into `tests/test_data.json` for pytest fixtures.
> **Companion docs**: [ER_DIAGRAM.md](ER_DIAGRAM.md) (schema reference) · [HOSPITALITY_BUSINESS_GUIDE.md](HOSPITALITY_BUSINESS_GUIDE.md) (how the model fits hospitality workloads).

All test data is written through the engine's GraphQL surface, not by directly inserting DynamoDB items. This keeps validation, computed columns (totals, `total_cost_per_uom`, FX conversion, cancellation snapshots), and cache-purge hooks consistent with production traffic.

---

## 1. Environment Setup

Before any mutation will succeed, you need a working tenant context.

### 1.1 `.env`

Copy `ai_rfq_engine/tests/.env.example` to `ai_rfq_engine/tests/.env` and fill in:

```ini
base_dir=/absolute/path/to/silvaengine
region_name=us-west-2
aws_access_key_id=<your-aws-access-key-id>
aws_secret_access_key=<your-aws-secret-access-key>
endpoint_id=<your-endpoint-id>
part_id=<your-part-id>
execute_mode=local_for_all
initialize_tables=0
cache_enabled=0
```

`part_id` becomes the tenant `partition_key` for every record. `endpoint_id` + `part_id` are required on every GraphQL call.

### 1.2 Tables

Set `initialize_tables=1` on the very first run if your AWS account has no `are-*` tables yet. Subsequent runs should leave it `0` to avoid re-creating tables.

### 1.3 Invocation Pattern

The committed seed script wraps every mutation through `engine.ai_rfq_graphql(...)`:

```python
from ai_rfq_engine import AIRFQEngine
from silvaengine_utility.serializer import Serializer

engine = AIRFQEngine(logger, **SETTING)

def run(query, variables):
    response = engine.ai_rfq_graphql(
        query=query, variables=variables,
        endpoint_id=SETTING["endpoint_id"],
        part_id=SETTING["part_id"],
    )
    parsed = Serializer.json_loads(response) if isinstance(response, (str, bytes)) else response
    if "body" in parsed and isinstance(parsed["body"], str):
        parsed = Serializer.json_loads(parsed["body"])
    if parsed.get("errors"):
        raise RuntimeError(parsed["errors"])
    return parsed.get("data", parsed)
```

Use this wrapper for every snippet below.

---

## 2. Dependency Order

Tables have **soft foreign keys** (UUID strings; DynamoDB does not enforce them). The application code does enforce ordering, so seed in this sequence:

```
                                 ┌──> SegmentContact
                                 │
1. Segment ──────────────────────┤
                                 │
2. Item ──┬──> ProviderItem ──┬──┴──> ItemPriceTier (needs Item + ProviderItem + Segment)
          │                   │
          │                   ├──> ProviderItemBatch ──> AvailabilityHold (runtime only)
          │                   │            │
          │                   │            └──> CancellationPolicy (link by uuid)
          │                   │
          │                   └──> ItemCatalogRef (optional KGE mapping)
          │
          └──> CancellationPolicy (optional supplier scoping)

3. CancellationPolicy   (independent; linked from ProviderItemBatch)
4. FxRate               (independent; locked rate copied onto Quote)
5. DiscountPrompt       (independent; scoped by tag)

6. Request
7. File (per request)

8. Quote ──> QuoteItem (needs ItemPriceTier ACTIVE in DynamoDB GSI; see §13.1)
         └──> Installment
```

Skipping ahead in the order causes either "not found" rejections (e.g. `ProviderItem` without an `Item`) or empty-result computations (e.g. a `QuoteItem` insert that finds no matching `ItemPriceTier`).

---

## 3. `are-segments` — Segments

A customer-segment label (retail, corporate, channel, loyalty). Drives which `ItemPriceTier` is picked.

| Argument | Required | Notes |
|---|---|---|
| `segmentName` | yes (effective) | Display label. |
| `segmentDescription` | no | Free text. |
| `providerCorpExternalId` | no | Defaults to a 20-X placeholder. |
| `updatedBy` | yes | Audit attribution. |
| `segmentUuid` | no | Provide to update an existing segment; omit on create. |

```graphql
mutation InsertUpdateSegment($name: String, $desc: String, $by: String!) {
  insertUpdateSegment(segmentName: $name, segmentDescription: $desc, updatedBy: $by) {
    segment { segmentUuid }
  }
}
```

**Capture**: `segmentUuid` — reused by `SegmentContact`, `ItemPriceTier`, and (via discount-prompt `tags`) `DiscountPrompt`.

---

## 4. `are-segment_contacts` — Segment Contacts

Email-keyed membership rows.

| Argument | Required | Notes |
|---|---|---|
| `segmentUuid` | yes | FK to `Segment`. |
| `email` | yes | Range key in the table — unique per tenant. |
| `contactUuid` | no | Optional external CRM identifier. |
| `consumerCorpExternalId` | no | Customer-corporation tag. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateSegmentContact($sid: String!, $email: String!, $cid: String, $by: String!) {
  insertUpdateSegmentContact(segmentUuid: $sid, email: $email,
                              consumerCorpExternalId: $cid, updatedBy: $by) {
    segmentContact { contactUuid }
  }
}
```

**Capture**: `email` — useful when seeding `Request` (the request's `email` should match a real contact for end-to-end test scenarios).

**Delete guard**: a `Segment` cannot be deleted while contacts still reference it.

---

## 5. `are-items` — Catalog Items

A priceable thing. Set `pricingMode` to match how downstream `QuoteItem` should compute totals.

| Argument | Required | Notes |
|---|---|---|
| `itemName` | yes (effective) |  |
| `itemType` | yes (effective) | Free-form category. Convention: `"product"` for procurement, `"room"` / `"seat"` / `"transfer"` for hospitality. |
| `uom` | yes (effective) | Unit of measure: `"each"`, `"night"`, `"seat"`, `"kg"`, … |
| `pricingMode` | no | One of `unit` / `per_pax_type` / `occupancy` / `null` (treated as `unit`). |
| `itemDescription` | no |  |
| `itemExternalId` | no | External SKU reference. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateItem(
  $type: String, $name: String, $desc: String, $mode: String, $uom: String, $by: String!
) {
  insertUpdateItem(itemType: $type, itemName: $name, itemDescription: $desc,
                   pricingMode: $mode, uom: $uom, updatedBy: $by) {
    item { itemUuid }
  }
}
```

**Hospitality variants**:
- Hotel room: `itemType="room"`, `pricingMode="occupancy"`, `uom="night"`.
- Event ticket / restaurant cover / transfer seat: `itemType="seat"`, `pricingMode="per_pax_type"`, `uom="seat"`.
- Procurement SKU / add-on: `itemType="product"`, `pricingMode=null`, `uom="each"`.

**Capture**: `itemUuid`.

---

## 6. `are-provider_items` — Provider Offerings

A supplier-specific offering of an `Item`. Two hotels selling the same room category produce two `ProviderItem` rows for one `Item`.

| Argument | Required | Notes |
|---|---|---|
| `itemUuid` | yes (effective) | FK to `Item`. |
| `basePricePerUom` | yes (effective) | Reference rate. `ItemPriceTier` overrides per segment/qty. |
| `providerCorpExternalId` | no | Supplier corp tag. Default `"XXXXXXXXXXXXXXXXXXXX"`. |
| `providerItemExternalId` | no | Supplier's SKU. |
| `availabilityMode` | no | One of `none` (default) / `check_only` / `require_hold`. **Required hospitality switch.** |
| `itemSpec` | no | JSON map of supplier-specific attributes (amenities, capacity, …). |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateProviderItem(
  $iid: String!, $price: Float, $mode: String, $extId: String, $by: String!
) {
  insertUpdateProviderItem(itemUuid: $iid, basePricePerUom: $price,
                           availabilityMode: $mode, providerCorpExternalId: $extId,
                           updatedBy: $by) {
    providerItem { providerItemUuid }
  }
}
```

**Capture**: `providerItemUuid`.

**Hospitality reminder**: for `require_hold` to actually reserve capacity, the linked `ProviderItemBatch` must populate `availabilityQty` (see §7).

---

## 7. `are-provider_item_batches` — Inventory Batches

A specific lot. For procurement: physical batch + cost basis. For hospitality: a dated room block, ticket allotment, or event session.

| Argument | Required | Notes |
|---|---|---|
| `providerItemUuid` | yes | FK to `ProviderItem` (hash key). |
| `batchNo` | yes | Human-meaningful lot identifier (e.g. `"B-12345"`, `"HOTEL-20260601"`). |
| `itemUuid` | yes (effective) | Denormalized FK to `Item`. |
| `producedAt`, `expiredAt` | yes (effective) | Inventory lifecycle datetimes. |
| `serviceStartAt`, `serviceEndAt` | no | **Service window** for hospitality. Set both for dated inventory; leave `null` for procurement. |
| `costPerUom` | yes (effective) | Base cost. |
| `freightCostPerUom`, `additionalCostPerUom` | yes (effective) | Cost breakdown — engine computes `totalCostPerUom = cost + freight + additional`. |
| `guardrailMarginPerUom` | no | Minimum margin percentage; engine computes `guardrailPricePerUom`. |
| `slowMoveItem` | no | Boolean flag. |
| `inStock` | no | Defaults to `true`. |
| `availabilityQty` | no | **Hospitality**: bookable units. `null` = unquantified (`require_hold` will reject). |
| `currency` | no | Native currency for cost figures. |
| `cancellationPolicyUuid` | no | Link a `CancellationPolicy` so quoted lines get a snapshot. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateProviderItemBatch(
  $pid: String!, $iid: String!, $bno: String!,
  $prod: DateTime, $exp: DateTime,
  $start: DateTime, $end: DateTime,
  $cost: Float, $freight: Float, $addl: Float,
  $qty: Float, $cur: String, $polUuid: String, $by: String!
) {
  insertUpdateProviderItemBatch(
    providerItemUuid: $pid, itemUuid: $iid, batchNo: $bno,
    producedAt: $prod, expiredAt: $exp,
    serviceStartAt: $start, serviceEndAt: $end,
    costPerUom: $cost, freightCostPerUom: $freight, additionalCostPerUom: $addl,
    availabilityQty: $qty, inStock: true,
    currency: $cur, cancellationPolicyUuid: $polUuid,
    updatedBy: $by
  ) {
    providerItemBatch { batchNo availabilityQty totalCostPerUom }
  }
}
```

**Capture**: `(providerItemUuid, batchNo)` together — the composite PK.

**Validation rule**: when `serviceStartAt` and `serviceEndAt` are both set, `serviceEndAt > serviceStartAt`. Provide both or neither; partial windows are rejected.

---

## 8. `are-item_price_tiers` — Price Tiers

Quantity- and segment-banded price. The active tier whose `[quantity_greater_then, quantity_less_then)` bracket contains the requested `qty` provides `price_per_uom`.

| Argument | Required | Notes |
|---|---|---|
| `itemUuid` | yes | FK to `Item` (hash key). |
| `providerItemUuid` | yes (effective) | FK to `ProviderItem`. |
| `segmentUuid` | yes (effective) | FK to `Segment`. |
| `quantityGreaterThen` | yes (effective) | Inclusive lower bound. First tier should be `0`. |
| `pricePerUom` | yes (effective) | Sell price. (Or `marginPerUom`.) |
| `marginPerUom` | no | Alternative to `pricePerUom`. |
| `paxType` | no | When set, this tier prices a specific PAX category (`adult`, `child`, …). Required for `per_pax_type` mode. |
| `currency` | no |  |
| `baseOccupancy` | no | **Hospitality occupancy mode**: included guests, e.g. `{"adult": 2}`. |
| `extraPaxSurcharges` | no | **Hospitality occupancy mode**: per-extra-pax surcharge, e.g. `{"adult": 50, "child": 25}`. |
| `status` | no | Default `in_review`; **must be `active`** to participate in pricing. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateItemPriceTier(
  $iid: String!, $pid: String, $sid: String,
  $qty: Float, $price: Float, $pax: String,
  $base: JSONCamelCase, $extra: JSONCamelCase,
  $stat: String, $by: String!
) {
  insertUpdateItemPriceTier(
    itemUuid: $iid, providerItemUuid: $pid, segmentUuid: $sid,
    quantityGreaterThen: $qty, pricePerUom: $price, paxType: $pax,
    baseOccupancy: $base, extraPaxSurcharges: $extra,
    status: $stat, updatedBy: $by
  ) {
    itemPriceTier { itemPriceTierUuid }
  }
}
```

**Tier configurations by pricing mode**:

- **`unit`**: one tier per quantity bracket, no `paxType`, no occupancy maps.
- **`per_pax_type`**: one tier *per pax category* (e.g. one `adult` tier, one `child` tier). `qty` on the quote line must equal the sum of `pax_breakdown`.
- **`occupancy`**: a single base tier (no `paxType`) with `baseOccupancy` and `extraPaxSurcharges` maps. Surcharges run per-pax-type for guests beyond the base.

**Capture**: `itemPriceTierUuid`.

**Gotcha**: Price tiers are queried at quote-item time via a DynamoDB GSI. After creating tiers, **wait 60–120 seconds** before seeding `QuoteItem` rows — see §13.1.

---

## 9. `are-cancellation_policies` — Cancellation Policies

Reusable refund-tier definitions. Linked from `ProviderItemBatch` so that quote lines pinned to that batch get an **engine-owned** snapshot at quote time.

| Argument | Required | Notes |
|---|---|---|
| `label` | no | Display name. |
| `description` | no |  |
| `tiers` | no | Tier definition map, e.g. `{"tiers": [{"days_before_service_gte": 14, "refund_pct": 1.0}, {"days_before_service_gte": 7, "refund_pct": 0.5}]}`. |
| `providerItemUuid` | no | Optional scoping to a supplier. |
| `notesTemplateUuid` | no | Pointer to external notes template. |
| `status` | no | Default `active`. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateCancellationPolicy(
  $label: String, $desc: String, $tiers: JSONCamelCase,
  $provider: String, $by: String!
) {
  insertUpdateCancellationPolicy(
    label: $label, description: $desc, tiers: $tiers,
    providerItemUuid: $provider, updatedBy: $by
  ) {
    cancellationPolicy { policyUuid }
  }
}
```

**Capture**: `policyUuid` — pass to `ProviderItemBatch.cancellationPolicyUuid`.

---

## 10. `are-fx_rates` — FX Rates

Tenant-managed conversion rates. The engine does **not** look up `FxRate` at quote-item save — the `Quote` carries a locked numeric `fxRate`. This table exists for rate-management UX, audit, and operator reference.

| Argument | Required | Notes |
|---|---|---|
| `sourceCurrency`, `targetCurrency` | yes (effective) | ISO codes. |
| `rate` | yes (effective) | Target units per 1 source unit. |
| `currencyPairDate` | no | Composite key for the LSI (e.g. `"USD#EUR#2026-05-25"`). |
| `rateDate` | no | When the rate is valid. |
| `provider`, `notes` | no |  |
| `status` | no | Default `active`. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateFxRate(
  $src: String, $tgt: String, $rate: Float, $pair: String,
  $date: DateTime, $prov: String, $by: String!
) {
  insertUpdateFxRate(
    sourceCurrency: $src, targetCurrency: $tgt, rate: $rate,
    currencyPairDate: $pair, rateDate: $date, provider: $prov,
    updatedBy: $by
  ) {
    fxRate { fxRateUuid }
  }
}
```

---

## 11. `are-item_catalog_refs` — Catalog Mapping

Maps external catalog references (typically from KGE search) to internal `Item` / `ProviderItem` records.

| Argument | Required | Notes |
|---|---|---|
| `namespace` | no | Defaults to `"DEFAULT"`. |
| `nodeId` | yes (effective) | External identifier. |
| `itemUuid` | yes (effective) | FK to `Item`. |
| `providerItemUuid` | no | FK to `ProviderItem` (supplier-specific mapping). |
| `extra` | no | Free-form passthrough map. |
| `status` | no | Default `active`. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateItemCatalogRef(
  $ns: String, $node: String, $iid: String, $pid: String,
  $extra: JSONCamelCase, $by: String!
) {
  insertUpdateItemCatalogRef(
    namespace: $ns, nodeId: $node, itemUuid: $iid,
    providerItemUuid: $pid, extra: $extra, updatedBy: $by
  ) {
    itemCatalogRef { catalogRefUuid }
  }
}
```

---

## 12. `are-discount_prompts` — Discount Rules

| Argument | Required | Notes |
|---|---|---|
| `scope` | yes (effective) | One of `global` / `segment` / `item` / `provider_item`. |
| `tags` | yes (effective) | List of identifiers the scope applies to (e.g. `[segmentUuid]`). |
| `discountPrompt` | yes (effective) | Natural-language prompt explaining the rule. |
| `conditions` | no | List of predicate strings. |
| `discountRules` | no | Tier ladder of `{greaterThan, lessThan, maxDiscountPercentage}` maps. Validated to be contiguous, monotonically increasing in discount. |
| `priority` | no | Lower wins on tie. |
| `status` | no | Default `in_review`; set `active` to participate. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateDiscountPrompt(
  $scope: String, $tags: [String], $prompt: String,
  $rules: [JSONCamelCase], $stat: String, $by: String!
) {
  insertUpdateDiscountPrompt(
    scope: $scope, tags: $tags, discountPrompt: $prompt,
    discountRules: $rules, status: $stat, updatedBy: $by
  ) {
    discountPrompt { discountPromptUuid }
  }
}
```

See [DISCOUNT_PROMOTION_PROMPT.md](DISCOUNT_PROMOTION_PROMPT.md) for the prompt-authoring contract.

---

## 13. `are-requests` — Requests

An incoming customer inquiry.

| Argument | Required | Notes |
|---|---|---|
| `email` | yes (effective) | Customer email. |
| `requestTitle` | yes (effective) |  |
| `requestDescription` | no |  |
| `items` | no | List of `{item_uuid, quantity, provider_items?}` maps. Free-form — not a strict FK. |
| `billingAddress`, `shippingAddress` | no | Address blobs (`street`, `city`, `state`, `postal_code`, `country`). |
| `notes` | no |  |
| `status` | no | Default `initial`. |
| `expiredAt` | no | Optional expiry. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateRequest(
  $email: String!, $title: String!, $desc: String,
  $billing: JSONCamelCase, $shipping: JSONCamelCase,
  $items: [JSONCamelCase], $expired: DateTime, $by: String!
) {
  insertUpdateRequest(
    email: $email, requestTitle: $title, requestDescription: $desc,
    billingAddress: $billing, shippingAddress: $shipping,
    items: $items, expiredAt: $expired, updatedBy: $by
  ) {
    request { requestUuid }
  }
}
```

**Capture**: `requestUuid` — used by `Quote`, `QuoteItem`, `Installment`, `File`.

---

## 14. `are-files` — Request Attachments (metadata only)

| Argument | Required | Notes |
|---|---|---|
| `requestUuid` | yes | FK. |
| `fileName` | yes | Range key. |
| `email` | no | Uploader contact. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateFile($rid: String!, $name: String!, $email: String, $by: String!) {
  insertUpdateFile(requestUuid: $rid, fileName: $name, email: $email, updatedBy: $by) {
    file { fileName }
  }
}
```

The engine stores only filename metadata; file content delivery is downstream.

---

## 15. `are-quotes` — Quotes

A supplier-specific quote answering a request.

| Argument | Required | Notes |
|---|---|---|
| `requestUuid` | yes | FK to `Request`. |
| `providerCorpExternalId` | no | Quoting supplier. |
| `salesRepEmail` | no |  |
| `shippingMethod`, `shippingAmount` | no | Optional shipping line. |
| `currency` | no | **Native** supplier currency. |
| `displayCurrency` | no | **Customer-facing** currency. |
| `fxRate` | no | Locked rate (display per 1 native unit). |
| `fxRateLockedAt` | no | When the rate was locked. |
| `notes` | no |  |
| `status` | no | Default `initial`. Transition to `accepted` triggers `confirmHold` on every held quote item. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateQuote(
  $rid: String!, $prov: String, $sales: String,
  $cur: String, $disp: String, $fx: Float, $fxAt: DateTime,
  $stat: String, $by: String!
) {
  insertUpdateQuote(
    requestUuid: $rid, providerCorpExternalId: $prov, salesRepEmail: $sales,
    currency: $cur, displayCurrency: $disp, fxRate: $fx, fxRateLockedAt: $fxAt,
    status: $stat, updatedBy: $by
  ) {
    quote { quoteUuid }
  }
}
```

**Capture**: `(requestUuid, quoteUuid)` together — the composite PK.

---

## 16. `are-quote_items` — Quote Lines

The heart of the engine. Insert triggers tier pricing, availability enforcement, FX conversion, and (when applicable) hold acquisition + cancellation snapshot generation.

| Argument | Required | Notes |
|---|---|---|
| `quoteUuid` | yes | FK to `Quote`. |
| `requestUuid` | yes (effective) | Needed to update quote totals. |
| `itemUuid` | yes (effective) | FK to `Item`. |
| `providerItemUuid` | yes (effective) | FK to `ProviderItem`. |
| `segmentUuid` | yes (effective) | Tier selection driver. |
| `qty` | yes (effective) | Billable unit count. For `per_pax_type`, must equal total of `paxBreakdown`. For `occupancy`, this is room-nights. |
| `batchNo` | no | Pin a specific `ProviderItemBatch`. Required for hospitality date-driven pricing. |
| `paxBreakdown` | no | Required for `per_pax_type` and `occupancy` modes. E.g. `{"adult": 2, "child": 1}`. |
| `bundleUuid`, `bundleLabel` | no | Itinerary grouping. |
| `serviceStartAt`, `serviceEndAt` | no | Service window. Auto-filled from the pinned batch when `batchNo` is set. |
| `subtotalDiscount` | no | Display-currency discount. |
| `currency`, `subtotalNative` | no | Set by the engine during FX conversion. Don't pre-populate. |
| `notes` | no |  |
| `requestData` | no | Free-form. **Reserved key**: `cancellationPolicySnapshot` is engine-owned — including it is rejected. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateQuoteItem(
  $qid: String!, $rid: String, $iid: String, $pid: String, $sid: String,
  $bno: String, $qty: Float, $pax: JSONCamelCase,
  $start: DateTime, $end: DateTime,
  $bundle: String, $label: String, $by: String!
) {
  insertUpdateQuoteItem(
    quoteUuid: $qid, requestUuid: $rid, itemUuid: $iid,
    providerItemUuid: $pid, segmentUuid: $sid, batchNo: $bno,
    qty: $qty, paxBreakdown: $pax,
    serviceStartAt: $start, serviceEndAt: $end,
    bundleUuid: $bundle, bundleLabel: $label,
    updatedBy: $by
  ) {
    quoteItem {
      quoteItemUuid pricePerUom qty
      subtotal subtotalNative finalSubtotal
      holdToken holdExpiresAt
    }
  }
}
```

### 16.1 DynamoDB Eventual Consistency

`QuoteItem` insert queries `ItemPriceTier` rows via a GSI. GSIs propagate asynchronously and **cannot use consistent reads**. After seeding tiers, wait before inserting quote items:

```python
import time
time.sleep(90)  # tiers usually propagate within 60–120s
```

The committed `load_sample_data.py` defaults `create_quote_items = False` and recommends a two-pass run: first pass seeds everything except quote items, second pass (after the GSI catches up) creates them.

### 16.2 Update Rule

After insert, `qty`, `batchNo`, and `paxBreakdown` **cannot be changed**. Allowed updates: `notes`, `bundleUuid`, `bundleLabel`, `currency`, `subtotalDiscount`, `subtotalNative`. To reprice, delete and re-insert.

---

## 17. `are-installments` — Payment Schedule

| Argument | Required | Notes |
|---|---|---|
| `quoteUuid` | yes | FK. |
| `requestUuid` | no | Denormalized. |
| `priority` | no | Order in schedule (1, 2, …). |
| `installmentAmount` | no | Explicit amount. |
| `installmentRatio` | no | Alternative — fraction of total. |
| `paymentMethod` | no | `credit_card`, `wire_transfer`, etc. |
| `scheduledDate` | no | Due date. |
| `status` | no | Default `pending`. |
| `salesorderNo` | no | Optional sales-order reference. |
| `updatedBy` | yes |  |

```graphql
mutation InsertUpdateInstallment(
  $qid: String!, $rid: String, $priority: Int,
  $amount: SafeFloat, $method: String, $sched: DateTime, $by: String!
) {
  insertUpdateInstallment(
    quoteUuid: $qid, requestUuid: $rid, priority: $priority,
    installmentAmount: $amount, paymentMethod: $method,
    scheduledDate: $sched, updatedBy: $by
  ) {
    installment { installmentUuid }
  }
}
```

**Delete guard**: a `QuoteItem` cannot be deleted while installments exist on its parent quote.

---

## 18. `are-availability_holds` — Holds (runtime only)

**Not seeded directly.** The engine creates a hold row atomically when:
- A `QuoteItem` is inserted whose `ProviderItem.availabilityMode == "require_hold"`.
- The pinned batch has quantified `availabilityQty >= qty`.

What you can do for tests:

| Operation | Mutation |
|---|---|
| Inspect | `acquireAvailabilityHold` returns `availability { available holdToken expiresAt }` |
| Confirm (idempotent) | `confirmAvailabilityHold(providerItemUuid, batchNo, holdToken)` |
| Release (idempotent) | `releaseAvailabilityHold(providerItemUuid, batchNo, holdToken)` |
| Force-expire stale holds | `expireAvailabilityHold(...)` — only after `expiresAt` has passed |

See [HOSPITALITY_BUSINESS_GUIDE.md §5](HOSPITALITY_BUSINESS_GUIDE.md) for the lifecycle and [tests/test_availability_contention.py](../ai_rfq_engine/tests/test_availability_contention.py) for integration-test patterns.

---

## 19. Worked Seed Recipes

### 19.1 Minimal Procurement Quote

A single-tenant, single-quote, single-line scenario that exercises the original procurement path.

```text
1. InsertUpdateSegment       → segmentUuid
2. InsertUpdateItem          → itemUuid (pricingMode=null, uom="each")
3. InsertUpdateProviderItem  → providerItemUuid (availabilityMode="none")
4. InsertUpdateProviderItemBatch → batchNo (no service window, costs set)
5. InsertUpdateItemPriceTier → status="active", quantityGreaterThen=0, pricePerUom set
6. (wait 60–120s for GSI propagation)
7. InsertUpdateRequest       → requestUuid
8. InsertUpdateQuote         → quoteUuid
9. InsertUpdateQuoteItem     → quoteItemUuid (qty>0, no pax/batch)
10. InsertUpdateInstallment  → 2 rows (priority 1, 2)
```

### 19.2 Hotel Room-Night with Hold

Drives every hospitality feature: occupancy pricing, service-dated batch, durable hold, cancellation snapshot, FX conversion.

```text
1.  InsertUpdateSegment            → segmentUuid
2.  InsertUpdateSegmentContact     → links guest email to segment
3.  InsertUpdateItem               → itemUuid (pricingMode="occupancy", uom="night")
4.  InsertUpdateProviderItem       → providerItemUuid (availabilityMode="require_hold")
5.  InsertUpdateCancellationPolicy → policyUuid
6.  InsertUpdateProviderItemBatch  → batchNo with serviceStartAt/serviceEndAt,
                                        availabilityQty=N, cancellationPolicyUuid
7.  InsertUpdateItemPriceTier      → active base tier with baseOccupancy={"adult":2},
                                        extraPaxSurcharges={"adult":50,"child":25}
8.  InsertUpdateFxRate (optional)  → operator-visible reference rate
9.  (wait 60–120s)
10. InsertUpdateRequest            → requestUuid
11. InsertUpdateQuote              → quoteUuid with currency, displayCurrency, fxRate
12. InsertUpdateQuoteItem          → qty=room-nights, paxBreakdown, batchNo
                                       → engine acquires hold, snapshots policy, applies FX
13. InsertUpdateInstallment        → 30% deposit + 70% balance
14. (test) InsertUpdateQuote status="accepted" → engine confirms held items
```

### 19.3 Multi-Leg Itinerary Bundle

Three lines on one quote sharing `bundleUuid` and `bundleLabel`:

```text
… seed prerequisites for transfer, hotel, activity items …

InsertUpdateQuoteItem (transfer)  bundleUuid="trip-1" bundleLabel="Honeymoon Package"
InsertUpdateQuoteItem (hotel)     bundleUuid="trip-1" bundleLabel="Honeymoon Package"
InsertUpdateQuoteItem (activity)  bundleUuid="trip-1" bundleLabel="Honeymoon Package"
```

Listing quote items with `bundleUuid` filter returns them as a group.

---

## 20. Planned: KGE Catalog Ingestion (`prepare_flight_catalog_refs.py`)

> **Status**: Plan, not yet implemented. Captured here for review before code lands.
> **Goal**: ingest the products generated by `prepare_flight_products.py` into the knowledge graph (`knowledge_graph_engine`) and write `ItemCatalogRef` rows so `inquire_catalog` can resolve KGE search hits back to internal `Item` / `ProviderItem` records.

### 20.1 Inputs

`tests/prepare_test_data/flight_products.json` (already produced by `prepare_flight_products.py`). No new generation — the script reads what's on disk:

```json
{
  "segmentUuid": "…",
  "cancellation_policies": [...],
  "items": [{"itemUuid": "...", "itemName": "Flight JFK->LAX Business",
             "itemExternalId": "FLIGHT-JFK-LAX-BUS", "pricingMode": "per_pax_type", ...}],
  "provider_items": [{"providerItemUuid": "...", "itemUuid": "...",
                      "itemSpec": {"airline_code": "AA", "cabin_class": "Business", ...}}],
  "provider_item_batches": [...],
  "item_price_tiers": [...]
}
```

### 20.2 KGE surface

From `knowledge_graph_engine/mutations/` and `queries/`:

| Operation | Purpose |
|---|---|
| `insertUpdateGraphSchema(...)` (mutation) | Seed entity/relationship types — `Flight`, `Airline`, `Airport`, `CabinClass`, `CancellationPolicy` + edges `OPERATED_BY`, `DEPARTS_FROM`, `ARRIVES_AT`, `IN_CABIN`, `HAS_POLICY`. Optional but recommended for label stability. |
| `executeExtract(text, documentSource, documentExternalId)` (mutation) | Runs `neo4j-graphrag-python` `SimpleKGPipeline` to extract entities + relationships from `text` into Neo4j, and persists a `kge-documents` row. |
| `search(queryText, …)` (query) | Same call `_search_inquiry` in [handlers/catalog/handler.py](../ai_rfq_engine/handlers/catalog/handler.py) already uses — verification only. |

Invocation uses the same `aws_lambda_invoker` path the catalog handler already wires (no new transport).

### 20.3 Flow

```
flight_products.json
  → load + bundle each item with its provider, batches, tiers, policy
  → (optional) insertUpdateGraphSchema with seed flight ontology
  → for each item bundle:
      a. compose natural-language description
      b. executeExtract(text=description,
                        documentSource="ai_rfq_seed",
                        documentExternalId=item.itemExternalId)
         → Neo4j nodes/edges + kge-documents row
      c. insertUpdateItemCatalogRef(
             namespace="FLIGHTS",
             nodeId=item.itemExternalId,
             itemUuid=item.itemUuid,
             providerItemUuid=...,
             extra={"documentUuid": ..., "airline_code": ..., "cabin_class": ...})
  → (optional) verification: search("Business class to LAX") and assert the
    item surfaces via its ItemCatalogRef
  → write flight_catalog_refs.json (gitignored)
```

### 20.4 Design decisions

| Decision | Choice | Why |
|---|---|---|
| `node_id` value | `itemExternalId` (e.g. `FLIGHT-JFK-LAX-BUS`) passed as `documentExternalId` to KGE | Stable, semantic, survives re-extraction. Neo4j internal IDs are not stable. |
| Granularity | One `executeExtract` per `Item`; one `ItemCatalogRef` per `(item, provider_item)` pair | An item is what the customer searches for; a row per provider so a hit resolves to a priced offering. |
| Schema seeding | Pre-seed via `insertUpdateGraphSchema` | KGE evolves the schema automatically, but first extractions produce inconsistent LLM-picked labels. |
| Namespace | `"FLIGHTS"` (override default `"DEFAULT"`) | Lets future hotel/event seed scripts use their own namespace without collision. |
| Text format | Plain English prose composed from bundle fields | LLM extraction prefers prose over JSON. |

### 20.5 Configuration

```bash
SEED_CATALOG_NAMESPACE=FLIGHTS              # ItemCatalogRef namespace
SEED_CATALOG_ENSURE_SCHEMA=1                # 1 = run insertUpdateGraphSchema
SEED_CATALOG_INPUT=flight_products.json     # source JSON path
```

Output: `tests/prepare_test_data/flight_catalog_refs.json` (gitignored).

### 20.6 Prerequisites

- A Neo4j instance registered for the tenant via `insertUpdateNeo4jInstance` (one-time tenant setup; out of scope for this script).
- `flight_products.json` present on disk.
- KGE deployed and reachable through `aws_lambda_invoker` in the engine context.

### 20.7 Open questions to resolve before implementing

1. **Segment in extracted text?** Include "available to {segment_name} tier customers" in the prose, or keep segment scoping purely RFQ-side?
2. **`ItemCatalogRef` per provider, or one per item with `provider_item_uuid` null?** Recommendation: per provider.
3. **Schema seed: aggressive or conservative?** Aggressive = all entity types + relationships up front; conservative = only `Flight`, let KGE evolve.
4. **Idempotency on re-run.** Skip extract when a `Document` with the same `documentExternalId` already exists, or accept duplicates? Pre-check would use KGE's `documentList` query.
5. **Verification scope.** Run a final `search` round-trip and assert discoverability, or write and exit?

### 20.8 Testing approach

| Layer | Method |
|---|---|
| Unit | Mock `engine.ai_rfq_graphql`; assert the expected `executeExtract` + `insertUpdateItemCatalogRef` payloads. Validates text composition and field mapping. |
| Integration | Run end-to-end against a Neo4j-enabled tenant; issue `search(queryText="business class JFK")` and assert at least one hit whose `documentExternalId` matches a row in `are-item_catalog_refs`. |

---

## 21. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `No price tier found for item_uuid=…, qty=…, segment_uuid=…` on `QuoteItem` insert | Tier `status` is not `active`, the quantity bracket misses, or DynamoDB GSI hasn't propagated yet — wait 60–120 s. |
| `service_start_at and service_end_at are required for availability checks` | `availabilityMode != "none"` but the request didn't supply a service window and no `batchNo` was pinned. |
| `require_hold requires a quantified availability_qty` | The selected batch's `availabilityQty` is `null`. Set it on the batch or use `availabilityMode="check_only"`. |
| `Requested provider item is not available for the service window` | No matching batch overlaps the requested window, all matching batches are `inStock=false`, or `availabilityQty < qty`. |
| `request_data.cancellation_policy_snapshot is engine-owned` | Caller included the reserved key in `requestData`. Remove it — the engine generates it from the linked policy. |
| `Cannot find the segment with …` on delete | Soft-FK guard: a `Segment` cannot be deleted while contacts reference it; same pattern for `QuoteItem` ↔ `Installment`. |
| Mutations return `errors` referencing `partition_key` | Missing `endpoint_id` / `part_id` in the GraphQL call context, or `.env` not loaded. |

---

## 22. Where To Look Next

| Question | Pointer |
|---|---|
| "What columns does each table actually have?" | [ER_DIAGRAM.md](ER_DIAGRAM.md) |
| "How do these mutations turn into reservations and pricing?" | [HOSPITALITY_BUSINESS_GUIDE.md](HOSPITALITY_BUSINESS_GUIDE.md), [PRICING_CALCULATION.md](PRICING_CALCULATION.md) |
| "Working end-to-end seed script" | [tests/load_sample_data.py](../ai_rfq_engine/tests/load_sample_data.py) |
| "Pytest fixtures consuming the seed JSON" | [tests/conftest.py](../ai_rfq_engine/tests/conftest.py), [tests/test_data.json](../ai_rfq_engine/tests/test_data.json) |
| "Integration patterns for holds" | [tests/test_availability_contention.py](../ai_rfq_engine/tests/test_availability_contention.py) |
