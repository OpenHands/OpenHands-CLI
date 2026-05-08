SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

# Colors for output
ECHO := printf '%b\n'
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
CYAN := \033[36m
UNDERLINE := \033[4m
RESET := \033[0m
REQUIRED_UV_VERSION := 0.11.6

.PHONY: help install install-dev test test-snapshots test-binary format clean run run-watch check-uv-version build install-uv lint pre-commit

check-uv-version:
	@$(ECHO) "$(YELLOW)Checking uv version...$(RESET)"
	@if ! command -v uv >/dev/null 2>&1; then \
		$(ECHO) "$(RED)Error: uv is not installed$(RESET)"; \
		$(ECHO) "$(YELLOW)Install uv first with: make install-uv$(RESET)"; \
		exit 1; \
	fi
	@UV_VERSION=$$(uv --version | cut -d' ' -f2); \
	REQUIRED_VERSION=$(REQUIRED_UV_VERSION); \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$UV_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		$(ECHO) "$(RED)Error: uv version $$UV_VERSION is less than required $$REQUIRED_VERSION$(RESET)"; \
		$(ECHO) "$(YELLOW)Please update uv with: uv self update$(RESET)"; \
		exit 1; \
	fi; \
	$(ECHO) "$(GREEN)uv version $$UV_VERSION meets requirements$(RESET)"

build: check-uv-version
	@$(ECHO) "$(CYAN)Setting up OpenHands V1 development environment...$(RESET)"
	@$(ECHO) "$(YELLOW)Installing dependencies with uv sync --dev...$(RESET)"
	@uv sync --dev
	@$(ECHO) "$(GREEN)Dependencies installed successfully.$(RESET)"
	@$(ECHO) "$(YELLOW)Setting up pre-commit hooks...$(RESET)"
	@uv run pre-commit install
	@$(ECHO) "$(GREEN)Pre-commit hooks installed successfully.$(RESET)"
	@$(ECHO) "$(GREEN)Build complete! Development environment is ready.$(RESET)"

help:
	@echo "OpenHands CLI: Lightweight OpenHands CLI in a binary executable"
	@echo ""
	@$(ECHO) "$(UNDERLINE)Usage:$(RESET) make <COMMAND>"
	@echo ""
	@$(ECHO) "$(UNDERLINE)Commands:$(RESET)"
	@$(ECHO) "  $(CYAN)install$(RESET)           Install the package"
	@$(ECHO) "  $(CYAN)install-dev$(RESET)       Install with development dependencies"
	@$(ECHO) "  $(CYAN)test$(RESET)              Run tests"
	@$(ECHO) "  $(CYAN)test-snapshots$(RESET)    Run tests snapshots"
	@$(ECHO) "  $(CYAN)test-binary$(RESET)       Run end-to-end tests"
	@$(ECHO) "  $(CYAN)test-all$(RESET)          Run tests and tests-snapshots"
	@$(ECHO) "  $(CYAN)lint$(RESET)              Lint code with Ruff"
	@$(ECHO) "  $(CYAN)format$(RESET)            Format code with Ruff"
	@$(ECHO) "  $(CYAN)pre-commit$(RESET)        Run pre-commit"
	@$(ECHO) "  $(CYAN)clean$(RESET)             Clean build artifacts"
	@$(ECHO) "  $(CYAN)run$(RESET)               Run the CLI"
	@$(ECHO) "  $(CYAN)run-watch$(RESET)         Run CLI with auto-restart on file changes"

install: check-uv-version
	@$(ECHO) "$(YELLOW)Installing the package...$(RESET)"
	uv sync
	@$(ECHO) "$(GREEN)Package installed successfully.$(RESET)"

install-dev: check-uv-version
	@$(ECHO) "$(YELLOW)Installing dev dependencies...$(RESET)"
	uv sync --group dev
	@$(ECHO) "$(GREEN)Dev dependencies installed successfully.$(RESET)"

test: check-uv-version
	@$(ECHO) "$(YELLOW)Run tests...$(RESET)"
	uv run env HOME="$$(mktemp -d)" pytest --ignore=tests/snapshots
	@$(ECHO) "$(GREEN)Tests completed.$(RESET)"

test-snapshots: check-uv-version
	@$(ECHO) "$(YELLOW)Run snapshots tests...$(RESET)"
	uv run env HOME="$$(mktemp -d)" pytest tests/snapshots -v
	@$(ECHO) "$(GREEN)Snapshots tests completed.$(RESET)"

test-binary: check-uv-version
	@$(ECHO) "$(YELLOW)Run end-to-end tests...$(RESET)"
	uv run env HOME="$$(mktemp -d)" pytest tui_e2e
	@$(ECHO) "$(GREEN)End-to-end tests completed.$(RESET)"

test-all: test test-snapshots

lint: check-uv-version
	@$(ECHO) "$(YELLOW)Linting code with uv format...$(RESET)"
	uv run ruff check openhands_cli/ --fix
	@$(ECHO) "$(GREEN)Code linted successfully.$(RESET)"

format: check-uv-version
	@$(ECHO) "$(YELLOW)Formatting code with uv format...$(RESET)"
	uv run ruff format openhands_cli/
	@$(ECHO) "$(GREEN)Code formatted successfully.$(RESET)"

pre-commit: check-uv-version
	@$(ECHO) "$(YELLOW)Run pre-commit...$(RESET)"
	uv run pre-commit run --all-files
	@$(ECHO) "$(GREEN)Pre-commit run successfully.$(RESET)"

# Clean build artifacts
clean:
	rm -rf .venv/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run the CLI
run:
	uv run openhands

# Run the CLI with auto-restart on file changes (.py and .tcss files)
run-watch:
	uv run python scripts/run_watch.py

# Install UV if not present
install-uv:
	@if ! command -v uv &> /dev/null; then \
		echo "Installing UV..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	else \
		echo "UV is already installed"; \
	fi
