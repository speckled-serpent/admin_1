# Connectors

How a panel gets data, and how to add another pull connector. The product intent is in [project.md](project.md). Fixture readers stay in [adapters.md](adapters.md).

The dashboard reads SQLite. It does not call the network while rendering. Push and pull both end as local rows.

## Three sources

| Mode | Who moves the data | Stored as |
| --- | --- | --- |
| Fake | Nobody. Sales data reads `fixtures/acme_notes_charges.json`. | The panel has no connection. Mode is `fake` on `panel_data_sources` |
| Push | A named connection's server sends a payload to admin_1. | `ingest_snapshots`, one row per connection and section |
| Pull | admin_1 sends a read-only request on a schedule. | The connection row, plus `last_status` on the panels that reference it |

A connection belongs to one project and has a name and a kind (`push` or `http-health`). Panels point at a connection with `panel_data_sources.connection_id`. Credentials live on the connection, not the panel. A panel defaults to Fake. System health may use an HTTP health connection. Other panels are Fake or Push only.

Nothing in these modes restarts, deploys, or otherwise changes a remote server.

## Push schema, version 1

`POST /api/ingest/{slug}` with `Authorization: Bearer <connection API key>`.

```json
{
  "schema_version": 1,
  "health": { "status": "up", "checked_at": "2026-10-10T12:00:00+00:00", "latency_ms": 20 },
  "users": { "daily_active": 4, "new": 1, "monthly_returning": 3, "as_of": "2026-10-10T12:00:00+00:00" },
  "revenue": {
    "currency": "usd",
    "gross_amount": 500,
    "refunded_amount": 100,
    "net_amount": 400,
    "as_of": "2026-10-10T12:00:00+00:00"
  },
  "costs": { "currency": "usd", "amount": 80, "as_of": "2026-10-10T12:00:00+00:00" }
}
```

Rules, enforced by `backend/app/ingest_schema.py`:

- `schema_version` must be `1`.
- At least one of `health`, `users`, `revenue`, and `costs` is required. Omitting a section is valid. A present section must include every field.
- `health.status` is `up`, `down`, or `degraded`. `latency_ms` is a non-negative integer or `null`.
- User counts are non-negative integers. Money fields are non-negative minor units. `net_amount` must equal `gross_amount` minus `refunded_amount`.
- Timestamps are ISO-8601. Currency is a 3-letter code, stored lowercase.
- Unknown fields are rejected. A bad payload writes nothing.

Each accepted section is stored in `ingest_snapshots`. A section is stamped onto panels of the matching type whose `connection_id` is the connection that authenticated the request: `health` on System health, `users` on User data, `revenue` on Sales data, `costs` on Consolidated costs. System health renders the stored health status. `users`, `revenue`, and `costs` are stored and are not rendered. Other panels can be set to Push, but this schema has no section for them, so they stay on Coming soon.

## Connection API keys

`connection_api_keys.key_hash` is the SHA-256 of the key for one push connection. The plaintext is returned once from generate or rotate and is not stored. A revoked key cannot ingest. A key is rejected on another project's ingest URL. A user session token is not an ingest key.

Generate fails when that connection already has an active key. Rotate revokes it and returns a new key. Revoke leaves the connection with no active key. HTTP health connections do not have API keys; they store an encrypted secret.

## HTTP health

HTTP health is the pull connector. It implements `HealthAdapter.list_pings()` in `backend/app/connectors/http_health.py`.

Settings on the connection: URL (`http` or `https`, no userinfo), expected status (100–599), timeout (1–30 seconds), and an optional secret. The secret is encrypted with Fernet before it is stored. Set `CONNECTOR_MASTER_KEY` or let the first save create `backend/data/connector.key` (gitignored). The API returns `has_secret`, never the secret. The panel settings page assigns System health to that connection.

The check is one GET. If a secret is set, the request adds `Authorization: Bearer <secret>`. Status `up` means the response status equals the expected status. Anything else, including a transport failure, is `down`.

`HttpClient` is a protocol in `backend/app/connectors/http.py`. The route depends on `get_http_client()`. Tests override that dependency with a fake. The urllib implementation lives in `urllib_client.py` and is not used by tests.

`poll_due_http_health` checks connections whose last receipt is older than 300 seconds. No thread in this process calls it. Test connection checks immediately and writes the status onto every panel that references the connection. A running scheduler is planned.

## How to add a connector

1. Add a read-only method on the existing adapter protocol, or reuse `list_pings`, `list_charges`, or `list_cost_items`. Do not add a method that changes the remote system.
2. Put the class under `backend/app/connectors/`. Take the network client in the constructor. Do not open a socket at import time.
3. Validate settings before calling the client. Reject schemes other than the ones the connector documents.
4. Encrypt any secret with `app.crypto` before writing it. Never return the plaintext from a later GET.
5. Persist the result in SQLite. The page reads that row.
6. Allow the new mode only on the panels it applies to (`allowed_modes` in `app/services/connections.py`).
7. Add an Alembic migration if the settings need columns or a table. Keep `tests/test_migrations.py` in agreement with the models.
8. Test with a fake transport. The suite blocks non-localhost sockets. Do not weaken that guard.
9. Add the mode to the panel settings page. Keep the panel body on Coming soon unless the new status is as small as the system-health line.

Card-processor connectors, cloud-cost connectors, a reporter SDK, scheduler hardening, rollups, and alerts are out of scope here. See [roadmap.md](roadmap.md).
