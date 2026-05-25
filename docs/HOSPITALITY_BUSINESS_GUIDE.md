# Hospitality Business Guide

> **Audience**: Engineers, product, and integration partners learning how this RFQ engine serves hospitality workloads.
> **Scope**: Conceptual explanation of how hotels, restaurants, events, transfers, and itinerary packages map onto the existing RFQ core.
> **Companion docs**:
> - [HOSPITALITY_QUICK_START.md](HOSPITALITY_QUICK_START.md) — step-by-step setup recipe
> - [PRICING_CALCULATION.md](PRICING_CALCULATION.md) — field-level pricing reference
> - [HOSPITALITY_BUSINESS_GAP_PLAN.md](HOSPITALITY_BUSINESS_GAP_PLAN.md) — implementation status and remaining gaps

---

## 1. What This Engine Does For Hospitality

The AI RFQ engine quotes priceable line items against a request, accepting it into a quote with installments, and (for capacity-constrained products) reserves inventory before persisting the line. Hospitality products — hotel rooms, restaurant covers, event seats, transfers, activities, delegate fees — fit this shape when each component is **independently priceable** and **independently attributable to a supplier**.

The engine deliberately does **not** introduce a separate "hospitality engine." Every hospitality use case reuses the same core models (`Item`, `ProviderItem`, `ProviderItemBatch`, `Quote`, `QuoteItem`, `Installment`) with three behavioural extensions:

1. **Service windows** on `ProviderItemBatch` — turns generic inventory into dated capacity.
2. **Pricing modes** on `Item` — selects unit, per-pax-type, or occupancy calculation.
3. **Availability modes** on `ProviderItem` — controls whether the engine skips, checks, or durably reserves capacity.

Everything else (cancellation snapshots, FX, bundles, KGE catalog mapping) layers on top of those three extensions.

---

## 2. The Business Shapes This Engine Supports

| Hospitality product | How it maps |
|---|---|
| **Hotel room-night** | `Item.pricing_mode="occupancy"` + dated `ProviderItemBatch`; `qty` is room-nights, `pax_breakdown` describes guests |
| **Restaurant cover / event ticket / activity / transfer** | `pricing_mode="per_pax_type"` with `pax_breakdown`; `qty` equals total participants |
| **Add-on / unit good** | `pricing_mode="unit"` (or `null`); legacy procurement still works unchanged |
| **Multi-component itinerary or package** | Multiple `QuoteItem` records sharing a `bundle_uuid` and `bundle_label`; no parent reservation record |
| **Deposit and balance** | Two `Installment` rows on the quote (e.g. 30% / 70%) |
| **Supplier cancellation terms** | `CancellationPolicyModel` linked from `ProviderItemBatch`; engine writes a server-owned snapshot on the quote line |
| **Customer-facing currency** | `Quote.currency` (native) + `display_currency` + locked `fx_rate`; lines persist both `subtotal_native` and converted `subtotal` |
| **External catalog discovery** | `inquire_catalog` calls KGE, then `ItemCatalogRefModel.namespace_node_index` resolves search results to internal `Item`/`ProviderItem` |

Three deliberate non-features round out the picture:

- **No parent bundle row.** A package is a set of priced lines that share a `bundle_uuid`. There is no unpriced "reservation header" hiding component prices — each leg stays attributable to its provider.
- **No payment, refund, or document delivery.** The engine quotes and reserves; downstream systems capture funds, issue documents, and execute refunds.
- **No graph/catalog ownership.** The knowledge graph engine (KGE) owns catalog content; this engine maps KGE search results to its own priceable identifiers.

---

## 3. The Quote Lifecycle, End To End

A hospitality quote flows through five phases. Each phase has a clear owner and a clear failure mode.

### 3.1 Discovery (optional)

