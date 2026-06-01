# AI RFQ Engine — Hospitality Business Gap Plan

> **Status**: Core gap closure implemented; DynamoDB-backed production validation remains open; expiry scanner, handler telemetry, and snapshot content hash added
> **Reviewed**: 2026-05-24 (updated after durable holds and engine-owned cancellation snapshots were implemented; expiry scanner, telemetry, and content hash added)
> **Baseline**: `feature/add-hospitality-business-support` working tree and focused hospitality tests
>
> **Related documents**: [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), [PRICING_CALCULATION.md](PRICING_CALCULATION.md), [HOSPITALITY_QUICK_START.md](HOSPITALITY_QUICK_START.md), [DISCOUNT_PROMOTION_PROMPT.md](DISCOUNT_PROMOTION_PROMPT.md)

## 1. Executive Summary

Most hospitality domain-model and quote-calculation gaps are implemented. The engine now extends its existing RFQ core to support:

- **Service-dated inventory** via `ProviderItemBatch.service_start_at` / `service_end_at`.
- **Guest/participant and occupancy pricing** via `Item.pricing_mode` (`per_pax_type`, `occupancy`).
- **Reusable package templates** via `BundleModel` / `BundleComponentModel`.
- **Grouped priced itinerary components** via `Request.bundle_uuid` and `QuoteItem.bundle_uuid` / `bundle_label` / `bundle_component_uuid`.
- **Quote-level currency conversion** via `FxRateModel` and locked FX rates.
- **Quoted cancellation terms** via `CancellationPolicyModel` with engine-owned quote-line snapshots.
- **Durable availability holds** via `AvailabilityHoldModel` and transactional `ProviderItemBatch.availability_qty` reservation/restoration.

The two identified integrity gaps are now addressed in code. `require_hold` persists tenant-scoped hold records and uses conditional transactional capacity changes; confirmation, release, and explicit expiry are state-aware and idempotent. `request_data.cancellation_policy_snapshot` is now reserved for server-generated terms and cannot be supplied or changed by a caller.

Production readiness still requires DynamoDB-backed contention/lifecycle execution and an operational trigger that invokes expiry processing for abandoned held records. Catalog discovery remains KGE-owned.

---

## 2. Supported Business Shape

The implemented design covers hospitality products expressible as independently priced quote items:

| Use case | Representation |
|---|---|
| Hotel room-night | `Item.pricing_mode="occupancy"` + service-dated `ProviderItemBatch` |
| Ticket, transfer, activity, delegate fee | `pricing_mode="per_pax_type"` with `pax_breakdown` |
| Unit-priced add-on or legacy procurement item | `pricing_mode="unit"` or `null` |
| Reusable itinerary or package | `BundleModel` with `BundleComponentModel` rows for default components |
| Quoted package execution | Multiple independently priced `QuoteItem` records sharing `bundle_uuid` and optionally referencing `bundle_component_uuid` |
| Deposit and balance | Existing `Installment` records on the quote |
| Supplier cancellation terms | `CancellationPolicyModel` referenced from a batch; engine-owned snapshot on the quote line |
| Display currency conversion | Line subtotal in native currency; display conversion when the quote carries a locked FX rate |
| KGE-discovered product | KGE search response resolved to internal `Item`/`ProviderItem` via `ItemCatalogRefModel` namespace and node ID |

The bundle model is a reusable template layer, not a priced reservation parent. Components stay independently priced and attributable to their providers on `QuoteItem`.

---

## 3. Current Capability Assessment

### 3.1 Status by Original Gap

