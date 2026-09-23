# Nexus Analytics metric contracts

All timestamps are normalized to UTC for comparison. Date filters are inclusive. Every query is scoped by the authenticated `workspace_id`; client-supplied workspace IDs are never accepted as authorization.

## Canonical source fields

| Field | Required for | Definition |
|---|---|---|
| `event_id` | all modules | Unique inside a workspace. |
| `event_name` | all modules | Allowlisted application event name such as `signup`, `view_product`, `add_to_cart`, `begin_checkout`, `purchase`. |
| `occurred_at` | all modules | ISO-8601 timestamp interpreted in UTC. |
| `user_id` | active users, ARPU, retention, cohort, segments | Stable pseudonymous user identifier. |
| `session_id` | sessions, conversion, funnel | Stable session identifier. |
| `revenue` | revenue, AOV, ARPU, anomalies, forecast | Numeric amount attributed only when `event_name=purchase`. |
| `source`, `device`, `region`, `product` | breakdowns/segments | Optional dimensions; missing values are returned as `Unknown`. |

Legacy transaction imports that map `timestamp` and `revenue` are normalized as `purchase` events. This makes revenue exact, but cannot manufacture session, retention, or funnel coverage.

## Revenue metrics

- **Revenue:** sum of `revenue` for `purchase` events in the inclusive period.
- **Purchases:** count of `purchase` events.
- **Active users:** distinct non-null `user_id` with any event in the period.
- **Sessions:** distinct non-null `session_id` with any event in the period.
- **Conversion rate:** distinct sessions containing a purchase divided by distinct sessions containing any event, multiplied by 100.
- **AOV:** Revenue / Purchases. Zero when there are no purchases.
- **ARPU:** Revenue / Active users. Zero when there are no identified active users.
- **Previous-period change:** `(current - previous) / previous * 100` for an immediately preceding interval of identical duration. `null` means the previous value was zero while the current value was non-zero; infinity is not emitted.

Revenue supports daily series and breakdowns by source, device, region, and product.

## Funnel

Default ordered steps are `view_product → add_to_cart → begin_checkout → purchase`. The entity is a session. A session completes step N only if the matching event occurs after all prior matching steps. Repeated and out-of-order events do not advance the cursor.

- **Entered:** sessions completing step 1.
- **Completed:** sessions completing the final step.
- **Funnel conversion:** Completed / Entered × 100.
- **Step conversion:** sessions completing the step / sessions completing the previous step × 100.
- **Drop-off:** previous-step completions minus current-step completions.
- **Time between steps:** arithmetic mean seconds between matched ordered event timestamps; `null` when unavailable.

## Retention

The anchor is a user's earliest `signup` event. A user is retained on Day N only when that user has at least one non-signup event on the exact UTC calendar date `signup_date + N`. D1, D7, D14, and D30 are returned. A user is eligible only after the dataset has been observed through that target date; immature users are excluded from the denominator. Rate is retained users / eligible signed-up users × 100.

## Cohort

Users are assigned to the Monday-anchored UTC week of their earliest signup. W0 is 100% of the signup cohort. W1-W7 count users with at least one non-signup event in the corresponding Monday-anchored week. Each mature cell is active users / cohort size × 100; future, not-yet-observed cells are `null`, not misleading zero retention.

## Segments

Rules are evaluated server-side and are composable with `ALL` or `ANY`. Supported fields are `event_name`, `source`, `device`, `region`, `product`, and `revenue`. Supported operators are `eq`, `neq`, `in`, `gte`, and `lte`; revenue only accepts numeric comparison. Arbitrary SQL, JavaScript, or client expressions are never executed.

## Anomalies

Metric: daily revenue. For each day after seven historical observations, expected value is the population mean of the preceding seven observed days. Expected range is `max(0, mean - 3σ)` through `mean + 3σ`, with population standard deviation. A non-equal observation is anomalous when σ is zero. Severity is deterministic from standardized deviation: high ≥5, medium ≥3, otherwise low.

## Forecast

Baseline: ordinary least-squares linear regression over a contiguous daily-revenue series; missing calendar days are zero. At least eight days are required. The most recent `max(2, min(7, floor(n/5)))` days are held out and evaluated with MAE and RMSE. The production baseline is refit on the full history and emits up to 30 future days. The displayed uncertainty is estimate ±1.96 population standard deviations of residuals, floored at zero; it is explicitly a baseline interval, not a probabilistic guarantee.

## Insights

Numeric metrics always come from this deterministic engine. The current explanation endpoint is a transparent deterministic template over structured anomaly/forecast results (`external_ai_enabled=false`). A future language model may explain or suggest investigation paths only after consuming the structured results; it must never recalculate or invent metric values.
