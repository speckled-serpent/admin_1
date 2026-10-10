# Testing

`make test` runs the backend suite and the frontend suite. Both must pass with no network.

## Backend

From `backend/`, with the virtualenv:

```bash
cd backend && .venv/bin/pytest
```

Pytest config is in `backend/pyproject.toml`. Tests live in `backend/tests/`.

Conventions:

- Each test gets its own SQLite file under pytest's temp directory. Nothing in the suite reads or writes `backend/data/admin.db`.
- `tests/conftest.py` replaces `socket.socket` with a guard. Connecting to anything other than localhost raises. Do not weaken that guard to reach a real service.
- Money assertions use minor units. The Acme Notes fixture is pinned: gross `15900`, refunded `1700`, net `14200`, 6 succeeded, 8 charges.
- Adapter tests call the fake classes on the JSON files. They do not boot the ASGI app.
- API tests use `TestClient` and the dependency override for `get_db`. Login through `POST /api/auth/login`; do not hardcode a session row unless the test is about expiry.
- `tests/test_migrations.py` runs `alembic upgrade head` and compares column names to the SQLAlchemy models. If you add a column, add it to the migration and the model together.

`FixtureError` on a malformed record is part of the current adapter contract. A dedicated bad-data or partial-data suite is out of scope until a second adapter exists.

## Frontend

```bash
cd frontend && npm test && npm run typecheck
```

Vitest uses jsdom. Tests stub `fetch`. They must not call the backend and must not load a remote asset.

- `src/test/format.test.ts` locks display of minor units and charge labels.
- `src/test/Login.test.tsx` covers a successful sign-in, a 401 message, and the redirect when no token is stored.
- `src/test/projects.test.tsx` covers the empty state, the create-project flow, and the panel rail.
- `src/test/Dashboard.test.tsx` renders revenue totals from the Sales data panel.
- `src/test/deleteProject.test.tsx` covers the delete confirmation: disabled until `DELETE`, Enter submits, Cancel and Escape close.

Prefer queries by role and visible text. The display locale is `en-US` so `$159.00` is stable.

## What not to add

- Tests that need a token from a hosted service.
- Tests that download fixture data.
- Snapshot tests of the whole page.
- Coverage gates. The suites above are the contract.