| Gap | Status | Repository evidence | Remaining work |
|---|---|---|---|
| **G1**: Service-date inventory | Implemented | `ProviderItemBatch.service_start_at`, `service_end_at`; overlap filter via `service_window_start`/`service_window_end` parameters in [provider_item_batches.py](../ai_rfq_engine/models/provider_item_batches.py) | Load-test access patterns; decide on production indexing |
| **G2**: PAX and occupancy pricing | Implemented | `Item.pricing_mode`; `ItemPriceTier.pax_type`, `base_occupancy`, `extra_pax_surcharges`; full calculation paths in [quote_item.py](../ai_rfq_engine/models/quote_item.py) | Publish pricing examples; settle configurable PAX vocabulary |
| **G3**: Availability and holds | Implemented in core; deployment validation pending | `AvailabilityHoldModel`; conditional transactional capacity mutation and persisted lifecycle in [handler.py](../ai_rfq_engine/handlers/availability/handler.py); quote hooks in [quote_item.py](../ai_rfq_engine/models/quote_item.py) | Run DynamoDB-backed contention/lifecycle tests; schedule expiry processing |
| **G4**: Bundle composition | Implemented | `BundleModel`, `BundleComponentModel`; `Request.bundle_uuid`; `QuoteItem.bundle_uuid`, `bundle_label`, `bundle_component_uuid`; bundle filters in quote item and request list queries; seeded itinerary integration scenario in [test_hardening_pilot.py](../ai_rfq_engine/tests/test_hardening_pilot.py) | Execute the scenario against reachable DynamoDB |
| **G5**: Currency and FX | Implemented for quote-time conversion | `FxRateModel` with `currency_pair_date` LSI; `Quote.currency`, `display_currency`, `fx_rate`, `fx_rate_locked_at`; conversion logic in [quote_item.py](../ai_rfq_engine/models/quote_item.py) lines 834–863 | Define rate sourcing, rounding, expiry, and downstream settlement reconciliation |
| **G6**: Cancellation policy | Implemented for quoted-term integrity | `CancellationPolicyModel`; server-generated snapshot in [quote_item.py](../ai_rfq_engine/models/quote_item.py); caller substitution and update mutation rejected | Define policy authoring/import ownership and refund execution contract |
| **G7**: Catalog bridge | Implemented for KGE search-first lookup | `ItemCatalogRefModel` with `namespace_node_index` and `item_lookup_index`; `inquire_catalog`; KGE invoker-backed handler in [handler.py](../ai_rfq_engine/handlers/catalog/handler.py) | Node-by-ID KGE inquiry blocked (`OperationUnsupportedError`); validate against deployed KGE |

### 3.2 Existing RFQ Capabilities Reused Without a Separate Hospitality Engine

| Existing capability | Hospitality usage |
|---|---|
| `Item` and `ProviderItem` | Product and supplier/property/operator offering; `ProviderItem.availability_mode` governs availability enforcement |
| `Segment` and `SegmentContact` | Retail, corporate, loyalty, channel, or agent pricing segment |
| `Request`, `Quote`, and `QuoteItem` | Inquiry-to-offer workflow; `Request.bundle_uuid` may select a reusable package; `QuoteItem.batch_no` pins a service-dated batch |
| `Installment` | Deposit and balance schedule on a quote |
| `DiscountPrompt` | Discount and promotional rule input |
| `File` | Request-associated metadata only; document delivery is out of scope |

---

## 4. Implemented Design

### 4.1 Service Windows and Capacity Selection

`ProviderItemBatch` carries optional `service_start_at` and `service_end_at` fields for dated inventory, a boolean `in_stock` flag, and a numeric `availability_qty` field for remaining bookable units. The batch list query accepts `service_window_start` and `service_window_end` parameters and filters overlapping inventory:

```text
batch.service_start_at < service_window_end
and batch.service_end_at > service_window_start
```

Procurement batches without service dates remain unaffected. `produced_at` and `expired_at` are inventory-lifecycle fields and do not substitute for service dates.

### 4.2 Pricing Modes

`Item.pricing_mode` controls line pricing inside `insert_update_quote_item`:

| Mode | Calculation | Intended usage |
|---|---|---|
| `unit` or `null` | `price_per_uom * qty` | Procurement items, room-only unit rates, add-ons |
| `per_pax_type` | `sum(pax_breakdown[t] * tier_price_for(t))` per pax-type; `qty` must equal total pax | Tickets, meals, transfers, delegates |
| `occupancy` | `(base_rate + per-unit surcharges for guests beyond base_occupancy) * qty` | Room-nights and accommodation |

For occupancy mode, `qty` is the billable unit count (e.g. room-nights), **not** guest count. The `_get_occupancy_pricing_tier` helper selects the tier with `legacy_pax_only=True` (no `pax_type` filter) and reads `base_occupancy` and `extra_pax_surcharges` to compute per-unit surcharges.

