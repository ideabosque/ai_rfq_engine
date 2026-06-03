# Product Requirements Document (PRD)

# AI RFQ Engine

**Version**: 1.0  
**Date**: 2026-06-02  
**Status**: Active Development  
**Author**: Idea Bosque  
**License**: MIT  

---

## 1. Product Overview

### 1.1 Vision

The AI RFQ Engine is a serverless, GraphQL-first Request for Quote management platform that powers intelligent, automated B2B procurement and hospitality quoting workflows. It combines deterministic pricing calculation with AI-driven discount negotiation, enabling organizations to generate, negotiate, and finalize quotes through a unified API that integrates seamlessly with AI assistants via the Model Context Protocol (MCP).

### 1.2 Problem Statement

Organizations managing RFQ workflows face three persistent challenges:

1. **Manual, error-prone pricing**: Pricing teams manually compute tiered prices across segments, providers, and volume thresholds, leading to inconsistencies and margin leakage.
2. **Opaque discount authority**: Discount decisions lack structured guardrails, making it hard to enforce pricing policies while still allowing flexibility for negotiations.
3. **Fragmented supplier communication**: RFQ distribution, quote collection, and supplier comparison require manual coordination across disconnected tools.

### 1.3 Target Users

| User Persona | Role | Key Needs |
|---|---|---|
| **Procurement Manager** | Initiates RFQs, compares supplier quotes | Fast quote generation, multi-provider comparison, transparent pricing |
| **Sales Representative** | Responds to RFQs with quotes | Accurate tier pricing, discount authority, negotiation tracking |
| **Pricing Administrator** | Configures tiers, segments, discount policies | Structured rule authoring, validation, scope management |
| **AI Assistant (via MCP)** | Orchestrates end-to-end RFQ workflows | 28 high-level tools, batch-optimized queries, status automation |
| **Hospitality Operator** | Quotes rooms, events, transfers, packages | Service-dated inventory, occupancy/PAX pricing, availability holds, cancellation terms |
| **Integration Engineer** | Connects external systems | GraphQL API, DynamoDB schema, catalog mapping, MCP protocol |

### 1.4 Product Differentiators

1. **AI-native discount system**: Discount prompts combine machine-readable tiered rules with natural-language instructions for LLM-driven negotiation decisions, bounded by `max_discount_percentage` guardrails.
2. **Hospitality without a separate engine**: Service-dated batches, PAX/occupancy pricing, availability holds, FX conversion, and cancellation snapshots extend the procurement core without branching into a separate product line.
3. **Batch-optimized GraphQL**: DataLoader pattern eliminates N+1 queries, achieving 97% reduction in database reads (153 to 5 queries for typical workflows) and sub-200ms p95 latency for nested queries.
4. **Multi-tenant serverless**: AWS Lambda + DynamoDB with `partition_key` tenant isolation; zero infrastructure management at the API layer.

---

## 2. Functional Requirements

### 2.1 Item and Catalog Management

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-001 | Create, update, and delete catalog items with type, UOM, description, and pricing mode | Must | Implemented |
| FR-002 | Items support three pricing modes: `unit`, `per_pax_type`, and `occupancy` | Must | Implemented |
| FR-003 | Items carry an optional `item_external_id` for external system reference | Should | Implemented |
| FR-004 | Deletion is blocked when provider items reference the item (referential integrity) | Must | Implemented |
| FR-005 | List and filter items by type, name, description, pricing mode, and UOM | Must | Implemented |
| FR-006 | Map external catalog identities (KGE nodes) to internal items via `ItemCatalogRef` | Should | Implemented |
| FR-007 | Query catalog references by namespace, node ID, and item UUID (forward and reverse) | Should | Implemented |
| FR-008 | Search KGE catalog via `inquire_catalog` and resolve results to internal items | Should | Implemented |

