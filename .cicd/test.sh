#!/usr/bin/env bash
# Run the full test suite. Extra arguments go to pytest.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

step "Tests" uv run pytest "$@"

if [[ -f frontend/package.json ]]; then
  step "Frontend tests" npm test --prefix frontend
fi
