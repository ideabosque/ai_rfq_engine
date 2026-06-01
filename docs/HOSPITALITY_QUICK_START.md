# Hospitality Quick Start

> **Status**: Working-tree capability guide
> **Reviewed**: 2026-05-24
> **Readiness boundary**: Durable local holds are implemented. Complete DynamoDB contention validation and configure expiry invocation before production rollout.

## What Is Supported

The RFQ core supports hospitality quote lines without a separate hospitality engine:

| Need | Model surface |
|---|---|
| Dated inventory | `ProviderItemBatch.service_start_at`, `service_end_at` |
| Capacity evaluation | `ProviderItemBatch.in_stock`, `availability_qty`; `ProviderItem.availability_mode` |
| Participant pricing | `Item.pricing_mode="per_pax_type"` and `QuoteItem.pax_breakdown` |
| Accommodation pricing | `Item.pricing_mode="occupancy"` with tier `base_occupancy` and `extra_pax_surcharges` |
| Reusable package template | `BundleModel` plus `BundleComponentModel` |
| Itinerary grouping | `Request.bundle_uuid`; `QuoteItem.bundle_uuid`, `bundle_label`, `bundle_component_uuid` |
| Display-currency quote | `Quote.currency`, `display_currency`, `fx_rate`, `fx_rate_locked_at` |
| Quoted terms | `CancellationPolicyModel` linked from `ProviderItemBatch` |
| External discovery | `inquire_catalog` through KGE and `ItemCatalogRefModel` mapping |

## Configure A Service-Dated Product

1. Create an `Item` with the required pricing mode:
   - `unit` for unit-priced extras or legacy goods.
   - `per_pax_type` for admissions, transfers, meals, or delegates.
   - `occupancy` for room-night pricing with included guests and surcharges.
2. Create a `ProviderItem` for the supplier offering.
   - Use `availability_mode="none"` for non-reservable quoting.
   - Use `check_only` for local availability gating.
   - Use `require_hold` for quantified local capacity that must be reserved through a durable hold.
3. Create a `ProviderItemBatch` with a service window:

```text
service_start_at < requested_service_end
and service_end_at > requested_service_start
```

For capacity-constrained products, set `in_stock=true` and `availability_qty` to the visible quantity. A null `availability_qty` is treated as unquantified capacity.

## Configure Pricing

For `per_pax_type`, define one active `ItemPriceTier` per supported category and pass total quantity equal to the participant count:

```json
{
  "pricing_mode": "per_pax_type",
  "qty": 3,
  "pax_breakdown": {"adult": 2, "child": 1}
}
```

For `occupancy`, define an active base tier with included occupancy and surcharge maps:

```json
{
  "pricing_mode": "occupancy",
  "qty": 3,
  "pax_breakdown": {"adult": 2, "child": 1},
  "base_occupancy": {"adult": 2},
  "extra_pax_surcharges": {"child": 25.0}
}
```

Here `qty` is the number of billable units, such as room-nights. With a base nightly price of `200.0`, this example prices at `(200 + 25) * 3 = 675`.

## Configure A Reusable Bundle

Use bundles when the package is reusable or selectable, not just when quote lines need a visual group.

1. Create a `BundleModel` for the package: `bundle_uuid`, `bundle_code`, `bundle_name`, `bundle_type`, optional `extra`, and `status`.
2. Create one `BundleComponentModel` per default component: `bundle_component_uuid`, `bundle_uuid`, `item_uuid`, optional `provider_item_uuid`, `component_role`, `required`, `default_qty`, and `sort_order`.
3. Set `Request.bundle_uuid` when a customer request is for that package.
4. When creating priced quote lines, keep each component as an independent `QuoteItem` and set `bundle_uuid`, `bundle_label`, and optionally `bundle_component_uuid`.

Do not model a single priced parent bundle line unless the commercial contract is actually sold as one inseparable item. Independent quote lines preserve provider attribution, capacity holds, currencies, and cancellation terms.

## Terms, Currency, And Catalog

- Link a `CancellationPolicyModel` from `ProviderItemBatch.cancellation_policy_uuid` to generate a quote-line cancellation snapshot.
- Set a quote native currency, display currency, and locked FX rate to store `subtotal_native` while presenting converted `subtotal`.
- Use `inquire_catalog` for KGE text search, then map returned `namespace` and `node_id` values through `ItemCatalogRefModel` to internal item records.
- Direct KGE node-by-ID inquiry is not implemented by this engine.

## Production Gates

`require_hold` now persists an `AvailabilityHoldModel` row and transactionally reserves quantified `availability_qty`; unknown tokens fail closed, while release and explicit expiry restore capacity exactly once. The cancellation snapshot key is engine-owned and caller substitution is rejected.

Before production rollout:

1. Run DynamoDB-backed concurrent acquisition and lifecycle tests against the deployed `are-availability_holds` table.
2. Configure expiry invocation for abandoned `held` rows so timed-out capacity is restored.
3. Define downstream refund behavior against the stored cancellation snapshot.

The tracked exit criteria and rollout order are in [HOSPITALITY_BUSINESS_GAP_PLAN.md](HOSPITALITY_BUSINESS_GAP_PLAN.md).
