# shellcheck shell=bash
# Shared helpers for the .cicd scripts. Source it; do not run it.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# step TITLE COMMAND [ARGS...]: run a command under a heading. On GitHub
# Actions the heading becomes a collapsible log group.
step() {
  local title=$1
  shift
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::group::${title}"
    "$@"
    echo "::endgroup::"
  else
    echo "==> ${title}"
    "$@"
  fi
}