### 4.3 Availability — Local Batch-Based Resolution

`ProviderItem.availability_mode` (default `"none"`) controls whether availability is evaluated before persisting a quote item:

| Mode | Behavior |
|---|---|
| `none` | Persist the quote item without an availability check |
| `check_only` | Require an available response from local batch data before persisting |
| `require_hold` | Atomically reserve quantified local batch capacity, persist a hold, and store its `hold_token` before persisting |

The availability handler ([handler.py](../ai_rfq_engine/handlers/availability/handler.py)) resolves availability directly from `ProviderItemBatch` data in this project's own DynamoDB tables — no external service call is needed. It matches batches using the existing `service_window_start`/`service_window_end` overlap filter and checks:

1. **`in_stock`** — the boolean stock flag (existing field).
2. **`availability_qty`** — a new numeric field representing remaining bookable units. When `availability_qty` is `null`, the batch is considered unquantified and passes the quantity check on `in_stock` alone. When set, the requested `qty` must not exceed `availability_qty`.

The four operations are:

| Operation | Behavior |
|---|---|
| `dispatch_check` | Queries matching batches; returns `available=True` if at least one batch passes `in_stock` and `availability_qty` thresholds |
| `dispatch_acquire_hold` | Requires quantified capacity; transactionally decrements `availability_qty` and writes a `held` hold record with a 15-minute `expires_at` |
| `dispatch_release_hold` | Loads the persisted hold and restores capacity exactly once when transitioning `held` to `released` |
| `dispatch_confirm_hold` | Loads the persisted unexpired hold and transitions `held` to `confirmed` without a second decrement |
| `dispatch_expire_hold` | Restores capacity exactly once when an expired `held` record transitions to `expired` |

The lifecycle hooks are:

- **Create**: `_enforce_availability` in `insert_update_quote_item` — dispatches `check` or `acquire_hold` depending on mode. If a hold is acquired, `hold_token` and `hold_expires_at` are stored on the `QuoteItem`.
- **Delete**: `_release_availability_hold` in `delete_quote_item` — dispatches `release_hold` for any held item.
- **Accept**: `_confirm_quote_item_holds` called when a `Quote` transitions to `accepted` status — dispatches `confirm_hold` for every held item on that quote.

**Hold token semantics**: Tokens identify persisted `AvailabilityHoldModel` rows. Unknown tokens fail closed. Local `require_hold` rejects unquantified capacity; a PMS/GDS-controlled product must instead use an authoritative external reservation boundary. The remaining operational requirement is invoking `expireAvailabilityHold` for expired abandoned holds so capacity is restored promptly.

### 4.4 Reservation Integrity Closure Design

**Implemented decision**: when `ProviderItem.availability_mode="require_hold"` and `ProviderItemBatch.availability_qty` is populated, RFQ owns a durable reservation hold and updates batch capacity atomically. If inventory is controlled by a PMS/GDS, the product must use that authoritative service rather than the local hold path.

#### Required Persistence

`AvailabilityHoldModel` persists one record per acquired hold:

| Field | Purpose |
|---|---|
| `partition_key`, `hold_token` | Tenant-scoped hold identity |
| `provider_item_uuid`, `batch_no` | Reserved capacity source |
| `quote_uuid`, `quote_item_uuid` | Owning quote line, populated before or as part of line persistence |
| `qty` | Reserved unit quantity |
| `service_start_at`, `service_end_at` | Reserved service window |
| `status` | `held`, `confirmed`, `released`, or `expired` |
| `expires_at` | Business expiration time; also usable for DynamoDB TTL cleanup after status processing |
| `created_at`, `updated_at`, `updated_by` | Audit attributes |

`ProviderItemBatch.availability_qty` represents currently available units after active holds have been deducted. For `require_hold`, a batch with `availability_qty=null` is not locally reservable: either reject it or route it through an explicitly configured external reservation authority.

#### Required Atomic Lifecycle