### 2.2 Provider and Inventory Management

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-009 | Create, update, and delete provider-specific item offerings with base price, spec, and external ID | Must | Implemented |
| FR-010 | Provider items support availability enforcement modes: `none`, `check_only`, `require_hold` | Must | Implemented |
| FR-011 | Track inventory batches with cost breakdown (cost + freight + additional = total cost) | Must | Implemented |
| FR-012 | Auto-calculate `total_cost_per_uom` and `guardrail_price_per_uom` on batch insert/update | Must | Implemented |
| FR-013 | Batches support service windows (`service_start_at`, `service_end_at`) for dated inventory | Must | Implemented |
| FR-014 | Batches carry `availability_qty` for quantified bookable units; `null` = unquantified | Must | Implemented |
| FR-015 | Batches carry `currency` and `cancellation_policy_uuid` for hospitality workflows | Should | Implemented |
| FR-016 | Filter batches by service window overlap, cost range, stock status, and slow-move flag | Should | Implemented |
| FR-017 | Deletion is blocked when quote items, price tiers, or batches reference the provider item | Must | Implemented |

### 2.3 Customer Segmentation

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-018 | Create, update, and delete customer segments with name and description | Must | Implemented |
| FR-019 | Associate contacts with segments via email-based lookup (`SegmentContact`) | Must | Implemented |
| FR-020 | Segments can be scoped to a provider corporation via `provider_corp_external_id` | Should | Implemented |
| FR-021 | Deletion is blocked when contacts, price tiers, or discount prompts reference the segment | Must | Implemented |

### 2.4 Tiered Pricing

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-022 | Define quantity-banded price tiers per (item, provider item, segment) combination | Must | Implemented |
| FR-023 | Tiers support two pricing paths: fixed `price_per_uom` or margin-based from batch costs | Must | Implemented |
| FR-024 | Tier insertion auto-updates the previous tier's upper bound to maintain contiguous ranges | Must | Implemented |
| FR-025 | Tiers in `active` status participate in pricing; `in_review` and `inactive` do not | Must | Implemented |
| FR-026 | Tiers support `pax_type` for per-PAX-type pricing mode | Must | Implemented |
| FR-027 | Tiers support `base_occupancy` and `extra_pax_surcharges` maps for occupancy pricing mode | Must | Implemented |
| FR-028 | Filter tiers by provider item, segment, quantity value, price range, PAX type, and status | Must | Implemented |

### 2.5 Discount Prompts and AI-Driven Negotiation

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-029 | Create discount prompts with scope (GLOBAL, SEGMENT, ITEM, PROVIDER_ITEM), tags, priority, and status | Must | Implemented |
| FR-030 | Each prompt carries a `discount_prompt` natural-language instruction for AI consumption | Must | Implemented |
| FR-031 | Each prompt carries structured `discount_rules` (tiered discount table with validation) | Must | Implemented |
| FR-032 | Discount rules are validated: contiguous, monotonically increasing, first tier at 0, open-ended last tier | Must | Implemented |
| FR-033 | Discount rules merge on update: same-`greater_than` values are overridden, then re-validated | Must | Implemented |
| FR-034 | Prompts carry optional `conditions` (predicate list) for AI evaluation | Should | Implemented |
| FR-035 | Combine all applicable prompts across scope hierarchy (GLOBAL -> SEGMENT -> ITEM -> PROVIDER_ITEM) | Must | Implemented |
| FR-036 | Segmented prompts resolved via email-to-segment lookup using `SegmentContactLoader` | Must | Implemented |
| FR-037 | Apply discounts to quote items as `subtotal_discount`; recalculate `final_subtotal` and quote totals | Must | Implemented |

### 2.6 Request and Quote Workflow

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-038 | Create, update, and delete RFQ requests with email, title, description, items, and addresses | Must | Implemented |
| FR-039 | Requests carry an optional `bundle_uuid` for package/template selection | Should | Implemented |
| FR-040 | Requests carry an optional `expired_at` for deadline management | Should | Implemented |
| FR-041 | Request status auto-transitions: adding items -> `in_progress`; confirming -> `confirmed`; all quotes completed -> `completed` | Must | Implemented |
| FR-042 | Create, update, and delete quotes against a request, specifying provider, shipping, and notes | Must | Implemented |
| FR-043 | Quotes track negotiation `rounds` (auto-incremented on quote/quote-item updates) | Should | Implemented |
| FR-044 | Quote confirmation auto-disapproves competing quotes from the same request | Must | Implemented |
| FR-045 | Quotes support native `currency`, `display_currency`, locked `fx_rate`, and `fx_rate_locked_at` | Must | Implemented |
| FR-046 | Quote totals (`total_quote_amount`, `total_quote_discount`, `final_total_quote_amount`) are auto-calculated from quote items | Must | Implemented |
| FR-047 | Create, update, and delete quote items with pricing, quantities, discounts, and bundle grouping | Must | Implemented |
| FR-048 | Quote item pricing is mode-dependent (`unit`, `per_pax_type`, `occupancy`) | Must | Implemented |
| FR-049 | Quote items support `bundle_uuid`, `bundle_label`, and `bundle_component_uuid` for package grouping | Should | Implemented |
| FR-050 | Quote items store `subtotal_native` and display-converted `subtotal` when FX is configured | Must | Implemented |
| FR-051 | Quote items store `hold_token` and `hold_expires_at` for availability holds | Must | Implemented |
| FR-052 | After creation, `qty`, `batch_no`, and `pax_breakdown` on quote items are immutable | Must | Implemented |
| FR-053 | Deletion is blocked when installments exist on the parent quote | Must | Implemented |

