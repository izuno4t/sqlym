.PHONY: dev install test lint format lint-fix spell pre-commit clean db-up db-down test-postgresql test-mysql test-oracle test-db test-all build release-test release

dev: install
	uv run pre-commit install

install:
	uv sync --dev

test:
	uv run pytest

test-cov:
	uv run pytest --cov=sqly --cov-report=term-missing

lint:
	uv run ruff check .

format:
	uv run ruff format .

lint-fix:
	uv run ruff check . --fix

spell:
	npx cspell "**/*.py" "**/*.md" --no-progress

pre-commit:
	uv run pre-commit run --all-files

db-up:
	docker compose up -d --wait

db-down:
	docker compose down

test-postgresql:
	uv run pytest -m postgresql -v

test-mysql:
	uv run pytest -m mysql -v

test-oracle:
	uv run pytest -m oracle -v

test-db:
	uv run pytest -m "postgresql or mysql or oracle" -v

test-all:
	uv run pytest -v

clean:
	rm -rf .venv .ruff_cache .pytest_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

build:
	rm -rf dist/
	uv run python -m build

release-test: build
	uv run twine upload --repository testpypi dist/*

release: build
	uv run twine upload --repository sqlym dist/*