| Operation | Required behavior |
|---|---|
| Acquire | Select a matching batch, then transact: condition `in_stock=true` and `availability_qty >= qty`; decrement `availability_qty`; insert a `held` hold record with a unique token and expiration. The request succeeds only if both writes succeed. |
| Confirm | Conditionally change an existing unexpired `held` hold to `confirmed`. Capacity was already deducted at acquire time and must not be deducted again. Repeating confirmation returns the existing confirmed result without a second mutation. |
| Release | Conditionally change an existing `held` hold to `released` and increment the linked batch capacity once. Repeated release is idempotent. Release of a `confirmed` reservation is a cancellation/refund workflow, not a hold release. |
| Expire | For an expired `held` record, conditionally change it to `expired` and restore capacity once. TTL deletion may clean up records only after the capacity restoration transition is processed. |
| Unknown or invalid token | Reject confirmation and release; never acknowledge an unpersisted token as successful. |

Quote-item persistence must be consistent with the hold. If hold acquisition succeeds and subsequent `QuoteItem` creation fails, the operation must release the new hold or execute both operations within one transaction boundary. Any future update that changes `qty`, `batch_no`, or service dates on a held line must acquire replacement capacity atomically before releasing the prior hold, or be rejected until that workflow exists.

#### Required Verification

| Test | Passing condition |
|---|---|
| Concurrent acquisition | Two requests competing for insufficient remaining quantity cannot both receive successful holds. |
| Confirm idempotency | Confirming the same held token repeatedly does not decrement capacity again. |
| Release idempotency | Releasing the same held token repeatedly restores quantity only once. |
| Expiry restoration | An expired unconfirmed hold restores capacity once and cannot subsequently confirm. |
| Unknown token | Confirm/release of a token with no stored hold fails closed. |
| Quote creation failure | Capacity is not leaked when line creation fails after acquisition. |
| Unquantified batch | `require_hold` rejects a local batch with null `availability_qty`, unless an authoritative external adapter is selected. |

### 4.5 Catalog Search and Identity Mapping

Catalog discovery is KGE-owned. RFQ owns the mapping from KGE results to priceable internal records:

```text
KGE search(query_text, ...)
  → (namespace, node_id)
  → ItemCatalogRef.namespace_node_index (key: "namespace#node_id")
  → Item / optional ProviderItem
  → pricing and quote creation
```

`ItemCatalogRefModel` uses `namespace_node_key = namespace#node_id` and `item_lookup_key = item_uuid`. It also provides an `item_lookup_index` for reverse lookups from `item_uuid` to catalog references. The default namespace is `"DEFAULT"`. RFQ does not store `ExternalSystemConfig`, credentials, a Neo4j driver, or a handler registry; KGE owns all graph configuration and connection management.

Current limitation: text/search inquiry is supported via `inquire_catalog`; direct node-by-ID inquiry raises `OperationUnsupportedError` until KGE publishes that operation.

### 4.6 Terms and Currency

- A `ProviderItemBatch` may reference a `CancellationPolicyModel` via `cancellation_policy_uuid`. On quote-item creation, `_build_cancellation_snapshot` loads the policy and writes a server-generated copy to `QuoteItem.request_data.cancellation_policy_snapshot`. The snapshot key is reserved: caller input containing it is rejected, and an existing generated snapshot cannot be changed through quote-item update.
- A `Quote` may specify `currency` (native), `display_currency`, `fx_rate`, and `fx_rate_locked_at`. Line creation stores `subtotal_native` and applies conversion to display currency only when currencies differ and an FX rate is configured.
- Payment capture, refund computation, and settlement reconciliation are downstream responsibilities and out of scope for this engine.

#### Cancellation-Term Integrity Closure Design

`request_data.cancellation_policy_snapshot` is a reserved, engine-owned field. Caller-provided free-form `request_data` remains supported, but callers cannot write or update that reserved key.

Required behavior:

