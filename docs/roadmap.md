# Roadmap

This repository is a skeleton. The pieces below are named so later tasks have a place to land. They are not implemented.

## Left undone on purpose

### A second source adapter

There is one concrete reader per kind (`fixture.revenue`, `fixture.costs`, `fixture.health`). A later task should add another adapter: its own key, its own fixtures, and behavior for bad or partial records (missing fields, unknown status, truncated files). That includes tests. Do not weaken the current adapters into silent skip-bad-rows behavior as a shortcut.

Cost and health fakes already read `acme_notes_costs.json` and `acme_notes_health.json`. They are not bound in the seed, and they have no service, route, or page. Wiring those two fakes through the API is separate from adding a second adapter implementation.

### Cross-project rollups

The dashboard asks for one project's revenue. It does not total across projects, filter by a date range, or convert currency. `MixedCurrencyError` is the current response when one project's succeeded charges disagree on currency.

Later work can add rollups for revenue, costs, and uptime. Likely shape: a service that takes an explicit set of project slugs and a date range, still using integer minor units, and a documented conversion step if more than one currency is allowed. Invented project names only (Lumen and Orbit are reserved examples). Do not pull in a live rates service.

### Alert rules and a local outbox

No rules engine, no notification table. A later task can add an outbox table (via Alembic) and a local evaluator that writes rows when a rule matches. Delivery stays on the machine. No email or chat provider.

## Also not in this skeleton

- Signup, password reset, and more than the seeded dev user.
- Editing projects or source bindings in the UI.
- Background workers and scheduled polls.
- Production hosting, containers, or a reverse proxy. Local uvicorn and Vite are the supported run.
