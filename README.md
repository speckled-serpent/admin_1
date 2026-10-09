# admin_1

Local-first admin panel for a user's software projects. This repository is the skeleton: local login, a SQLite project registry, fixture-backed source adapters, and one wired view — revenue for the fictional project **Acme Notes**.

Runtime and tests do not call the network. There is no external API, CDN, font host, or telemetry.

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

The living goal and scope is [docs/project.md](docs/project.md). Conventions live in [docs/architecture.md](docs/architecture.md), [docs/adapters.md](docs/adapters.md), and [docs/testing.md](docs/testing.md). Work still to do, and the constraints on it, are listed in [docs/roadmap.md](docs/roadmap.md).

## Prerequisites

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

After sign-in the top bar leads with Overview, then one tab per project. With no projects, the page says "No projects started yet. Create one". Creating a project asks for a name and which panels to turn on.

The seed still adds Acme Notes. Open that tab and choose Sales data to see revenue from `backend/fixtures/acme_notes_charges.json` (gross, refunds, net, and the charge list). Other panels stay on a Coming soon page.

## Test

```bash
make test
```

That runs `pytest` for the backend and `vitest` plus `tsc --noEmit` for the frontend. Backend tests refuse outbound sockets. Frontend tests stub `fetch`.

## Seeded data

| Piece | Value |
| --- | --- |
| User | `dev` / `devpass` (password stored as a PBKDF2 hash) |
| Project | Acme Notes (`acme-notes`) |
| Revenue source | `fixture.revenue` → `fixtures/acme_notes_charges.json` |

Cost and health fixtures are on disk for their adapters and are not attached to the project. Running `make seed` again does not duplicate the user, the project, or the binding. It also does not reset the password if the user already exists.

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
| `GET` | `/api/projects/{slug}/revenue` | One project's revenue |

Money in JSON is integer minor units. `usd` `15900` is 159.00 dollars.

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"dev","password":"devpass"}'
```

## License

MIT. See [LICENSE](LICENSE).
