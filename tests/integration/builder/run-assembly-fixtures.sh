#!/bin/sh
set -eu
# Invoke from the independent project root, or select it explicitly.
ROOT=${BATOCERA_GOW_PROJECT_ROOT:-"$PWD"}
export XDG_CACHE_HOME="$ROOT/cache"
export TMPDIR="$ROOT/output/tmp"
export PYTHONDONTWRITEBYTECODE=1
export UV_PYTHON_DOWNLOADS=never
mkdir -p "$TMPDIR" "$ROOT/cache"
exec uv run --project "$ROOT" python "$ROOT/tests/integration/builder/assembly_fixtures.py" --project-root "$ROOT" "$@"
