# Local setup

Boot admin_1 on your machine. These steps match the root `Makefile` and [README](../README.md). Run them from the repository root.

The checkout this guide assumes is `~/projects/admin_1`.

## Prerequisites

- Python 3.11 or newer, with the standard-library `venv` module. On Debian or Ubuntu that package is `python3-venv`. `backend/pyproject.toml` sets `requires-python = ">=3.11"`.
- Node.js 22 or newer.
- `make`.

`make setup` is the only step that needs a network. After it finishes, running the app and `make test` stay on the machine.

## Update the checkout

```bash
cd ~/projects/admin_1
git pull
```

## Install, migrate, and seed

```bash
make setup
```

That target runs three steps:

1. `install` creates `backend/.venv`, installs `backend/requirements.txt`, and runs `npm install` in `frontend/`.
2. `migrate` runs `alembic upgrade head`.
3. `seed` creates the local user `dev` / `devpass` if that user is not already there. It does not create a project.

You do not need `backend/.env`. Defaults are `sqlite:///./data/admin.db` (stored as `backend/data/admin.db`), username `dev`, and password `devpass`. Copy `backend/.env.example` to `backend/.env` only to override them.

## Run

Use two terminals. In both, start in the repository root.

Terminal 1:

```bash
cd ~/projects/admin_1
make run-backend
```

That runs uvicorn on `127.0.0.1:8000`.

Terminal 2:

```bash
cd ~/projects/admin_1
make run-frontend
```

That runs Vite on `127.0.0.1:5173` and proxies `/api` to `127.0.0.1:8000`.

Open http://127.0.0.1:5173

Sign in with:

- username: `dev`
- password: `devpass`

With no projects, the page says "No projects started yet. Create one".

The API health check is http://127.0.0.1:8000/api/health and returns `{"status":"ok"}`. The page to use is the Vite URL, not port 8000.

## Test

From the repository root, servers do not need to be running:

```bash
cd ~/projects/admin_1
make test
```

`make test` runs backend `pytest`, then frontend `vitest` and `tsc --noEmit`. Tests use their own temporary databases. They do not read or write `backend/data/admin.db`.

## Reset the local database

Stop the backend first (Ctrl+C in that terminal) so nothing is holding the SQLite file. Then, from the repository root:

```bash
rm -f backend/data/admin.db
make migrate
make seed
```

`make seed` on a file with no schema fails and tells you to migrate. Run `make migrate` before `make seed`. Seeding again does not duplicate `dev` and does not change that user's password.

If `backend/.env` sets `DATABASE_URL`, delete that file instead of `backend/data/admin.db`, then run the same two `make` targets. Start `make run-backend` again after the reset.

## Stop the servers

Press Ctrl+C in the terminal running `make run-backend`, and Ctrl+C in the terminal running `make run-frontend`. Each process stays in the foreground until you stop it.

## Ports already in use

`make run-backend` binds `127.0.0.1:8000`. `make run-frontend` binds `127.0.0.1:5173`. If either command exits with `Address already in use`, another process already has that port. A previous `make run-backend` or `make run-frontend` left running in another terminal is the usual cause. Press Ctrl+C there.

To see the listener:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Stop that process, then run the `make` target again. If `lsof` is not installed, this Linux command prints the same kind of listener:

```bash
ss -ltnp 'sport = :8000'
ss -ltnp 'sport = :5173'
```

## Other setup failures

- `python3 -m venv backend/.venv` fails with `ensurepip` or `venv` missing: install `python3-venv`, then run `make setup` again.
- The sign-in page cannot reach the API: the backend terminal should still be running, and the browser should be on http://127.0.0.1:5173. Port 8000 is the API only.
