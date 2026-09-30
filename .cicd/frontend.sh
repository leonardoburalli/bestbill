#!/usr/bin/env bash
# Frontend checks: install (locked), type-check, test, build. Uses bun.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

cd frontend
step "Install frontend dependencies" bun install --frozen-lockfile
step "Type-check frontend" bun run typecheck
step "Frontend tests" bun run test
step "Build frontend" bun run build