### 2.7 Availability and Holds

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-054 | `check_only` mode: verify availability against local batch data before persisting quote item | Must | Implemented |
| FR-055 | `require_hold` mode: atomically decrement `availability_qty` and persist `AvailabilityHold` with 15-minute TTL | Must | Implemented |
| FR-056 | Hold acquisition uses conditional `TransactWrite` to prevent overbooking under concurrency | Must | Implemented |
| FR-057 | On quote-item creation failure after hold acquisition, capacity is released automatically | Must | Implemented |
| FR-058 | Hold confirmation (on quote `accepted`): transition `held` to `confirmed` without re-decrementing capacity | Must | Implemented |
| FR-059 | Hold release: transition `held` to `released` and restore capacity exactly once (idempotent) | Must | Implemented |
| FR-060 | Hold expiry: transition stale `held` records to `expired` and restore capacity exactly once | Must | Implemented |
| FR-061 | Unknown tokens fail closed (reject confirm/release) | Must | Implemented |
| FR-062 | `require_hold` rejects unquantified batches (`availability_qty = null`) | Must | Implemented |

### 2.8 Cancellation Policies

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-063 | Create and manage reusable cancellation policies with tiers, labels, and descriptions | Should | Implemented |
| FR-064 | Link policies from `ProviderItemBatch.cancellation_policy_uuid` | Must | Implemented |
| FR-065 | Engine generates immutable snapshot on `QuoteItem.request_data.cancellation_policy_snapshot` at quote time | Must | Implemented |
| FR-066 | The `cancellation_policy_snapshot` key is engine-owned: caller input is rejected, existing snapshots cannot be edited | Must | Implemented |
| FR-067 | Snapshot includes `content_hash` (SHA-256 truncated) for audit reconciliation | Should | Implemented |

### 2.9 Installment and Payment Scheduling

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-068 | Create, update, and delete installment rows on a quote for payment scheduling | Must | Implemented |
| FR-069 | Installments carry `priority`, `installment_amount`, `installment_ratio`, `scheduled_date`, and `payment_method` | Must | Implemented |
| FR-070 | `installment_ratio` is auto-calculated as percentage of `final_total_quote_amount` | Must | Implemented |
| FR-071 | Installments carry optional `salesorder_no` for downstream invoicing | Should | Implemented |
| FR-072 | Filter installments by quote, request, date range, amount range, ratio range, and status | Should | Implemented |

### 2.10 Bundles and Package Templates

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-073 | Create reusable package/itinerary templates (`Bundle`) with code, name, type, description, and status | Should | Implemented |
| FR-074 | Define default components (`BundleComponent`) per bundle with item, provider item, role, required flag, default qty, and sort order | Should | Implemented |
| FR-075 | Requests can select a bundle via `bundle_uuid` | Should | Implemented |
| FR-076 | Quote items can group under a `bundle_uuid` and `bundle_label` without creating a priced parent line | Should | Implemented |
| FR-077 | Quote items can reference back to their originating `bundle_component_uuid` | Should | Implemented |
| FR-078 | Deletion is blocked when components, requests, or quote items reference the bundle | Must | Implemented |

### 2.11 Foreign Exchange

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-079 | Manage currency conversion rates (`FxRate`) with source/target currencies, rate, date, and provider | Should | Implemented |
| FR-080 | Rates indexed by `currency_pair_date` composite key for time-based lookups | Should | Implemented |
| FR-081 | Quotes lock an FX rate at quote time; line items persist both `subtotal_native` and converted `subtotal` | Must | Implemented |
| FR-082 | FX conversion is skipped when currencies match; the engine does not silently default to rate 1.0 | Must | Implemented |

