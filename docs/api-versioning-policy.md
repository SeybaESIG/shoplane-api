# API Versioning & Deprecation Policy

## URL scheme

All endpoints live under a versioned prefix:

```
/api/v{N}/...
```

The current production version is **v1**.

## When to create a new version

A new major version (`v2`, `v3`, …) is required when a change **breaks** an
existing client contract. Breaking changes include:

- Removing or renaming an endpoint
- Removing or renaming a field in a request or response body
- Changing a field's type (e.g. `string` → `integer`)
- Changing the meaning/semantics of a status code or error code
- Changing authentication requirements on a public endpoint
- Altering the response envelope structure

The following are **not** breaking and can ship inside the current version:

- Adding a new endpoint
- Adding an optional request field
- Adding a new field to a response body
- Adding a new query parameter for filtering/sorting
- Tightening server-side validation (stricter input rules)
- Bug fixes that align behavior with documented spec

## Lifecycle stages

Every API version moves through four stages:

| Stage | Duration | Behavior |
|---|---|---|
| **Active** | Indefinite | Full read + write access. Receives new features and bug fixes. |
| **Maintenance** | Begins when the next version reaches Active | Full read + write access. Receives security and critical bug fixes only. No new features. |
| **Read-only** | 3 months after Maintenance starts | All mutating endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) return `405 Method Not Allowed`. Read endpoints (`GET`, `HEAD`, `OPTIONS`) continue to work. |
| **Sunset** | 3 months after Read-only starts | All endpoints return `410 Gone` with a body pointing to the replacement version. The version is removed in the next release. |

**Total time from deprecation to removal: 6 months.**

```
v1 Active ──► v1 Maintenance ──► v1 Read-only ──► v1 Sunset ──► v1 Removed
                 │                  (3 months)      (3 months)
                 │
              v2 Active
```

## Signaling deprecation to clients

### Response headers

Once a version enters **Maintenance**, every response includes:

```http
Deprecation: true
Sunset: Sat, 01 Nov 2026 00:00:00 GMT
Link: </api/v2/>; rel="successor-version"
```

- `Deprecation` — signals clients that this version is deprecated (RFC 8594).
- `Sunset` — the date the version will stop responding (end of Sunset stage).
- `Link` — points to the replacement version.

### Endpoint-level deprecation

Individual endpoints can be deprecated ahead of a full version change.
Deprecated endpoints return the same headers and are documented as deprecated
in the OpenAPI schema via `@extend_schema(deprecated=True)`.

## Implementation checklist (when launching v2)

1. **Create the new URL module**
   - `shoplane/urls_v2.py` mounted at `path("api/v2/", include("shoplane.urls_v2"))`
   - v1 URLs remain untouched.

2. **Add deprecation middleware**
   - Intercept requests to `/api/v1/` and inject `Deprecation`, `Sunset`, and
     `Link` headers on every response.

3. **Enforce read-only stage**
   - A middleware or permission class checks the version's lifecycle stage.
   - During read-only: reject non-safe methods with `405`.
   - During sunset: reject all methods with `410` and a JSON body:
     ```json
     {
       "success": false,
       "message": "API v1 has been retired. Use /api/v2/ instead.",
       "errors": null,
       "code": "VERSION_SUNSET"
     }
     ```

4. **Update OpenAPI schema**
   - Mark all v1 endpoints as `deprecated: true` in drf-spectacular.
   - Add v2 schema generation.

5. **Communicate the timeline**
   - Changelog entry with exact dates for each stage.
   - Notification in API docs (Swagger UI banner or description).

## Version negotiation

This project uses **URL-path versioning only**. No header-based or
query-parameter versioning is supported. This keeps routing explicit and
cache-friendly.

Clients must update their base URL to migrate:

```
# Before
https://api.shoplane.ch/api/v1/products/

# After
https://api.shoplane.ch/api/v2/products/
```

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-03-21 | 6-month total sunset window (3+3) | Gives clients two clear milestones: read-only first, then full removal. Short enough to avoid maintaining dead code indefinitely. |
| 2026-03-21 | URL-path versioning only | Simplest to implement, debug, and cache. Header versioning adds complexity with no benefit at our scale. |
| 2026-03-21 | Read-only stage before full sunset | Allows clients that only consume data to keep working longer, reducing migration pressure. |
