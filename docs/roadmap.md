# Roadmap

What is still missing, and the constraints later tasks must keep. The goal they serve is [project.md](project.md). None of the items below are implemented. Do not treat this file as permission to widen a task past what it asks for.

The skeleton already has local login, a project registry, three local adapter interfaces (revenue, costs, health), and one wired revenue view. See the status section in [project.md](project.md).

## Navigation, empty state, and creating a project

The basic shell is in place. See [project.md](project.md).

- Top bar: **Overview** first, then one tab per project.
- Empty copy: "No projects started yet. Create one", with a **Create new project** button under it.
- A persistent floating **+** / **Create New Project** on every authenticated page.
- Create flow: name the project, then toggle panels. Confirm stores the project and its panel keys. The project tab opens with those panels in a rail. Every panel is Coming soon, except Sales data when that project already has a revenue fixture.

Still open:

- A data-source setting for each chosen panel. Toggles only record that the panel is wanted.
- Editing an existing project's panels.
- Real adapters for users, the rest of server, product metrics, marketing, support, and logistics. Logistics stays opt-in for projects that move physical goods.

## A second source adapter

There is one concrete reader per kind (`fixture.revenue`, `fixture.costs`, `fixture.health`). A later task should add another adapter: its own key, its own fixtures, and behavior for bad or partial records (missing fields, unknown status, truncated files). That includes tests. Do not weaken the current adapters into silent skip-bad-rows behavior as a shortcut.

Cost and health fakes already read `acme_notes_costs.json` and `acme_notes_health.json`. They are not bound in the seed, and they have no service, route, or page. Wiring those two fakes through the API is separate from adding a second adapter implementation.

## Overview

The current dashboard asks for one project's revenue. It does not total across projects, filter by a date range, or convert currency. `MixedCurrencyError` is the current response when one project's succeeded charges disagree on currency.

Overview, as specified in [project.md](project.md), adds cross-project totals (revenue, costs, uptime, and the other chosen categories), a date range, a currency, and an activity feed. Likely shape for money: a service that takes an explicit set of project slugs and a date range, still using integer minor units, and a documented conversion step if more than one currency is allowed. Invented project names only (Lumen and Orbit are reserved examples). Do not pull in a live rates service.

## Attention, alert rules, and a local outbox

No rules engine, no notification table, no "needs attention" flag on a category. A later task can add an outbox table (via Alembic) and a local evaluator that writes rows when a rule matches. Overview should surface those rows first. Delivery stays on the machine. No email or chat provider.

## System Controls

Not built. When added, they are show-and-configure only: refresh data, enable or disable sources, and edit settings. They must not restart, deploy, or otherwise act on project infrastructure.

## Admin Users

Not built. The skeleton has one seeded local user and no screen to add, remove, or disable sign-in accounts. Password reset and remote identity providers stay out until a task asks for them.

## Also unchanged

- Background workers and scheduled polls.
- Production hosting, containers, or a reverse proxy. Local uvicorn and Vite are the supported run.
