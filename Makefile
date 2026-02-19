.PHONY: setup test lint format build clean

setup:
	pip install uv
	uv venv
	uv pip install -e ".[dev,test]"
	uv run pre-commit install

test:
	uv run pytest tests/

lint:
	uv run flake8 src tests
	uv run black --check src tests
	uv run mypy src

format:
	uv run black src tests
	uv run isort src tests

build:
	uv run python -m build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .venv

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

db-migrate:
	uv run alembic upgrade head