1. On create, reject any input containing `request_data.cancellation_policy_snapshot`, then write a server-generated value when the selected batch has a cancellation policy. Rejecting the reserved key exposes integration mistakes immediately and prevents forged terms even when no policy resolves.
2. On update, reject any attempt to edit or remove an existing generated snapshot. Changing the selected batch or its policy requires an explicit repricing/requote operation that creates a new server-generated snapshot.
3. Snapshot content must include the selected `policy_uuid`, displayed terms, tier data, and `snapshotted_at`. Add a policy version or content hash if policies may be externally reconciled or audited. ~~**Done** - `content_hash` (SHA-256 truncated to 16 hex chars) is now generated from stable policy-term content, excluding `snapshotted_at`, for cross-quote audit correlation.~~
4. Refund or cancellation processing must consume the stored server-generated snapshot, not the current mutable policy master record.

Required verification:

| Test | Passing condition |
|---|---|
| Caller substitution on create | A caller-supplied snapshot cannot replace the batch-linked generated snapshot. |
| Caller mutation on update | An existing generated snapshot cannot be edited or removed through quote-item update. |
| Policy changes after quote | Changing the policy master does not change the stored quote-line snapshot. |
| No batch policy | Free-form `request_data` remains usable when no cancellation policy is selected. |

---

## 5. GraphQL and Persistence Surface

| Area | Implemented additions |
|---|---|
| `Item` | `pricing_mode` |
| `ProviderItem` | `availability_mode` (default `"none"`), `provider_item_external_id`, `item_spec` (MapAttribute) |
| `ProviderItemBatch` | `service_start_at`, `service_end_at`, `availability_qty`, `currency`, `cancellation_policy_uuid` |
| `ItemPriceTier` | `pax_type`, `currency`, `base_occupancy` (MapAttribute), `extra_pax_surcharges` (MapAttribute) |
| `Request` | `bundle_uuid` optional package/template selection |
| `QuoteItem` | `pax_breakdown` (MapAttribute), `bundle_uuid`, `bundle_label`, `bundle_component_uuid`, `batch_no`, `currency`, `subtotal_native`, `hold_token`, `hold_expires_at` |
| New model/API | `BundleModel` - reusable package or itinerary template with `bundle_code`, `bundle_name`, `bundle_type`, `extra`, and `status` |
| New model/API | `BundleComponentModel` - default package components with `item_uuid`, optional `provider_item_uuid`, `component_role`, `required`, `default_qty`, `sort_order`, `extra`, and `status` |
| `Quote` | `currency`, `display_currency`, `fx_rate`, `fx_rate_locked_at` |
| New model/API | `AvailabilityHoldModel` - durable `held` / `confirmed` / `released` / `expired` capacity reservation state |
| New model/API | `FxRateModel` — `source_currency`, `target_currency`, `rate`, `currency_pair_date` (LSI), `rate_date`, `provider`, `notes`, `status` |
| New model/API | `CancellationPolicyModel` — `provider_item_uuid` (LSI), `label`, `description`, `tiers` (MapAttribute), `notes_template_uuid`, `status` |
| New model/API | `ItemCatalogRefModel` — `namespace_node_index`, `item_lookup_index`, `namespace`, `node_id`, `item_uuid`, `provider_item_uuid`, `extra` (MapAttribute), `status` |
| New integration API | Availability check and durable hold mutations (`checkAvailability`, `acquireAvailabilityHold`, `releaseAvailabilityHold`, `confirmAvailabilityHold`, `expireAvailabilityHold`) resolved locally from `ProviderItemBatch` and `AvailabilityHoldModel` data |
| New integration API | Catalog inquiry (`inquire_catalog`) routed to KGE search |

### Deployment Note

`ItemCatalogRefModel` uses `namespace_node_index` (not the previously drafted `system_node_index`). Any deployed `are-item_catalog_refs` table with the old LSI must be recreated or migrated; DynamoDB local secondary indexes cannot be altered in place.

---

## 6. Validation Status

Focused verification executed on 2026-05-24:

```powershell
$env:TEMP='C:\tmp'; $env:TMP='C:\tmp'
pytest ai_rfq_engine\tests\test_hospitality_pilot.py `
  ai_rfq_engine\tests\test_hardening_pilot.py `
  ai_rfq_engine\tests\test_availability_handler.py `
  ai_rfq_engine\tests\test_catalog_handler.py `
  ai_rfq_engine\tests\test_quote_item_g2_occupancy.py `
  ai_rfq_engine\tests\test_quote_item_g5_g6.py `
  ai_rfq_engine\tests\test_gap_closure_development.py `
  ai_rfq_engine\tests\test_availability_contention.py --test-function= -q