### 2.12 File Management

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-083 | Attach file metadata to requests (name, size, type, uploader email) | Should | Implemented |
| FR-084 | Filter files by request and email | Should | Implemented |

### 2.13 MCP Integration

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-085 | Expose 28 MCP tools covering request, item, quote, pricing, installment, file, segment, and workflow operations | Should | External package |
| FR-086 | Workflow abstraction: multi-step processes (e.g. "confirm request and create quotes") in single tool calls | Should | External package |
| FR-087 | Batch-optimized price tier and discount prompt queries via email-based segment lookup | Should | External package |
| FR-088 | Validated status transitions with automatic business rule enforcement | Should | External package |

---

## 3. Non-Functional Requirements

### 3.1 Performance

| ID | Requirement | Target | Current |
|---|---|---|---|
| NFR-001 | Nested GraphQL query p95 latency | < 200ms | Achieved |
| NFR-002 | N+1 query elimination via DataLoader | > 95% reduction in DB reads | 97% achieved (153 -> 5 queries) |
| NFR-003 | Batch loader cache hit rate for repeated entity lookups within a request | > 90% | Achieved |
| NFR-004 | Quote item creation (including pricing, hold, FX, snapshot) | < 500ms p95 | Achieved |

### 3.2 Scalability

| ID | Requirement | Target |
|---|---|---|
| NFR-005 | Multi-tenant isolation via `partition_key` on all tables | Complete |
| NFR-006 | Serverless auto-scaling via AWS Lambda | Complete |
| NFR-007 | DynamoDB on-demand capacity for variable workloads | Complete |
| NFR-008 | Request-scoped DataLoaders prevent cross-request memory leaks | Complete |

### 3.3 Reliability

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-009 | Overbooking prevention under concurrent holds | Zero double-bookings | Requires DynamoDB-backed validation |
| NFR-010 | Capacity leak prevention on quote-item creation failure | Automatic hold release on failure | Implemented |
| NFR-011 | Expired hold cleanup restores capacity | Operational expiry invocation | Scanner implemented; deployment trigger required |
| NFR-012 | Cascading delete protection for parent-child relationships | Prevents orphaned records | Implemented |

### 3.4 Data Integrity

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-013 | Cancellation snapshot immutability | Engine-ownership enforced | Implemented |
| NFR-014 | Discount rule validation (contiguous, increasing, well-formed) | Rejected on invalid input | Implemented |
| NFR-015 | Price tier contiguity (gap-free, auto-updating upper bounds) | Auto-maintained on insert | Implemented |
| NFR-016 | Quote totals consistency (sum of items + shipping) | Auto-recalculated on any item change | Implemented |
| NFR-017 | FX conversion only when currencies differ (no silent 1.0 default) | Strict check enforced | Implemented |

### 3.5 Security

| ID | Requirement | Target |
|---|---|---|
| NFR-018 | Tenant data isolation via `partition_key`; no cross-tenant data leakage | Complete |
| NFR-019 | Input validation on all mutations (required fields, type checking, range checks) | Complete |
| NFR-020 | Engine-owned fields (`cancellation_policy_snapshot`) cannot be caller-supplied | Complete |
| NFR-021 | Hold tokens are opaque; unknown tokens fail closed | Complete |

### 3.6 Observability

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-022 | Handler telemetry for availability and catalog operations (operation, duration, tenant, error code) | Structured audit events | Implemented |
| NFR-023 | Cache invalidation cascading (entity type, depth) | 3-level cascade | Implemented |
| NFR-024 | CloudWatch metrics for batch loader performance | Query reduction metrics | Not started |

---

## 4. System Architecture

### 4.1 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| API | Graphene (Python) | GraphQL schema, resolvers, types |
| Database | Amazon DynamoDB | 18 tables, multi-tenant partitioning |
| Compute | AWS Lambda | Serverless function execution |
| Framework | SilvaEngine | Custom Python framework (BaseModel, Graphql, utilities) |
| ORM | PynamoDB | DynamoDB model definitions and queries |
| Batch Loading | promise.DataLoader | N+1 query elimination |
| Cache | HybridCacheEngine | Multi-layer caching (application, request, method) |
| AI Integration | MCP Protocol | 28 tools for AI-driven RFQ workflows |
| Testing | pytest | Parametrized tests, fixtures, markers |