A customer-facing client searches KGE for offerings. This engine exposes `inquire_catalog` ([queries/catalog_inquiry.py](../ai_rfq_engine/queries/catalog_inquiry.py)) which invokes KGE's `search` operation. The client receives a list of `(namespace, node_id)` references and uses [ItemCatalogRefModel](../ai_rfq_engine/models/item_catalog_ref.py) to translate those into internal `item_uuid` / `provider_item_uuid` values that the engine can price.

Direct node-by-ID lookup against KGE is not yet exposed; only text/search inquiry is supported. The engine never holds KGE credentials, drivers, or connection state.

### 3.2 Request

A request is created with the customer's contact information and a free-form list of desired items. Hospitality-specific shaping (room-night service dates, occupancy mix, group size) is captured later on the quote line — the request itself remains intentionally generic.

### 3.3 Quote and Quote Items

A `Quote` is created against the request, optionally specifying:
- `currency` — supplier's native currency on lines (defaults from `ProviderItemBatch.currency` if unset).
- `display_currency` + `fx_rate` + `fx_rate_locked_at` — customer-facing currency and locked conversion rate.

Each `QuoteItem` ties to a specific `provider_item_uuid` (the supplier offering) and optionally pins a `batch_no` (specific dated inventory). On insert, `insert_update_quote_item` ([models/quote_item.py](../ai_rfq_engine/models/quote_item.py)) executes a fixed sequence:

1. **Validate inputs** and look up the `Item` to pick a pricing mode.
2. **Price the line** using the selected mode (see §4).
3. **Enforce availability** — call `_enforce_availability` to either skip, check, or acquire a durable hold (see §5).
4. **Build the cancellation snapshot** — if the selected batch links a policy, the engine writes a server-owned copy of the terms to `request_data.cancellation_policy_snapshot` (see §6).
5. **Apply FX** — convert `subtotal` from native into display currency when the quote carries a locked rate.
6. **Persist** — on save failure, any acquired hold is released atomically.

The flow short-circuits on the first failure. A failed availability check or pricing lookup raises before the QuoteItem is saved, leaving no orphan records.

### 3.4 Installments

A quote may carry any number of `Installment` rows for deposit/balance scheduling. Hospitality deals commonly use 30% deposit + 70% balance, but the model is generic. Installments are not coupled to the hold lifecycle — they describe an intended payment schedule, not actual payments.

### 3.5 Acceptance

