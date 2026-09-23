# Nexus Analytics API contract

## Base conventions

- Current API paths use `/api/...`; legacy analytics utilities `/forecast` and `/cluster` remain temporarily supported.
- JSON is UTF-8. Request bodies with unknown fields are rejected.
- All `/api` routes except authentication entry points and `/health` require authentication. The same-origin UI uses secure cookies; API clients may send `Authorization: Bearer <access-token>`.
- Cookie-authenticated unsafe requests (`POST`, `PUT`, `PATCH`, `DELETE`) require `X-CSRF-Token` matching the readable `nexus_csrf_token` cookie.
- Timestamps are ISO 8601 strings. Analytics date ranges are inclusive and expressed as `YYYY-MM-DD`.
- Database IDs are positive integers. External order/customer IDs remain strings.
- Money is returned as JSON numbers in VND; formatting belongs to the frontend.

## Response envelope

Success:

```json
{"success": true, "data": {}, "meta": {}}
```

Error:

```json
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": []}}
```

During the v1 compatibility window, existing successful endpoints also retain legacy fields such as `status`, `overview`, `forecast`, `clusters`, or analytics fields at the top level. New frontend code must prefer `success`, `data`, and `error`.

Stable error codes: `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `INTERNAL_ERROR`. `NOT_IMPLEMENTED` is used by the intentionally disabled Phase 1 chat endpoint.

Production errors never contain stack traces, SQL, file paths, secrets, or raw provider errors.

## Query conventions

- `days`: integer from 1 through 365.
- `date_from` and `date_to`: inclusive `YYYY-MM-DD`; both are required together and the range cannot exceed 365 days.
- `page`: positive integer, default `1`.
- `page_size`: integer from 1 through 100, default `20`.
- List metadata is returned as `meta.pagination`: `page`, `page_size`, `total`, `total_pages`.
- `search`: literal case-insensitive search up to 200 characters. `%`, `_` and `\\` are escaped and are not treated as SQL wildcards.
- `sort_by`: endpoint-specific allowlisted column; arbitrary SQL identifiers are rejected.
- `sort_order`: `asc` or `desc`.
- `unread_only`: boolean (`true` or `false`).
- Resource filters are endpoint-specific: report `status/report_type`, alert `severity/unread_only`, insight `severity/insight_type`, source `status/source_type/health_status`, saved view `view_type/is_favorite`, import job `status/file_type`.

List endpoints supporting this contract: `/api/insights`, `/api/alerts`,
`/api/reports`, `/api/data-sources`, `/api/saved-views`, and
`/api/ingestion/jobs`.

## Major endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service and environment status |
| POST | `/api/auth/register` | Create user, first workspace and OWNER membership |
| POST | `/api/auth/login` | Authenticate and create a revocable session |
| POST | `/api/auth/refresh` | Rotate the refresh token and renew access |
| POST | `/api/auth/logout` | Revoke the current session and clear cookies |
| GET | `/api/auth/session` | Current user, active workspace, role and memberships |
| POST | `/api/auth/forgot-password` | Generic password recovery response |
| POST | `/api/auth/reset-password` | Consume reset token and revoke all user sessions |
| GET | `/api/workspaces` | List current user's workspaces |
| POST | `/api/workspaces/switch` | Switch active workspace and rotate the session |
| GET | `/api/workspaces/current/members` | List members (ADMIN+) |
| POST | `/api/workspaces/current/invitations` | Create invitation (ADMIN+) |
| POST | `/api/workspaces/invitations/accept` | Accept invitation matching authenticated email |
| PATCH | `/api/workspaces/current/members/{user_id}` | Change non-owner role (OWNER only) |
| GET | `/api/bootstrap` | Overview, insights, alerts and profile for initial UI load |
| GET | `/api/dashboard/overview` | KPI summary, trend, category revenue split (legacy field name `traffic_sources`) and attention items |
| GET | `/api/analytics/revenue` | Daily, regional and category revenue |
| GET | `/api/analytics/funnel` | Funnel completion and step counts |
| GET | `/api/analytics/cohort` | Current deterministic cohort demo dataset |
| GET | `/api/sales/realtime` | Most recent order records |
| GET | `/api/anomalies` | Current order anomaly check |
| GET | `/api/insights` | Insight list |
| GET/POST | `/api/alerts` | List or create alerts |
| PATCH | `/api/alerts/{alert_id}/read` | Mark an alert as read |
| GET/POST | `/api/reports` | List or create report metadata |
| GET/POST | `/api/data-sources` | List or create source metadata |
| GET | `/api/saved-views` | Saved analysis views |
| GET/PUT | `/api/profile` | Read or update the authenticated user's profile |
| POST | `/forecast` | Legacy local linear forecast utility |
| POST | `/cluster` | Legacy rule-based customer grouping utility |
| POST | `/api/chat` | Still disabled; returns `501 NOT_IMPLEMENTED` and no provider is connected |

## File ingestion endpoints

All ingestion endpoints require an authenticated active workspace. Upload,
preview, import, cancellation, history and failure details require `ADMIN` or
`OWNER` and are scoped server-side to that workspace.

| Method | Path | Purpose | Resulting state |
|---|---|---|---|
| GET | `/api/ingestion/schema` | Canonical fields and supported types | unchanged |
| POST | `/api/ingestion/uploads` | Stream a multipart CSV/XLSX file to server-owned storage | `UPLOADED` |
| POST | `/api/ingestion/jobs/{id}/preview` | Inspect sheets, columns, types and first N rows | `PREVIEWED` or `FAILED` |
| POST | `/api/ingestion/jobs/{id}/import` | Validate mapping/rows and synchronously normalize valid records | `COMPLETED` or `FAILED` |
| GET | `/api/ingestion/jobs` | Workspace import history | unchanged |
| GET | `/api/ingestion/jobs/{id}` | Durable job metadata and counts | unchanged |
| GET | `/api/ingestion/jobs/{id}/errors` | Paginated row/field/code errors | unchanged |
| POST | `/api/ingestion/jobs/{id}/cancel` | Cancel before validation begins | `CANCELLED` |
| GET | `/api/ingestion/sources/{id}/history` | FILE_UPLOAD source and its imports | unchanged |

The browser never submits or receives a server storage path. Processing is
currently synchronous, so responses expose real states and final counts rather
than fabricated percentage progress. Ingestion-specific error codes include
`EMPTY_FILE`, `FILE_TOO_LARGE`, `UNSUPPORTED_EXTENSION`, `UNSUPPORTED_MIME_TYPE`,
`MALFORMED_CSV`, `MALFORMED_XLSX`, `MISSING_REQUIRED_MAPPING`,
`INVALID_NUMBER`, `INVALID_DATE`, and `DUPLICATE_IMPORT`.

## Versioning policy

The current contract is treated as v1 without a URL prefix to preserve compatibility. Breaking changes require either a new `/api/v2` path or a documented compatibility period with legacy fields.

## Authorization matrix

| Capability | VIEWER | ANALYST | ADMIN | OWNER |
|---|---:|---:|---:|---:|
| Read workspace analytics/resources | yes | yes | yes | yes |
| Create reports and alerts | no | yes | yes | yes |
| Create data-source metadata | no | no | yes | yes |
| Upload/preview/import files | no | no | yes | yes |
| List/invite members | no | no | yes | yes |
| Change member roles | no | no | no | yes |

Every resource query is scoped by the active `workspace_id` derived from the server-side session. Client-supplied workspace IDs are never trusted as authorization.
# Phase 5 analytics endpoints

All analytics endpoints derive the workspace from the authenticated session. Date ranges are inclusive UTC dates and `date_from`/`date_to` must be supplied together.

| Method | Endpoint | Minimum role | Result |
|---|---|---|---|
| GET | `/api/analytics/revenue` | VIEWER | Revenue/AOV/ARPU/users/sessions/conversion, previous period, daily series and dimensions. |
| GET | `/api/analytics/funnel` | VIEWER | Ordered session funnel; optional comma-separated `steps`. |
| GET | `/api/analytics/retention` | VIEWER | Exact D1/D7/D14/D30 signup retention. |
| GET | `/api/analytics/cohort` | VIEWER | Monday-anchored signup cohort W0-W7 matrix. |
| GET | `/api/analytics/segments` | VIEWER | Saved server-side segments with current counts. |
| POST | `/api/analytics/segments/preview` | ANALYST + CSRF | Validate and calculate allowlisted rules without saving. |
| POST | `/api/analytics/segments` | ANALYST + CSRF | Save an allowlisted segment definition. |
| GET | `/api/analytics/anomalies` | VIEWER | Deterministic daily-revenue detections and expected ranges. |
| GET | `/api/analytics/forecast?horizon=7` | VIEWER | Reproducible baseline forecast, holdout metrics, and uncertainty. |
| GET | `/api/analytics/insights/explanations` | VIEWER | Deterministic explanations over engine output; external AI disabled. |

Metric semantics and missing-identifier coverage behavior are normative in `docs/ANALYTICS_METRICS.md`.

# Phase 6 operational endpoints

| Method | Endpoint | Minimum role | Result |
|---|---|---|---|
| GET | `/health` | public | Liveness only. |
| GET | `/ready` | public | Database readiness. |
| GET | `/metrics` | public/internal network recommended | Prometheus text counters and latency gauge. |
| GET | `/api/notifications` | VIEWER | Workspace/user notifications. |
| POST | `/api/notifications` | ADMIN + CSRF | Idempotent notification creation. |
| POST | `/api/notifications/{id}/read` | VIEWER + CSRF | Mark an authorized notification read. |
| POST | `/api/exports` | ANALYST + CSRF | Create CSV/XLSX/PDF analytics-event export job. |
| GET | `/api/exports` | VIEWER | Workspace export history. |
| GET | `/api/exports/{id}` | VIEWER | Durable export status. |
| GET | `/api/exports/{id}/download` | VIEWER | Authorized completed file download. |
| GET | `/api/audit-logs` | ADMIN | Workspace audit records. |

Export status is one of `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`. Generated filenames and paths are server-owned.
# Staging operations additions (Phase 6B)

- `GET /health/live` — process liveness only; no dependency checks.
- `GET /health/ready` — HTTP 200 only when PostgreSQL, Redis (staging/
  production), and private object storage are healthy; otherwise HTTP 503 with
  per-dependency booleans.
- `POST /api/client-errors` — accepts a scrubbed frontend error message/page/
  component and forwards it to the configured staging error monitor.
- `POST /api/exports` — returns HTTP 202. In staging the response represents a
  durable RQ job; poll `GET /api/exports/{id}` until `COMPLETED` or `FAILED`.
- `GET /api/exports/{id}/download` — workspace-authorized download. S3 mode
  returns a short-lived HTTP 307 signed URL; it never exposes a permanent public
  object URL.
- `POST /api/ingestion/jobs/{id}/import` — local/test remains synchronous;
  staging/production returns `processing_mode: queued` and a durable job ID.
- `POST /api/notifications` — idempotent DB creation followed by durable delivery;
  repeated workspace/idempotency keys do not duplicate notifications.

Queue submission failures use HTTP 503. Authorization and workspace scoping are
evaluated before queueing; workers receive server-generated resource IDs and do
not trust client file paths.