### 4.2 Architectural Patterns

1. **Lazy Loading with Nested Resolvers**: Related data fetched only when requested by the client via GraphQL field resolvers, reducing payload size and unnecessary DB reads.

2. **DataLoader Batch Optimization**: Collects individual entity lookups within a single GraphQL request and batches them into minimal DB queries. Request-scoped `RequestLoaders` container manages 19+ loaders per request.

3. **Three-Layer Caching**:
   - **Application Cache**: Schema and static configuration
   - **Request Cache (DataLoader)**: Deduplication within a single GraphQL request
   - **Method Cache (`@method_cache`)**: Cross-request caching via `HybridCacheEngine`

4. **Multi-Tenant Partitioning**: Every table uses `partition_key` (or `endpoint_id`) as the hash key for tenant isolation. Cross-tenant queries are structurally impossible at the data layer.

5. **Derived Field Auto-Calculation**: Fields like `total_cost_per_uom`, `guardrail_price_per_uom`, `price_per_uom`, `subtotal`, `final_subtotal`, `installment_ratio`, and quote totals are computed by the engine and never manually set.

### 4.3 Data Model

The engine manages **18 DynamoDB tables** organized into five domain layers:

```
Catalog Layer:
  are-items, are-provider_items, are-provider_item_batches,
  are-item_catalog_refs, are-bundles, are-bundle_components

Pricing Layer:
  are-item_price_tiers, are-discount_prompts, are-fx_rates,
  are-cancellation_policies

Segmentation Layer:
  are-segments, are-segment_contacts

RFQ Workflow Layer:
  are-requests, are-quotes, are-quote_items, are-installments

Operations Layer:
  are-availability_holds, are-files
```

### 4.4 GraphQL Surface

**Queries**: 26 root query fields covering entity lookups, filtered lists, and cross-entity batch lookups (e.g. `itemPriceTiers`, `discountPrompts`, `itemCatalogRefs`).

**Mutations**: 32 mutations covering CRUD for all entities, plus 4 availability hold operations (`acquire`, `release`, `confirm`, `expire`).

---

## 5. Pricing Calculation

### 5.1 Two-Stage Pipeline

The engine implements a deterministic two-stage pricing pipeline:

**Stage 1 - Price Calculation**:
1. Resolve customer segment from email via `SegmentContact`
2. Match active `ItemPriceTier` by (item, provider item, segment, qty range)
3. Apply pricing mode:
   - `unit`: `price_per_uom * qty`
   - `per_pax_type`: `sum(pax_breakdown[t] * tier_price(t))`; `qty` must equal total pax
   - `occupancy`: `(base_rate + per-pax surcharges for guests beyond base_occupancy) * qty`
4. If tier uses `margin_per_uom`, compute from batch costs: `total_cost * (1 + margin/100)`
5. Slow-move items use `guardrail_price_per_uom` as floor price

**Stage 2 - Discount Application**:
1. Load applicable discount prompts across scope hierarchy (GLOBAL -> SEGMENT -> ITEM -> PROVIDER_ITEM)
2. AI evaluates prompt text, conditions, and `discount_rules` to decide `subtotal_discount`
3. Discount bounded by `max_discount_percentage` from matching tier rule
4. `final_subtotal = subtotal - subtotal_discount`
5. Quote totals are recalculated across all items

### 5.2 FX Conversion

When a quote carries a locked FX rate and `display_currency` differs from native `currency`:
- `subtotal_native` stores the supplier-currency amount
- `subtotal` stores the display-currency converted amount (`subtotal_native * fx_rate`)
- No silent default to rate 1.0 — same-currency quotes skip conversion entirely

---

## 6. Availability and Hold Lifecycle

```
                      acquireAvailabilityHold
                              │
                              ▼
                    ┌──────────────────┐
                    │     held         │
                    │ (15-min TTL)     │
                    └──┬────┬────┬────┘
                       │    │    │
            confirm    │    │    │   expireAvailabilityHold
                       │    │    │
                       ▼    │    ▼
              ┌──────────┐  │  ┌──────────┐
              │confirmed │  │  │ expired  │
              └──────────┘  │  └──────────┘
                            │
                     releaseAvailabilityHold
                            │
                            ▼
                     ┌──────────┐
                     │ released │
                     └──────────┘
```

