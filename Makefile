.PHONY: all check format lint typecheck test coverage golden

all: check

check: lint typecheck test

format:
	uv run isort src tests
	uv run black src tests

lint:
	uv run pylint src

typecheck:
	uv run mypy

test:
	uv run pytest

coverage:
	uv run pytest --cov=src --cov-report=term-missing

golden:
	UPDATE_GOLDEN=1 uv run pytest tests/test_golden_pipeline.py
