.PHONY: install setup test test-backend test-frontend migrate seed run-backend run-frontend

install:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements.txt
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
