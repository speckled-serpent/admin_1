# admin_1

admin_1 is an admin panel that consolidates multiple projects into one service. The goal of this project is to build a working admin panel that brings multiple projects together so you can review them quickly, all at once. Many panels are still under development.

## Layout

```
backend/          FastAPI, SQLAlchemy, Alembic, pytest
  app/            routes, services, adapters, seed
  fixtures/       local JSON for revenue, costs, and health
  alembic/        schema migrations
  tests/
frontend/         React, Vite, TypeScript, vitest
docs/             project goal, architecture, adapters, testing, roadmap
```

The living goal and scope is [docs/project.md](docs/project.md). Local boot, reset, and port troubleshooting are in [docs/local_setup.md](docs/local_setup.md). Conventions live in [docs/architecture.md](docs/architecture.md), [docs/adapters.md](docs/adapters.md), and [docs/testing.md](docs/testing.md). Work still to do, and the constraints on it, are listed in [docs/roadmap.md](docs/roadmap.md).

## Prerequisites

Step-by-step boot from `~/projects/admin_1` is in [docs/local_setup.md](docs/local_setup.md).

- Python 3.11+ (the standard library `venv` module; on Debian/Ubuntu that is the `python3-venv` package)
- Node.js 22+

Install once (this step needs a network). After that, boot, test, and run stay on the machine.

```bash
make setup
```

`make setup` creates `backend/.venv`, installs Python and Node dependencies, applies migrations, and seeds the database.

Equivalent commands:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
make migrate
make seed
```

Optional overrides: copy `backend/.env.example` to `backend/.env`.

## Run

Two processes, both bound to localhost.

```bash
make run-backend
```

```bash
make run-frontend
```

- API: http://127.0.0.1:8000
- App: http://127.0.0.1:5173
- Health: `GET http://127.0.0.1:8000/api/health`

Open the app and sign in as the seeded user:

- username: `dev`
- password: `devpass`

After sign-in the top bar leads with Overview, then one tab per project. With no projects, the page says "No projects started yet. Create one". Creating a project asks for a name, which panels to turn on, and a data source for each of those panels: Fake, a new connection, or a connection added earlier in that same step.

On a project page the left rail lists the panels. A cog opens that panel's settings. **Delete panel** and **Delete project** sit at the bottom of the rail. Each requires typing `DELETE`. Delete panel removes that panel and opens the next one, or Overview when none remain. Delete project removes the project and returns to Overview. Shared connections stay when only a panel is deleted.

Sales data shows fixture revenue only when that panel is Fake and the project has a revenue source. The default seed does not create one. System health can show the latest status when a snapshot or health check has one. Other panels stay on Coming soon until they have data. If an older database still has a project from a previous seed, delete `backend/data/admin.db` and run `make seed` again.

## Test

```bash
make test
```

That runs `pytest` for the backend and `vitest` plus `tsc --noEmit` for the frontend. Backend tests refuse outbound sockets. Frontend tests stub `fetch`.

```bash
make lint
```

`make lint` runs Ruff on the backend and ESLint on the frontend. It does not need a network once dependencies are installed.

## Seeded data

| Piece | Value |
| --- | --- |
| User | `dev` / `devpass` (password stored as a PBKDF2 hash) |

The seed does not create a project or a source binding. Charge, cost, and health fixtures stay on disk for adapters and tests. Running `make seed` again does not duplicate the user and does not reset the password if the user already exists.

## API (authenticated, except health and login)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness |
| `POST` | `/api/auth/login` | Exchange username and password for a bearer token |
| `POST` | `/api/auth/logout` | Revoke the current token |
| `GET` | `/api/auth/me` | Current username |
| `GET` | `/api/panel-catalog` | Panel checklist |
| `GET` | `/api/projects` | Projects and their panels |
| `POST` | `/api/projects` | Create a project and its panels |
| `DELETE` | `/api/projects/{slug}` | Remove a project, its panels, connections, keys, and snapshots |
| `DELETE` | `/api/projects/{slug}/panels/{panel}` | Remove one panel. Shared connections stay |
| `GET` | `/api/projects/{slug}/revenue` | One project's revenue, when a source is bound |
| `GET` | `/api/projects/{slug}/connections` | Named connections on the project |
| `POST` | `/api/projects/{slug}/connections` | Create a Push or HTTP health connection |
| `GET` | `/api/projects/{slug}/panels/{panel}/settings` | The panel's source, connection, and last received time |
| `PUT` | `/api/projects/{slug}/panels/{panel}/settings` | Assign Fake, an existing connection, or a new one |
| `POST` | `/api/projects/{slug}/connections/{id}/api-key` | Generate a connection API key (shown once) |
| `POST` | `/api/projects/{slug}/connections/{id}/api-key/rotate` | Revoke the active key and issue a new one |
| `DELETE` | `/api/projects/{slug}/connections/{id}/api-key` | Revoke the active key |
| `POST` | `/api/projects/{slug}/panels/{panel}/test-connection` | Check the panel's connection |
| `POST` | `/api/ingest/{slug}` | Push a version-1 payload (connection API key, not the user session) |

Money in JSON is integer minor units. `usd` `15900` is 159.00 dollars.

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"dev","password":"devpass"}'
```

## License

MIT. See [LICENSE](LICENSE).
