# Phase 4 approved UI to API inventory

Final inventory after Phase 4. `DONE` means the approved UI reads or mutates the
typed workspace-scoped API. `BLOCKED` is rendered visibly and the related
control is disabled. `INTENTIONAL` is deterministic/local product behavior that
is not presented as provider-connected or AI-generated data.

| Screen | Current data source | Target API | Status |
|---|---|---|---|
| Mobile / Overview | REAL | `GET /api/bootstrap`, `GET /api/dashboard/overview` | DONE; chart, KPI, category split and attention share one response |
| Mobile / Analytics | REAL | `GET /api/analytics/revenue` | DONE; presets/custom dates, empty/error states |
| Mobile / Revenue detail | REAL | `GET /api/analytics/revenue` | DONE |
| Mobile / Revenue category split (formerly Traffic) | REAL | `GET /api/dashboard/overview` | DONE; relabeled because backend groups by category, not traffic source |
| Mobile / Users detail | none | No user-event API | BLOCKED |
| Mobile / Conversion | DERIVED | `GET /api/analytics/funnel` | INTENTIONAL; order-derived funnel disclosed below |
| Mobile / Insights | REAL local records | `GET /api/insights` | DONE; no AI/provider claim |
| Mobile / Insight detail route | none | No detail endpoint | BLOCKED; list item modal uses the fetched record only |
| Mobile / Alerts | REAL | `GET /api/alerts`, `PATCH /api/alerts/{id}/read` | DONE |
| Mobile / Alert detail route | none | No detail endpoint | BLOCKED; list item modal uses the fetched record only |
| Mobile / Reports | REAL | `GET/POST /api/reports` | DONE |
| Mobile / Report detail/export | none | No detail/export endpoint | BLOCKED |
| Mobile / Saved Views | REAL read-only | `GET /api/saved-views` | DONE |
| Mobile / Data Sources | REAL | `GET /api/data-sources` | DONE |
| Mobile / Add Source + Import history | REAL | `/api/ingestion/*` | DONE; history supports pagination/search/filter/sort |
| Mobile / Notifications | none | No notification API | BLOCKED |
| Mobile / Global Search | REAL | resource list search endpoints | DONE; stale searches cancelled |
| Mobile / Advanced Filter | REAL/PARTIAL | analytics date parameters | DONE for date range; source/channel/device explicitly BLOCKED |
| Mobile / Profile + edit | REAL | `GET/PUT /api/profile` | DONE |
| Mobile / Account | REAL | `GET /api/profile` | DONE |
| Mobile / App Settings | none | No settings persistence API | BLOCKED |
| Mobile / Security detail | none | No 2FA/device-list API | BLOCKED; auth/session backend itself remains real |
| Mobile / Help/onboarding/UI map | static product copy | none required | INTENTIONAL content-only UI |
| Desktop / Overview | REAL | `GET /api/bootstrap`, `GET /api/dashboard/overview` | DONE; campaign widget explicitly BLOCKED |
| Desktop / Realtime | REAL | `GET /api/sales/realtime` | DONE |
| Desktop / Funnel | DERIVED | `GET /api/analytics/funnel` | INTENTIONAL |
| Desktop / Cohort | DETERMINISTIC | `GET /api/analytics/cohort` | INTENTIONAL |
| Desktop / Revenue | REAL | `GET /api/analytics/revenue` | DONE; presets/custom dates |
| Desktop / Insights | REAL local records | `GET /api/insights` | DONE |
| Desktop / Alerts | REAL | `GET/POST /api/alerts` | DONE |
| Desktop / Reports | REAL | `GET/POST /api/reports` | DONE |
| Desktop / Data Sources + Import history | REAL | `GET /api/data-sources`, `GET /api/ingestion/jobs` | DONE |
| Desktop / Members | REAL | workspace member/invitation APIs | DONE |
| Desktop / Workspace search | REAL | reports/views/sources search endpoints | DONE |
| Desktop / Dashboards + Builder | none | No dashboard persistence API | BLOCKED |
| Desktop / Segmentation/Journey/Retention | none | No event-model APIs | BLOCKED |
| Desktop / Forecast | legacy utility only | No persisted forecast workflow | BLOCKED |
| Desktop / Events/Quality/Export/Activity/Settings | none | No corresponding product APIs | BLOCKED |

## Exact remaining mock/synthetic inventory

No connected screen silently uses frontend business-data fixtures after its API
request completes. The only remaining synthetic analytics are:

1. `/api/analytics/funnel`: deterministic stage multipliers derived from real
   workspace order counts. It is not event-level funnel data.
2. `/api/analytics/cohort`: deterministic demo matrix. It is not computed from
   workspace retention events.
3. Seed records created only when `SEED_DEMO_DATA=true`: insights, alerts,
   reports, saved views and legacy source metadata. Production defaults do not
   enable this flag.
4. Static HTML numeric values remain only as the approved no-JavaScript design
   shell. Authenticated runtime immediately replaces them with loading state and
   then API success/empty/error state; they are never used as a failure fallback.
5. Onboarding, help text, illustration geometry, skeleton geometry and chart
   styling are static presentation content, not analytics data.

All capabilities without a truthful backend are displayed as `BLOCKED` or have
their controls disabled. The frontend does not fabricate success for them.
