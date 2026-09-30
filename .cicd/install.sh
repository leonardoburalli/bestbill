#!/usr/bin/env bash
# Install the locked Python environment (the frontend is handled by frontend.sh).
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$0")/lib.sh"

step "Install Python dependencies" uv sync --locked --extra dev