When a `Quote` transitions to `accepted` status, `_confirm_quote_item_holds` ([models/quote.py:255](../ai_rfq_engine/models/quote.py#L255)) walks every quote item, finds any `hold_token` whose provider item is in `require_hold` mode, and dispatches `confirm_hold`. This transitions each `AvailabilityHoldModel` from `held` to `confirmed`. Capacity was already decremented at acquire time — confirmation does not decrement again.

After confirmation, capacity is reserved for the service window. Cancellation now becomes a refund workflow against the stored cancellation snapshot, not a hold release.

---

## 4. Pricing Modes Explained

The `Item.pricing_mode` field selects which calculator runs inside `insert_update_quote_item`. Detailed formulas live in [PRICING_CALCULATION.md §7a](PRICING_CALCULATION.md); the business-level intuition:

- **`unit` (or `null`)** — classical `price_per_uom × qty`. Used for unit-priced extras (parking, breakfast supplements) and legacy procurement.
- **`per_pax_type`** — sum of per-pax-type prices weighted by headcount. `qty` must equal the total of all `pax_breakdown` values. Used wherever each participant has a distinct price (event ticket, transfer seat, restaurant cover, delegate fee).
- **`occupancy`** — a base nightly rate covers a defined occupancy; each additional guest beyond the base adds a per-pax-type surcharge. Used for room-nights and similar accommodation products. `qty` is the **billable unit count** (room-nights), not guest count.

The same `pax_breakdown` map serves two purposes — explicit pricing input for `per_pax_type` mode, and over-base surcharge calculation for `occupancy` mode. Pricing decisions live entirely on `ItemPriceTier` rows; the quote item just carries the inputs.

---

## 5. Availability And Holds

`ProviderItem.availability_mode` is the single switch governing capacity enforcement.

| Mode | Behaviour at quote-line insert |
|---|---|
| `none` (default) | No availability work. Procurement and other non-reservable products. |
| `check_only` | Verify against local `ProviderItemBatch` that at least one matching batch is in stock and has sufficient `availability_qty`. No reservation is taken. |
| `require_hold` | Atomically decrement `availability_qty` on the matching batch and persist an `AvailabilityHoldModel` row with a 15-minute TTL. The hold token is stored on the quote item. |

`require_hold` is the only mode that touches durable state. Its design protects against three classic failure modes:

1. **Overbooking under concurrency** — the batch capacity decrement and the hold-record insert run inside a single PynamoDB `TransactWrite` with a conditional `availability_qty >= qty` check. Two competing acquires for the last unit cannot both succeed.
2. **Capacity leaks on save failure** — if `QuoteItem.save()` fails after a hold succeeds, the except branch dispatches `release_hold` to restore capacity.
3. **Stuck reservations from abandoned quotes** — the [expiry_scanner](../ai_rfq_engine/handlers/availability/expiry_scanner.py) finds `held` records past their `expires_at` and transitions them to `expired`, restoring capacity. Operations must schedule this scanner (Lambda + EventBridge, cron, etc.).

The hold record carries `quote_uuid`, `quote_item_uuid`, `qty`, `service_start_at`, `service_end_at`, `status`, and `expires_at` so capacity is fully auditable. Unknown tokens fail closed — release and confirm of a non-existent token both error rather than silently succeeding.

**Boundary**: if inventory is controlled by a PMS or GDS, the local `require_hold` path is **not** appropriate. The product must be wired to an authoritative external reservation service instead. The engine currently exposes only the local-batch path; external adapters are deliberately out of scope.

---

## 6. Cancellation Terms

A `ProviderItemBatch` may reference a `CancellationPolicyModel` via `cancellation_policy_uuid`. When a quote line pins a batch with a linked policy, the engine builds a snapshot of the policy and writes it to `QuoteItem.request_data.cancellation_policy_snapshot`. The snapshot contains:

- `policy_uuid`, `label`, `description`, `tiers`, `notes_template_uuid` — the terms as quoted.
- `snapshotted_at` — when the snapshot was generated.
- `content_hash` — SHA-256 (truncated to 16 hex chars) of the stable content, for audit/reconciliation.

The `cancellation_policy_snapshot` key inside `request_data` is **reserved**. Caller payloads that try to write or update it are rejected at the mutation boundary. The snapshot is immutable on the quote line — if a supplier later changes the policy master record, the customer still sees the terms they agreed to. Changing the selected batch or its policy requires a fresh requote, which produces a new snapshot.

Downstream cancellation processing must read the stored snapshot, not the live policy. That commitment is what gives the snapshot its commercial value — it is the document of record for the refund computation.

---

## 7. Currency: Native vs. Display

Hospitality often involves a supplier-currency price (the hotel quotes in EUR) and a customer-currency display (the guest pays in USD). The engine handles this as a **single conversion at quote time**, not as a runtime FX lookup.

On the quote, an operator records:
- `currency` — the supplier's native currency.
- `display_currency` — the customer-facing currency.
- `fx_rate` — a locked rate (display per 1 unit of native).
- `fx_rate_locked_at` — when the rate was locked.

When a quote item is created:
- `subtotal_native` stores the tier-derived amount in the supplier currency.
- `subtotal` stores the converted amount in the display currency.
- `final_subtotal` applies the discount in the display currency.

If currencies match (e.g. domestic procurement), no conversion runs and `subtotal == subtotal_native`. If `fx_rate` is unset, the engine refuses to silently default to 1.0 — same-currency quotes simply skip the conversion path.

FX **policy** (where rates come from, how stale a locked rate may be, how to reconcile against actual settlement) is a tenant-level decision and is intentionally not codified in this engine.

---

## 8. Worked Scenarios

### 8.1 Two-Night Hotel Stay, Two Adults

1. `Item.pricing_mode="occupancy"` for "Grand Hotel Standard Room".
2. `ProviderItemBatch` with `service_start_at=2026-06-01`, `service_end_at=2026-06-03`, `availability_qty=4` rooms, `cancellation_policy_uuid` linking a standard policy.
3. `ItemPriceTier` with `price_per_uom=200`, `base_occupancy={"adult": 2}`.
4. Customer creates `Quote` with `currency="EUR"`, `display_currency="USD"`, `fx_rate=1.08`.
5. `QuoteItem` with `qty=2` (room-nights), `pax_breakdown={"adult": 2}`:
   - Native subtotal: `200 × 2 = 400 EUR` (no over-base surcharge — adults match base).
   - Display subtotal: `400 × 1.08 = 432 USD`.
   - Hold record persisted with `qty=2` against the batch; `availability_qty` becomes `2`.
   - Cancellation snapshot written to `request_data.cancellation_policy_snapshot`.
6. Two `Installment` rows: 30% deposit + 70% balance, both in USD.
7. Quote accepted → `confirm_hold` transitions the reservation to `confirmed`.

### 8.2 Restaurant Group Booking, Mixed Pax Types

1. `Item.pricing_mode="per_pax_type"` for "Tasting Menu".
2. `ProviderItemBatch` with `service_start_at=2026-06-15T19:00`, `service_end_at=2026-06-15T22:00`, `availability_qty=12` covers.
3. `ItemPriceTier` rows for `pax_type="adult"` at `120` and `pax_type="child"` at `60`.
4. `QuoteItem` with `qty=4`, `pax_breakdown={"adult": 3, "child": 1}`:
   - `120 × 3 + 60 × 1 = 420`.
   - One reservation, four covers debited from `availability_qty`.

### 8.3 Multi-Leg Itinerary

A three-component package — airport transfer + hotel + activity — becomes three `QuoteItem` rows sharing a `bundle_uuid` and a human-readable `bundle_label`:

| Line | provider | mode | qty | pax_breakdown |
|---|---|---|---|---|
| Transfer | Driver Co | `per_pax_type` | 2 | `{"adult": 2}` |
| Hotel | Grand Hotel | `occupancy` | 3 | `{"adult": 2}` |
| Activity | Tour Op | `per_pax_type` | 2 | `{"adult": 2}` |

Listing quote items with a `bundle_uuid` filter returns the package together while each line keeps its own provider, currency, hold, and cancellation snapshot. There is no parent record to keep in sync.

---

## 9. What Is Deliberately Out Of Scope

| Concern | Owner |
|---|---|
| Payment authorization, capture, settlement | Downstream payment service |
| Refund execution against the cancellation snapshot | Downstream refund/cancellation service |
| Email, document generation, PDF delivery | Downstream document service |
| KGE graph schema, credentials, connection pooling | Knowledge Graph Engine |
| PMS / GDS / channel-manager synchronisation | External adapter (not yet implemented) |
| MCP / AI agent orchestration | Outside this repository |
| Persisted parent bundle line or nested package row | By design — `bundle_uuid` grouping replaces it |

---

## 10. Where To Look Next

| Question | Document |
|---|---|
| "How do I configure a service-dated product?" | [HOSPITALITY_QUICK_START.md](HOSPITALITY_QUICK_START.md) |
| "What exactly does occupancy pricing compute?" | [PRICING_CALCULATION.md §7a](PRICING_CALCULATION.md) |
| "What's still on the roadmap before production?" | [HOSPITALITY_BUSINESS_GAP_PLAN.md §7](HOSPITALITY_BUSINESS_GAP_PLAN.md) |
| "How does the hold transaction actually run?" | [handlers/availability/handler.py](../ai_rfq_engine/handlers/availability/handler.py) |
| "How does the quote-item insert orchestrate everything?" | [models/quote_item.py](../ai_rfq_engine/models/quote_item.py) |
