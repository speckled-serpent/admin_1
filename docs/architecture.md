# Architecture

admin_1 is a local-first panel for one person's software projects. It shows revenue for a project from data that already lives on disk. It does not call external APIs, CDNs, font hosts, or telemetry.

FastAPI's built-in telemetry is turned off (`tracing`, `metrics`, `logs`, and exporter auto-configuration). Do not point the process at an OTLP endpoint.

The process split is fixed:

- `backend/` is a FastAPI app. SQLite holds users, sessions, projects, and source bindings. Alembic owns the schema.
- `frontend/` is a React + Vite + TypeScript client. The dev server proxies `/api` to the backend, so the browser talks only to localhost.
- `backend/fixtures/` holds JSON that stands in for outside systems. Adapters read those files. Nothing in the request path opens a socket to fetch them.

## Layers

```
browser
  -> frontend pages (login, dashboard)
    -> /api routes          backend/app/api
      -> services           backend/app/services
        -> adapters         backend/app/adapters
          -> fixtures       backend/fixtures
        -> SQLite           users, sessions, projects, project_sources
```

Routers authenticate the caller, validate the payload, and map domain errors to HTTP status codes. They do not total money and they do not open fixture files.

Services load a project and its source binding, build the adapter the binding names, and apply accounting rules.

Adapters turn one local fixture into typed records. They do not know about HTTP, sessions, or summaries.

## What lives in SQLite

| Table | Role |
| --- | --- |
| `users` | Local username and password hash |
| `sessions` | SHA-256 of a bearer token, plus expiry |
| `projects` | A software project (`slug`, display `name`) |
| `project_sources` | One adapter binding per project per kind |
| `project_panels` | Panel keys the operator turned on for a project. No data source is attached |

Kinds are `revenue`, `costs`, and `health`. A project has at most one row per kind. The row stores an `adapter_key` (for example `fixture.revenue`) and a `fixture_path` relative to `backend/`.

Charge records, cost lines, and health pings are not copied into SQLite. The fixture file is the source of truth, so a bad parse shows up in the adapter instead of hiding in a cache table.

## Money

Amounts are integers in minor units all the way through the API. `usd` 15900 means 159.00 dollars. Currency codes are lowercase ISO-4217. The API never returns a float for money.

The one revenue summary uses these rules:

- Gross is the sum of `amount` on charges with status `succeeded`.
- Refunded is the sum of `amount_refunded` on those same charges, including partial refunds and full refunds.
- Net is gross minus refunded.
- Pending and failed charges are listed and left out of the totals.
- If succeeded charges use more than one currency, the service refuses. Conversion is not implemented.

The dashboard divides by 100 for display and formats with `en-US`. That matches the seeded `usd` fixture. It is a display choice, not a second accounting rule.

## Auth

Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 rounds) and a random salt. The stored form is `pbkdf2_sha256$<rounds>$<salt hex>$<digest hex>`.

Login returns a random bearer token. Only the SHA-256 of that token is stored. Protected routes require `Authorization: Bearer <token>`. Missing or expired tokens get `401`.

The seed creates a single local user. There is no signup page and no remote identity provider.

## The one wired path

`GET /api/projects/{slug}/revenue` reads a `project_sources` row for that project and returns the summary plus every charge, newest first. The default seed does not insert a project or that row. Tests bind `fixture.revenue` to `fixtures/acme_notes_charges.json` when they need the numbers.

`DELETE /api/projects/{slug}` removes the project. Panels and sources go with it.

Cost and health adapters and their fixture files exist so a later task can bind them. They have no service, route, or page yet. See [roadmap.md](roadmap.md).

## Boot

Defaults are enough. `DATABASE_URL` defaults to `sqlite:///./data/admin.db`, resolved from `backend/` no matter the current working directory. Copy `backend/.env.example` to `backend/.env` only to override them.

Startup does not seed and does not migrate. Those are explicit commands so tests can build their own databases.
