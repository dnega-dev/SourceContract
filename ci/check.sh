#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

case "$(python3 -c 'import sys; print(int(sys.version_info >= (3, 9)))')" in
  1) ;;
  *) echo "SourceContract requires Python 3.9 or newer" >&2; exit 2 ;;
esac

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
python3 -m sourcecontract validate json --format text >/dev/null
python3 -m sourcecontract validate xml --format text >/dev/null
