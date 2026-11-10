#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
set -a
. "$HERE/bridge.env"
set +a
exec python3 "$HERE/runtime.py" frontend "$@"
