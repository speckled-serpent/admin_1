# Adapters

A project does not talk to an outside system directly. It has a `project_sources` row, and that row names an adapter. The adapter's only job is to return records from local data.

## Interfaces

Defined in `backend/app/adapters/types.py`:

| Protocol | Method | Record |
| --- | --- | --- |
| `RevenueAdapter` | `list_charges()` | `Charge` |
| `CostAdapter` | `list_cost_items()` | `CostItem` |
| `HealthAdapter` | `list_pings()` | `HealthPing` |

An adapter instance is already bound to one project source. Methods take no project id. The service resolves `fixture_path` and passes an absolute path into the constructor.

Registered keys today:

| Key | Class | Fixture shape | Wired through the API |
| --- | --- | --- | --- |
| `fixture.revenue` | `FixtureRevenueAdapter` | `{ "data": [ charge, ... ] }` | Yes, for Acme Notes |
| `fixture.costs` | `FixtureCostAdapter` | `{ "items": [ cost, ... ] }` | No |
| `fixture.health` | `FixtureHealthAdapter` | `{ "pings": [ ping, ... ] }` | No |

The registry lives in `backend/app/adapters/registry.py`. Paths must resolve inside `backend/fixtures/`. A path that escapes that directory is rejected.

## Charge records

Fixtures use the shape of a card-processor charge list. Fields the adapter requires:

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | Stable id |
| `amount` | int | Minor units, `>= 0` |
| `amount_refunded` | int | Minor units, from `0` through `amount` |
| `currency` | string | 3-letter code, stored lowercase |
| `status` | string | `succeeded`, `pending`, or `failed` |
| `refunded` | bool | `true` only when the charge was fully refunded |
| `created` | int | Unix seconds, UTC |

Optional: `description`, `customer`. Extra keys (for example `object` or `paid`) are ignored. A record that breaks these rules raises `FixtureError`. The adapter does not skip bad rows or invent replacement values. Tolerating partial data is left for a later task.

`succeeded` charges count toward gross even when they are fully refunded. The refund is subtracted via `amount_refunded`, so a full refund contributes zero to net and still appears in gross. That is deliberate.

## Cost and health records

Cost items: `id`, `vendor`, `category`, `description`, `amount` (minor units), `currency`, `incurred_on` (`YYYY-MM-DD`).

Health pings: `id`, `checked_at` (ISO-8601), `status` (`up`, `down`, or `degraded`), `latency_ms` (int or null), `region`.

Seeded files:

- `backend/fixtures/acme_notes_charges.json`
- `backend/fixtures/acme_notes_costs.json`
- `backend/fixtures/acme_notes_health.json`

Only the charges file is referenced by a `project_sources` row.

## How to add a source

Do this when a future task asks for another adapter. The skeleton stops after the steps that are already done for revenue.

1. Add a JSON fixture under `backend/fixtures/`. Use an invented project name (Acme Notes, Lumen, Orbit, or another fictional name). Do not name a real product.
2. Implement the matching protocol in `backend/app/adapters/`. Read the file. Do not import an HTTP client, open a socket, or read a remote secret.
3. Register a new `adapter_key` in `backend/app/adapters/registry.py`. Keep fixture readers and any future readers in separate maps per kind.
4. Insert a `project_sources` row (seed or migration) with `kind`, `adapter_key`, and `fixture_path`.
5. Add a service function that loads that binding and returns an explicit result. Do not fold several projects into one total unless the task is the rollup task.
6. Add a protected route under `/api/projects/{slug}/...`.
7. Add a page or a section that renders that payload, still talking only to `/api`.
8. Add tests that point at the fixture file or a temp database. Tests must pass with outbound network disabled (see [testing.md](testing.md)).

A second revenue adapter, partial-data handling, and the tests for those cases are intentionally not in this tree. See [roadmap.md](roadmap.md).
