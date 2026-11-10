#!/bin/sh
# Run fixture-only mounted-state/process checks from an explicit project root.
set -eu
ROOT=${BATOCERA_GOW_PROJECT_ROOT:-$PWD}
exec uv run --project "$ROOT" python \
    "$ROOT/tests/integration/runtime/run_runtime_tests.py" --project-root "$ROOT" "$@"
