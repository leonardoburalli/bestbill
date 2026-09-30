#!/usr/bin/env bash
# Static checks: lint and strict type checks.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

step "Lint" uv run ruff check .
step "Format check" uv run ruff format --check .
step "Type-check package" uv run mypy src
step "Lint CI scripts" uv run shellcheck -x .cicd/*.sh
