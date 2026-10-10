.PHONY: install setup test test-backend test-frontend migrate seed run-backend run-frontend

install:
	@if [ ! -x backend/.venv/bin/python ] || ! backend/.venv/bin/python -m pip --version >/dev/null 2>&1; then \
		echo "Creating backend/.venv"; \
		rm -rf backend/.venv; \
		python3 -m venv backend/.venv --upgrade-deps; \
		backend/.venv/bin/python -m ensurepip --upgrade; \
	fi
	backend/.venv/bin/python -m pip install -r backend/requirements.txt
	cd frontend && npm install

setup: install migrate seed

migrate:
	cd backend && .venv/bin/python -m alembic upgrade head

seed:
	cd backend && .venv/bin/python -m app.seed

test: test-backend test-frontend

test-backend:
	cd backend && .venv/bin/python -m pytest

test-frontend:
	cd frontend && npm test && npm run typecheck

run-backend:
	cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

run-frontend:
	cd frontend && npm run dev
