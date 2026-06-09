.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help install install-dev run test lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the app (editable)
	$(PYTHON) -m pip install -e .

install-dev: ## Install with dev/test dependencies
	$(PYTHON) -m pip install -e ".[dev]"

run: ## Launch the Pomodoro TUI
	$(PYTHON) -m pomodoro

test: ## Run the test suite
	$(PYTHON) -m pytest -q

lint: ## Lint sources with ruff (check + format check)
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
