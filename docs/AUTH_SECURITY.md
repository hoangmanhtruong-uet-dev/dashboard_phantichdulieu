# Authentication and workspace security

## Session design

- Access token: signed HS256 JWT, 15-minute default lifetime, HttpOnly `nexus_access_token` cookie.
- Refresh token: 256-bit opaque random value, 30-day default lifetime, HttpOnly `nexus_refresh_token` cookie. The database stores SHA-256 hashes only.
- Rotation: every successful refresh revokes the presented token and issues a replacement in the same family. Reusing a revoked token revokes its whole family and session.
- Session: server-side `auth_sessions` row contains the active workspace, expiry and revocation state. A valid JWT alone cannot bypass a revoked session.
- CSRF: unsafe cookie-authenticated requests require the double-submit `nexus_csrf_token` cookie/header pair.
- Passwords: `scrypt` with a unique 128-bit salt (`N=16384, r=8, p=1`). Policy requires 12–128 characters with uppercase, lowercase, number and symbol.

Cookies use `SameSite=Lax`, `Path=/`, and `Secure` in production. Sensitive long-lived credentials are never written to localStorage.

## Recovery and invalidation

Forgot-password responses are deliberately generic. Reset tokens are random, single-use, stored as hashes, and expire after 30 minutes. A successful reset revokes all sessions and refresh tokens for the user.

No email or OAuth provider is connected in Phase 2. In test mode only, forgot-password returns the reset token in response metadata. Workspace invitation tokens are returned only to an authenticated ADMIN/OWNER for manual delivery until a later provider phase.

## RBAC and tenant isolation

Roles are ordered `VIEWER < ANALYST < ADMIN < OWNER`. Reusable FastAPI dependencies enforce minimum roles server-side. The active workspace comes from a validated server session and membership join. Repository methods require that workspace ID in every query, update and insert.

Changing an alert/report/source ID cannot cross a workspace boundary: scoped updates return not found. Workspace switching first validates membership and then replaces the old session.

## Operational notes

- Production requires a unique `JWT_SECRET` of at least 32 characters.
- Login limiting permits five failures per IP/email pair in five minutes, then blocks for 15 minutes. It is process-local for the current single-instance architecture; a shared limiter is required before horizontal scaling.
- CORS credentials are disabled when development uses wildcard origins. Production must provide explicit origins.
- Safe redirects only accept root-relative paths and reject scheme-relative or backslash paths.