- **Acquire**: Conditional `TransactWrite` decrements `availability_qty` and inserts hold record
- **Confirm**: On quote acceptance; no second capacity decrement
- **Release**: On quote-item deletion; restores capacity once (idempotent)
- **Expire**: Scanner transitions abandoned holds; restores capacity once

---

## 7. Out of Scope

| Concern | Boundary |
|---|---|
| Payment authorization, capture, settlement | Downstream payment service |
| Refund execution against cancellation snapshots | Downstream cancel/refund service |
| Email, document generation, PDF delivery | Downstream document service |
| KGE graph schema, credentials, connection pooling | Knowledge Graph Engine |
| PMS / GDS / channel-manager synchronization | External adapter (not yet implemented) |
| MCP / AI agent orchestration | External package (`mcp_rfq_processor`) |
| Persisted parent bundle line or nested package row | By design — `bundle_uuid` grouping only |

---

## 8. Known Gaps and Roadmap

### 8.1 Production Readiness Gaps

| Gap | Priority | Status | Exit Criterion |
|---|---|---|---|
| DynamoDB-backed concurrent hold validation | P0 | Unit tests pass; integration pending | Competing requests cannot overbook |
| Expiry invocation for abandoned holds | P0 | Scanner implemented; deployment trigger needed | Abandoned holds restored operationally |
| Refund execution contract against snapshots | P1 | Not defined | Downstream consumes stored snapshot |
| KGE node-by-ID catalog lookup | P2 | Returns `OperationUnsupportedError` | KGE publishes the operation |
| Service-window query indexing | P3 | Not measured | Load-test + index decision |

### 8.2 Feature Roadmap

| Phase | Focus | Items |
|---|---|---|
| Phase 1 | Code quality | Complete resolver migration, linting (`black`, `flake8`, `mypy`), pre-commit hooks, pinned dependencies |
| Phase 2 | Performance | Batch loader monitoring, CloudWatch metrics, query complexity limits |
| Phase 3 | API experience | GraphQL docstrings, generated schema docs, client migration guide |
| Phase 4 | Commercial policy | PAX vocabulary, FX rate sourcing, cancellation authoring, namespace ratification, vendor roadmap |

### 8.3 Development Progress

```
Core Architecture:    75% - In progress
Caching System:      100% - Complete
Testing Framework:    85% - Good
Code Quality:          0% - Not started
Documentation:        40% - Fair
CI/CD Pipeline:        0% - Not started
Overall Progress:     75% - In progress
```

---

## 9. Success Metrics

| Metric | Target | Current |
|---|---|---|
| N+1 query reduction | > 95% | 97% (153 -> 5 reads) |
| Nested query p95 latency | < 200ms | Achieved |
| Test coverage | > 85% | 85% (78 passed, 11 skipped in hospitality suite) |
| Concurrent hold overbooking | 0 events | Pending DynamoDB validation |
| Discount rule validation catch rate | 100% | 100% (all invalid rules rejected) |
| Cascading delete enforcement | 100% | 100% (all parent-child guards active) |

---

## 10. Companion Documentation

| Document | Focus |
|---|---|
| [ER_DIAGRAM.md](ER_DIAGRAM.md) | Complete table, column, index, and relationship reference |
| [PRICING_CALCULATION.md](PRICING_CALCULATION.md) | Pricing formulas, tier mechanics, discount prompt flows |
| [DISCOUNT_PROMOTION_PROMPT.md](DISCOUNT_PROMOTION_PROMPT.md) | Discount prompt authoring, scope hierarchy, AI integration |
| [HOSPITALITY_BUSINESS_GUIDE.md](HOSPITALITY_BUSINESS_GUIDE.md) | How RFQ core serves hospitality workloads |
| [HOSPITALITY_QUICK_START.md](HOSPITALITY_QUICK_START.md) | Step-by-step hospitality product setup |
| [HOSPITALITY_BUSINESS_GAP_PLAN.md](HOSPITALITY_BUSINESS_GAP_PLAN.md) | Implementation status, remaining gaps, rollout plan |
| [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) | Roadmap, architecture decisions, MCP integration |
| [TEST_DATA_PREPARATION.md](TEST_DATA_PREPARATION.md) | Seed data recipes, dependency order, troubleshooting |