# Project

Living goal and scope for admin_1. This document evolves as the product does. It describes intent, not the current code. What the skeleton actually runs is in [Status](#status). How to land the rest is in [roadmap.md](roadmap.md).

Projects here are generic software projects or businesses the operator runs. Fixture names stay invented. Do not name a real product.

## Goal

A central admin panel that coordinates and consolidates many projects in one place. After signing in, you can review the most critical information for all of them together, and for each one on its own.

The app is local-first and offline-capable. Data sources are pluggable adapters. Today those adapters are local fakes that read files on disk.

## Navigation

After login, the top bar leads with **Overview** (consolidated data), then one tab per created project.

## Empty state

When the operator has no projects, the page shows:

> No projects started yet. Create one

A **Create new project** button sits under that text.

A persistent floating **+** (**Create New Project**) stays in the bottom-right corner on every authenticated page.

## Create a project

The flow asks for a name, then a checklist of the data categories that project needs. Each chosen category has its own data-source setting (which adapter feeds it).

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

## Attention

Any category can be flagged **needs attention**. Overview lists those flags first. The backing store is the future alert rules engine and its local outbox (see [roadmap.md](roadmap.md)).

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

The skeleton and this document are both evolving. Update this section when a task lands.

**Already in the skeleton**

- Local username/password sessions and one seeded dev user
- Overview tab, one tab per project, the empty-state copy, and the floating create button
- Create-project flow: a name plus the panel checklist, stored on the project
- Project page with a rail of the selected panels. Panels show Coming soon
- Delete project from the bottom of that rail, after typing DELETE. The project and its panels are removed, then Overview
- Default seed is the dev user only, so a fresh login shows the empty state
- Sales data shows fixture revenue when a project has a revenue source. Nothing is bound by default
- Adapter interfaces for revenue, costs, and server health, each with a local fake
- Offline boot and tests (`make test`)

**Not yet built**

- A data-source setting on each chosen panel
- Live data for panels other than the one revenue fixture
- Wiring cost and health fakes through to a page
- A second source adapter, and handling of bad or partial fixture data
- Cross-project totals, date ranges, and currency conversion
- The activity feed
- Needs-attention flags, the alert rules engine, and the local outbox
- System Controls and Admin Users screens
