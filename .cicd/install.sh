#!/usr/bin/env bash
# Install the locked Python environment (and the frontend, once it exists).
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

step "Install Python dependencies" uv sync --locked --extra dev

if [[ -f frontend/package.json ]]; then
  step "Install frontend dependencies" npm ci --prefix frontend
fi
