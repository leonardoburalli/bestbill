# shellcheck shell=bash
# Shared helpers for the .cicd scripts. Source it; do not run it.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Ignore user/system uv config (e.g. a corporate package index in
# ~/.config/uv/uv.toml): this project resolves from PyPI only, as pinned in
# uv.lock. Set BESTBILL_UV_USER_CONFIG=1 to keep your own config.
if [[ "${BESTBILL_UV_USER_CONFIG:-0}" != "1" ]]; then
  export UV_NO_CONFIG=1
fi

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
