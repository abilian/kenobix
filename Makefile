.PHONY: help install test lint type-check format clean

all: test lint

install:
	uv sync

test:
	pytest tests -v

test-cov:
	pytest --cov=kenobix --cov-report=html --cov-report=term


check: lint

lint:
	ruff check
	ty check src
	ruff format --check
	mypy src

format:
	ruff format
	ruff check --fix
	ruff format
	markdown-toc -i --maxdepth 3 README.md

clean:
	rm -rf build/ dist/ *.egg-info htmlcov/ .coverage .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

publish: clean
	git push --tags
	uv build
	twine upload dist/*
