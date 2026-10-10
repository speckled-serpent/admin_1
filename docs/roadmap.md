# Roadmap

What is still missing, and the constraints later tasks must keep. The goal they serve is [project.md](project.md). A section that says a slice is already in place is the exception. Do not treat this file as permission to widen a task past what it asks for.

The skeleton already has local login, a project registry, and three local adapter interfaces (revenue, costs, health). Push ingest, the HTTP health pull, project-level connections, panel settings, and the Select data sources step are in place. Sales data still shows fixture revenue when that panel is Fake and a revenue source is bound. See the status section in [project.md](project.md) and [connectors.md](connectors.md).

## Navigation, empty state, and creating a project

The basic shell is in place. See [project.md](project.md).

- Top bar: **Overview** first, then one tab per project.
- Empty copy: "No projects started yet. Create one", with a **Create new project** button under it.
- A persistent floating **+** / **Create New Project** on every authenticated page.
- Create flow: name the project, toggle panels, then Select data sources. Confirm stores the project, its panel keys, and the connections chosen in that step. The project tab opens with those panels in a rail. Every panel is Coming soon, except Sales data when that project already has a revenue fixture.
- Delete panel and Delete project sit at the bottom of the rail. The operator types DELETE. Deleting a panel leaves shared connections in place. Deleting a project removes its panels and connections.

Still open:

- Editing an existing project's panels.

Project connections are in place. See [project.md](project.md) and [connectors.md](connectors.md). A panel is Fake or references a shared Push or HTTP health connection. Push sections route to the panel type on that connection. HTTP health is one GET through an injectable client. Panel settings live on their own route, opened from the cog in the rail.

Leave these for a later task:

- Stripe and cloud-cost connectors
- A reporter SDK that sends the push payload
- Scheduler hardening (the poll function is not a running scheduler)
- Cross-project rollups
- Alerts
- Real adapters for users, the rest of server, product metrics, marketing, support, and logistics. Logistics stays opt-in for projects that move physical goods.

## A second source adapter

There is one concrete fixture reader per kind (`fixture.revenue`, `fixture.costs`, `fixture.health`). A later task should add another adapter: its own key, its own fixtures, and behavior for bad or partial records (missing fields, unknown status, truncated files). That includes tests. Do not weaken the current adapters into silent skip-bad-rows behavior as a shortcut.

`fixture.revenue` is what Sales data reads when that panel is Fake and a revenue source is bound. `fixture.costs` and `fixture.health` already read `acme_notes_costs.json` and `acme_notes_health.json`. They are not bound in the seed and have no page. Push ingest and the HTTP health connection are a different path: they write SQLite and do not replace these fixture readers. See [connectors.md](connectors.md). Wiring the cost and health fakes through the API is separate from adding a second adapter implementation.

## Overview

Overview is still a placeholder. It does not total across projects, filter by a date range, or convert currency. On a project, Sales data shows fixture revenue when a source is bound and that panel is Fake, and System health can show the latest status from a push snapshot or an HTTP health check. `MixedCurrencyError` is the response when one project's succeeded charges disagree on currency.

Overview, as specified in [project.md](project.md), adds cross-project totals (revenue, costs, uptime, and the other chosen categories), a date range, a currency, and an activity feed. Likely shape for money: a service that takes an explicit set of project slugs and a date range, still using integer minor units, and a documented conversion step if more than one currency is allowed. Invented project names only (Lumen and Orbit are reserved examples). Do not pull in a live rates service.

## Attention, alert rules, and a local outbox

No rules engine, no notification table, no "needs attention" flag on a category. A later task can add an outbox table (via Alembic) and a local evaluator that writes rows when a rule matches. Overview should surface those rows first. Delivery stays on the machine. No email or chat provider.

## System Controls

Not built. When added, they are show-and-configure only: refresh data, enable or disable sources, and edit settings. They must not restart, deploy, or otherwise act on project infrastructure.

## Admin Users

Not built. The skeleton has one seeded local user and no screen to add, remove, or disable sign-in accounts. Password reset and remote identity providers stay out until a task asks for them.

## Also unchanged

- A background worker. `poll_due_http_health` is the hook a later scheduler should call. This process does not start one. Test connection checks immediately.
- Production hosting, containers, or a reverse proxy. Local uvicorn and Vite are the supported run.
