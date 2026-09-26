.PHONY: db-up db-down migrate api frontend test

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	alembic upgrade head

api:
	uvicorn backend.app.main:app --reload

frontend:
	cd frontend && npm run dev

test:
	pytest
