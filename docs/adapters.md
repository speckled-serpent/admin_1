# Adapters

A fixture adapter returns records from a local file. Sales data set to Fake uses `fixture.revenue` on `fixtures/acme_notes_charges.json`. The revenue route makes that choice from the panel's data source. It does not look up a `project_sources` row.

## Interfaces

Defined in `backend/app/adapters/types.py`:

| Protocol | Method | Record |
| --- | --- | --- |
| `RevenueAdapter` | `list_charges()` | `Charge` |
| `CostAdapter` | `list_cost_items()` | `CostItem` |
| `HealthAdapter` | `list_pings()` | `HealthPing` |

An adapter instance is already bound to one fixture file. Methods take no project id. The service passes an absolute path into the constructor.

Registered keys today:

| Key | Class | Fixture shape | Wired through the API |
| --- | --- | --- | --- |
| `fixture.revenue` | `FixtureRevenueAdapter` | `{ "data": [ charge, ... ] }` | Yes, when Sales data is Fake |
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
| `refunded` | bool | Stored as given. The adapter does not check that `true` means a full refund |
| `created` | int | Non-negative integer. The adapter does not check a timezone |

Optional: `description`, `customer`. Extra keys (for example `object` or `paid`) are ignored. A record that breaks these rules raises `FixtureError`. The adapter does not skip bad rows or invent replacement values. Tolerating partial data is planned.

`succeeded` charges count toward gross even when they are fully refunded. The refund is subtracted via `amount_refunded`, so a full refund contributes zero to net and still appears in gross. That is deliberate.

## Cost and health records

Cost items: `id`, `vendor`, `category`, `description`, `amount` (minor units, `>= 0`), `currency` (non-empty string, stored lowercase), `incurred_on` (non-empty string). Fixture files use `YYYY-MM-DD`. The adapter does not parse the date.

Health pings: `id`, `checked_at` (non-empty string), `status` (`up`, `down`, or `degraded`), `latency_ms` (non-negative int or null), `region` (non-empty string). Fixture files use an ISO-8601 `checked_at`. The adapter does not parse the timestamp.

Seeded files:

- `backend/fixtures/acme_notes_charges.json`
- `backend/fixtures/acme_notes_costs.json`
- `backend/fixtures/acme_notes_health.json`

The charges file is what the revenue route reads when Sales data is Fake. The default seed does not create a project.

## How to add a source

1. Add a JSON fixture under `backend/fixtures/`. Use an invented project name (Acme Notes, Lumen, Orbit, or another fictional name). Do not name a real product.
2. Implement the matching protocol in `backend/app/adapters/`. Read the file. Do not import an HTTP client, open a socket, or read a remote secret.
3. Register a new `adapter_key` in `backend/app/adapters/registry.py`. Keep fixture readers and other readers in separate maps per kind.
4. Resolve that adapter from the panel's data source, the way Sales data resolves `fixture.revenue` when its mode is Fake. Do not require a hand-inserted `project_sources` row.
5. Add a service function that returns an explicit result. Do not fold several projects into one total unless the task is the rollup task.
6. Add a protected route under `/api/projects/{slug}/...`.
7. Add a page or a section that renders that payload, still talking only to `/api`.
8. Add tests that go through create or panel settings, or that point at the fixture file. Tests must pass with outbound network disabled (see [testing.md](testing.md)).

A second revenue adapter and partial-data handling are planned. See [roadmap.md](roadmap.md).

Pull connectors that call the network are a separate path. See [connectors.md](connectors.md).
