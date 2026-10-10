# Project

Living goal and scope for admin_1. This document evolves as the product does. It describes intent, not only the current code. What the app runs is in [Status](#status). Open work is in [roadmap.md](roadmap.md).

Projects here are generic software projects or businesses the operator runs. Fixture names stay invented. Do not name a real product.

## Goal

A central admin panel that coordinates and consolidates many projects in one place. After signing in, you can review the most critical information for all of them together, and for each one on its own.

Data sources are pluggable. Fixture adapters read files on disk. HTTP health performs one GET and stores the result. Pages read what is already stored.

## Navigation

After login, the top bar leads with **Overview** (consolidated data), then one tab per created project.

## Empty state

When the operator has no projects, the page shows:

> No projects started yet. Create one

A **Create new project** button sits under that text.

A persistent floating **+** (**Create New Project**) stays in the bottom-right corner on every authenticated page.

## Create a project

The flow asks for a name, then a checklist of the data categories that project needs. The next step, **Select data sources**, asks where each chosen panel gets its data: Fake, a new connection, or a connection added earlier in the same step. Back returns to the checklist. Confirm stores the project.

**Server**

- System health
- Performance
- Logs
- Uptime & incidents
- Deploys/releases

**Users**

- Daily active, new, monthly returning, and similar counts

**Financials**

- Sales/revenue
- Consolidated costs

**Optional**

- Product metrics (conversion, churn)
- Marketing (traffic, signups by channel)
- Support (tickets, response time)
- Logistics (orders, inventory, shipments, delivery status). Opt-in for projects that move physical goods.

## Data connections

A connection is a named server or service on a project, set up once. Panels reference a connection. They do not store its URL, secret, or API key. Several panels can share one connection. Fake leaves the panel with no connection. Sales data on Fake reads the charges fixture.

The panel page does not configure the source. A cog on each rail row opens `/projects/{slug}/panels/{panel}/settings`. That page chooses Fake, Push, or HTTP health (where that connector applies), creates or reuses a connection, tests it, and shows the last received time.

**Fake.** The panel reads local fixture files through the existing adapters. Nothing leaves the machine.

**Push.** One server sends a read-only payload to admin_1. admin_1 defines the payload; the panel does not get a way to change remote servers. Schema version 1 accepts any non-empty subset of `health`, `users`, `revenue`, and `costs`. A section that is present must be complete. Unknown fields are rejected. `POST /api/ingest/{project}` checks the API key of one push connection. Each section is stored on that connection and applied only to panels of the matching type that reference it: `health` to System health, `users` to User data, `revenue` to Sales data, `costs` to Consolidated costs. One server can feed System health and User data while Sales uses a different connection. The key is shown once at generation. Only its hash is stored. Rotate revokes the previous key and issues a new one. Revoke disables ingest until a new key exists.

**Pull.** A connector implements one of the existing adapter interfaces and is polled on a schedule. Connector secrets are encrypted at rest. HTTP health is the pull connector, as a connection that System health can use. It stores a URL, an expected status, and a timeout, then performs a single GET. The HTTP client is injected. Tests pass a fake transport and do not open a socket. The poll function exists; a long-running scheduler is not started in this process.

System health shows the latest status from a push snapshot or a health check. Sales data shows fixture revenue when that panel is Fake. Push sections other than health are stored in `ingest_snapshots` and are not rendered. Other panel bodies stay on Coming soon.

**Delete panel** sits at the bottom-left of every panel page, above Delete project. The operator types DELETE. The panel leaves the project and the rail. The connection stays, so other panels that share it keep working. The app opens the next panel, or Overview when that was the last one.

How to add another connector is in [connectors.md](connectors.md). Stripe and cloud-cost connectors, a reporter SDK, scheduler hardening, rollups, and alerts are planned. See [roadmap.md](roadmap.md).

## Attention

Any category can be flagged **needs attention**. Overview lists those flags first. The backing store is the planned alert rules engine and its local outbox (see [roadmap.md](roadmap.md)).

## Overview

Overview is the consolidated view:

- Cross-project totals, with a date range and a currency
- An activity feed
- **System Controls**
- **Admin Users**

### System Controls

Show and configure only: refresh data, enable or disable sources, and edit settings. Controls do not act on project infrastructure. There is no restart, deploy, or similar action.

### Admin Users

Manage who can sign in to this panel.

## Status

Update this section when a task lands.

**In place**

- Local username/password sessions and one seeded dev user
- Overview tab, one tab per project, the empty-state copy, and the floating create button
- Create-project flow: a name, the panel checklist, then Select data sources. Confirm stores the project, its panels, and any connections created in that step
- Project page with a rail of the selected panels. A cog on each row opens that panel's settings. System health shows the latest status when a snapshot or health check has one. Sales data shows fixture revenue when that panel is Fake. Other panels show Coming soon
- Delete panel from the bottom-left of every panel page, after typing DELETE. The panel leaves the rail. The next panel opens, or Overview when none remain. Shared connections stay
- Delete project from the bottom of that rail, after typing DELETE. The project, its panels, and its connections are removed, then Overview
- Default seed is the dev user only, so a fresh login shows the empty state
- Sales data shows fixture revenue when that panel is Fake. Create and panel settings do not insert a `project_sources` row. The seed does not create a project, so a fresh login has nothing to show
- Adapter interfaces for revenue, costs, and server health, each with a local fake
- Project connections. A panel is Fake or references a Push or HTTP health connection. One push connection can feed several panel types by payload section. API keys belong to the connection and are stored as hashes. HTTP health checks go through an injectable client
- Offline boot and tests (`make test`)

**Not yet built**

- Rendering stored push sections other than health (`users`, `revenue`, `costs`)
- Wiring cost and health fakes through to a page
- A second source adapter, and handling of bad or partial fixture data
- Cross-project totals, date ranges, and currency conversion
- The activity feed
- Needs-attention flags, the alert rules engine, and the local outbox
- System Controls and Admin Users screens