```

Result after gap-closure implementation and verification fixes: **78 passed, 11 skipped**.

| Validation area | Status |
|---|---|
| Schema exposure, service-window validation, PAX pricing, occupancy pricing, and FX behavior | Passing unit coverage |
| Cancellation snapshot generation and reserved-key substitution/update rejection | Passing unit coverage |
| KGE catalog request contract and error normalization | Passing unit coverage |
| Durable hold request construction, fail-closed atomic race path, transition hooks, and explicit expiry hooks | Passing unit coverage; DynamoDB-backed contention/lifecycle scaffold covers all seven §4.4 verification cases; execution still requires reachable DynamoDB |
| Hotel room-night integration flow | Collected; skipped without reachable DynamoDB |
| Procurement regression and complete hotel hardening integration paths | Collected; skipped without reachable DynamoDB |
| Restaurant/event hold flow | DynamoDB-backed test implemented with local `ProviderItemBatch` capacity, hold acquisition, deposit, and quote acceptance; not executed without reachable DynamoDB |
| Multi-leg itinerary bundle flow | Seeded hotel, transfer, and activity integration test implemented; not executed without reachable DynamoDB |

These results cover local contract, business-calculation, reservation-protection, and quoted-term protection logic. They do not constitute deployed DynamoDB contention/lifecycle evidence or successful deployed KGE workflow evidence.

---

## 7. Remaining Gaps and Priorities

### Priority 0 — Reserve-Authoritative Availability Validation

**Owner boundary**: RFQ team (availability is now local; no external dependency).

The Section 4.4 persistence and transaction design is implemented. Required validation and operational work:

1. Run concurrent acquisition and lifecycle integration tests against DynamoDB-backed `ProviderItemBatch` rows containing `availability_qty`.
2. Configure an expiry invoker or job that calls the implemented expiry operation for abandoned `held` records. ~~**Done** — `scan_expired_holds` in `handlers/availability/expiry_scanner.py` scans for expired `held` records and invokes `dispatch_expire_hold` to restore capacity. Supports `dry_run` mode for safe inspection and `batch_size` to limit processing per invocation. Designed to be called from a scheduled Lambda/EventBridge.~~
3. Confirm deployment table creation/migration for `are-availability_holds`.

**Exit criterion**: Competing requests cannot overbook one capacity pool; a persisted hold reserves availability, confirms on accepted quote, releases or expires exactly once, and is verified through DynamoDB-backed concurrency tests.

### Priority 1 - Authoritative Quoted Terms

Implemented behavior and remaining business work:

1. The reserved snapshot key is rejected in caller input and existing generated snapshots cannot be changed through quote-item update.
2. Unit tests cover substitution and update-mutation rejection.
3. Define who may author/import cancellation policies and how refunds consume the quoted snapshot.

**Exit criterion**: A quoted line with a selected cancellation policy always stores the engine-generated terms, independent of caller payload.

### Priority 2 - Complete Integration Evidence

Required work:

1. Run hotel and procurement regression paths against an accessible DynamoDB test environment.
2. Execute the seeded multi-leg itinerary integration test covering grouped hotel, transfer, and activity lines.
3. Validate KGE catalog search and namespace-to-item mapping against a deployed KGE instance.
4. Add a deployed contract test for any future node-by-ID catalog lookup.

**Exit criterion**: The four pilot scenarios run without placeholder skips (other than deliberately unavailable optional integration operations).

### Priority 3 - Production Migration and Operations

Required work:

1. Confirm whether any deployed catalog-reference table uses the obsolete `system_node_index` layout and prepare its migration.
2. Load-test service-window queries at representative volume before introducing an additional index.
3. Add handler metrics and audit events for KGE operation, duration, tenant partition, namespace, and error code.
4. Review cache invalidation for new filter dimensions: service windows, PAX tier selection, and bundle UUID.
5. Establish rate limits and timeout budgets for KGE-backed calls.

### Priority 4 - Commercial Policy Decisions

The following decisions are required before broad customer rollout:

| Decision | Current provisional behavior |
|---|---|
| PAX categories | Caller-provided category strings; formal tenant vocabulary not defined |
| Bundle representation | Reusable `Bundle`/`BundleComponent` templates feed independently priced `QuoteItem` component lines; no priced parent bundle line |
| FX rate source and staleness | Locked quote field exists; source/freshness policy not defined |
| Cancellation policy authoring | Engine persists and snapshots policies; import/authoring ownership not defined |
| Namespace default | `"DEFAULT"` is the catalog sentinel; should be ratified or replaced |
| External vendor breadth | KGE is the only catalog boundary implemented; PMS/GDS adapters absent |

### Priority 5 - Documentation Handoff

The implementation has moved ahead of general project documentation. Update:

1. ~~[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) — identify hospitality as a supported workload, not a future proposal.~~ **Done** — Item, ProviderItem, ProviderItemBatch, ItemPriceTier, Request, QuoteItem, Quote all reflect hospitality fields; Bundle, BundleComponent, FxRate, CancellationPolicy, ItemCatalogRef models documented.
2. ~~[PRICING_CALCULATION.md](PRICING_CALCULATION.md) — document `per_pax_type`, `occupancy`, native/display currency, and cancellation-snapshot behavior.~~ **Done** — Sections 7a–7d added covering hospitality pricing modes, FX conversion, cancellation snapshots, and availability hold lifecycle.
3. ~~[HOSPITALITY_QUICK_START.md](HOSPITALITY_QUICK_START.md) - service-dated inventory, pricing modes, KGE mapping, and reservation-readiness restrictions.~~ **Done**.

---

## 8. Rollout Plan

| Stage | Objective | Deliverables | Gate |
|---|---|---|---|
| **A**: Reservation integrity | Validate implemented authoritative availability under concurrency | DynamoDB contention/lifecycle execution; expiry invocation; hold table deployment | Competing requests cannot overbook; expired holds restore capacity operationally |
| **B**: Terms integrity | Complete commercial consumption of engine-owned terms | Implemented conflict/update rejection; refund consumption contract | Downstream cancellation uses stored quoted terms |
| **C**: Integration hardening | Establish real workflow confidence | DynamoDB-backed procurement, hotel, restaurant/event, and itinerary tests | No blocking integration skips |
| **D**: Production readiness | Make deployment observable and migratable | Catalog-ref migration plan; metrics/audit; load-test/index decision | Operational review complete |
| **E**: Commercial rollout | Define tenant-facing policy | ADRs for PAX, FX, cancellation, namespace, vendor roadmap; updated documentation | Product and architecture sign-off |

Stages A through D are bounded engineering work within this repository unless the team explicitly selects an external reservation authority. Stage A is no longer blocked on a KGE contract, but it is not complete.

---

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Expired hold processing is not scheduled in this repository | Abandoned capacity remains reserved until expiry is invoked | ~~`scan_expired_holds` implemented in `expiry_scanner.py`~~; configure a deployment-side scheduled invoker to call it |
| Integration tests skipped without DynamoDB access | Unit-tested behavior may diverge from deployed persistence behavior | Run the integration suite in deployment-side CI with controlled tables |
| Catalog-ref LSI layout changed during implementation | Existing deployed table cannot be updated in place | Detect deployment state and recreate/migrate before enabling G7 data |
| Service-window filters require scans at scale | Query-time latency and DynamoDB cost grow with dated inventory | Measure before selecting a production index design |
| FX and cancellation rules lack business governance | Customer totals or terms may be inconsistent across channels | Approve authoring, staleness, rounding, and refund policies before rollout |
| New filters and price dimensions interact with cache behavior | Stale inventory or pricing responses | Add invalidation tests and handler telemetry |
| Downstream refund workflow is not specified | Enforced snapshot may not be consumed during cancellation | Define refund execution against the stored engine-owned snapshot |

---

## 10. Gap Closure Development (2026-05-24)

The following additions were made to close identified priorities from §7:

### 10.1 Hold Expiry Scanner (Priority 0, item 2)

**File**: `handlers/availability/expiry_scanner.py`

`scan_expired_holds` scans `AvailabilityHoldModel` for `held` records past their `expires_at` and invokes `dispatch_expire_hold` to restore capacity. Features:

- `batch_size` parameter to limit records processed per invocation (default 100)
- `dry_run` mode for safe inspection before enabling in production
- `_query_fn` override for testability without DynamoDB
- Graceful handling of already-transitioned holds (`UnknownHoldError`)
- Audit logging of scanned, expired, and error counts

Exported from `handlers.availability.__init__` as `scan_expired_holds`.

**Deployment requirement**: configure a scheduled invoker (Lambda, EventBridge, cron) to call `scan_expired_holds(logger, partition_key=<tenant>)` at appropriate intervals.

### 10.2 Handler Telemetry (Priority 3, item 3)

**File**: `handlers/telemetry.py`

Structured audit events for availability and catalog operations:

- `emit_handler_event`: emits a log event with operation, handler, duration, tenant partition, namespace, and error code
- `measure_handler_duration`: context manager that measures wall-clock duration and emits telemetry on success or failure

Wired into all five availability dispatch functions and `dispatch_inquire` via `measure_handler_duration` wrapping.

### 10.3 Cancellation Snapshot Content Hash (Priority 1, §4.6 item 3)

**Change**: `_build_cancellation_snapshot` in `models/quote_item.py` now includes a `content_hash` field - a SHA-256 digest (truncated to 16 hex characters) of stable policy-term content, excluding `snapshotted_at`, providing an audit-deterministic fingerprint for external reconciliation of policy terms.

### 10.4 Concurrency Integration Test Scaffold (Priority 0, item 1)

**File**: `tests/test_availability_contention.py`

DynamoDB-backed integration tests for the §4.4 integrity requirements:

- `TestConcurrentHoldAcquisition`: concurrent acquisition, confirm idempotency, release idempotency, unknown-token fail-closed
- `TestExpiredHoldRestoresCapacity`: expired hold restores capacity once and blocks subsequent confirm (§4.4 verification #4)
- `TestUnquantifiedBatchRejectsHold`: `require_hold` rejects a local batch with null `availability_qty` (§4.4 verification #7)
- `TestQuoteCreationFailureNoLeak`: capacity restored exactly once when the line-creation cleanup primitive (release) runs after a successful acquire, then re-acquire succeeds (§4.4 verification #6, exercises the cleanup path used in `insert_update_quote_item`'s except block)

Gated on `@pytest.mark.integration` and requires reachable DynamoDB.

### 10.5 Gap Closure Unit Tests

**File**: `tests/test_gap_closure_development.py`

Covers expiry scanner, handler telemetry, and snapshot content hash with 14 unit tests:

| Component | Tests |
|---|---|
| Expiry scanner | dry_run, scheduled invocation without supplied GraphQL context, tenant-context validation, dispatch invocation, batch_size limit |
| Handler telemetry | success logging, error warning, duration measurement, namespace, no-op without logger |
| Snapshot content hash | hash included in snapshot, hash differs for different policies, hash remains stable for identical policy terms |

## 11. Out Of Scope

- Payment authorization, capture, refunds, and settlement reporting.
- Email, document generation, and file-content delivery.
- KGE graph schema design, credentials, and connection pooling (catalog discovery remains KGE-owned; availability is now local).
- External PMS/GDS synchronization beyond the selected reservation-authority boundary.
- MCP processor or AI agent orchestration outside this repository.
- Persisted parent bundle lines or nested packages.

---

## 12. Immediate Next Actions

| Order | Action | Outcome |
|---|---|---|
| 1 | Run existing and contention integration tests against reachable DynamoDB, including the new hold table | Replaces unit-only reservation evidence with end-to-end proof |
| 2 | Configure expiry invocation for abandoned `held` rows | ~~Scanner implemented (`expiry_scanner.py`)~~; deploy a scheduled invoker to call it |
| 3 | Define refund execution against engine-owned cancellation snapshots | Makes quoted terms operational downstream |
| 4 | Decide and execute any `are-item_catalog_refs` index migration | Avoids deployment failure for existing environments |
| 5 | Add operational telemetry, load tests, and commercial policy ADRs | Supports controlled rollout |
