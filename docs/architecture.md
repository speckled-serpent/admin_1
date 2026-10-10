# Architecture

admin_1 is an admin panel that consolidates multiple projects into one service. Pages read SQLite and local fixture files. They do not call CDNs, font hosts, or telemetry. An HTTP health connection performs one GET when a check runs. That result is stored, and System health renders the stored status.

FastAPI's built-in telemetry is turned off (`tracing`, `metrics`, `logs`, and exporter auto-configuration). Do not point the process at an OTLP endpoint.

The process split is fixed:

- `backend/` is a FastAPI app. SQLite holds users, sessions, projects, and source bindings. Alembic owns the schema.
- `frontend/` is a React + Vite + TypeScript client. The dev server proxies `/api` to the backend, so the browser talks only to localhost.
- `backend/fixtures/` holds JSON that stands in for outside systems. Adapters read those files. Fixture reads do not open a socket. The HTTP health check is the request that does: one GET through an injectable client.

## Layers

```
browser
  -> frontend pages (login, dashboard)
    -> /api routes          backend/app/api
      -> services           backend/app/services
        -> adapters         backend/app/adapters
          -> fixtures       backend/fixtures
        -> SQLite           users, sessions, projects, panels, connections, ingest_snapshots
```

Routers authenticate the caller, validate the payload, and map domain errors to HTTP status codes. They do not total money and they do not open fixture files.

Services load a project and the panel's data source, build the adapter that source selects, and apply accounting rules.

Adapters turn one local fixture into typed records. They do not know about HTTP, sessions, or summaries.

## What lives in SQLite

| Table | Role |
| --- | --- |
| `users` | Local username and password hash |
| `sessions` | SHA-256 of a bearer token, plus expiry |
| `projects` | A software project (`slug`, display `name`) |
| `project_sources` | Optional adapter binding per project per kind. Create, seed, and panel settings do not write it. Sales data on Fake does not read it |
| `project_panels` | Panel keys the operator turned on for a project |
| `connections` | A named Push or HTTP health source. Credentials live here |
| `connection_api_keys` | SHA-256 of a push connection's ingest key |
| `panel_data_sources` | Fake, or a `connection_id` the panel reads |
| `ingest_snapshots` | Latest accepted push section for one connection and kind |

`project_sources.kind` is `revenue`, `costs`, or `health`. A project has at most one row per kind. The row stores an `adapter_key` (for example `fixture.revenue`) and a `fixture_path` relative to `backend/`. The running Sales data path does not use that row.

Charge records, cost lines, and health pings from fixture files are not copied into SQLite. The fixture file is the source of truth, so a bad parse shows up in the adapter instead of hiding in a cache table. Accepted push sections are stored: each one is a row in `ingest_snapshots`, keyed by connection and kind (`health`, `users`, `revenue`, `costs`).

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

## Sales data and system health

`GET /api/projects/{slug}/revenue` returns the summary plus every charge, newest first, when that project's Sales data panel is set to Fake. It reads `fixtures/acme_notes_charges.json` through `fixture.revenue`. A missing Sales data panel, or a Sales data panel that is not Fake, responds with 404. The default seed does not create a project.

`DELETE /api/projects/{slug}` removes the project. Panels, sources, connections, API keys, and snapshots go with it. `DELETE /api/projects/{slug}/panels/{panel}` removes that panel only.

Push ingest stores every accepted section in `ingest_snapshots`. System health renders the latest `health` status from that snapshot or from an HTTP health check. `users`, `revenue`, and `costs` are stored and are not rendered. The page reads those stored rows. It does not call the network to draw them. See [connectors.md](connectors.md).

Cost and health fixture adapters read their JSON files. They have no service, route, or page. See [roadmap.md](roadmap.md).

## Boot

Defaults are enough. `DATABASE_URL` defaults to `sqlite:///./data/admin.db`, resolved from `backend/` no matter the current working directory. Copy `backend/.env.example` to `backend/.env` only to override them.

Startup does not seed and does not migrate. Those are explicit commands so tests can build their own databases.
