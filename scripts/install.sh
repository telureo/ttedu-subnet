#!/usr/bin/env bash
# Installs the ttedu command line in a virtual environment (.venv) inside this repository.
#
#   scripts/install.sh
#
# With uv (https://docs.astral.sh/uv/) it installs the exact versions in uv.lock. Without uv it uses Python's own
# venv and pip. To choose the Python it uses without uv: PYTHON=/path/to/python3.12 scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  uv sync --locked --no-dev
else
  python="${PYTHON:-python3}"
  if ! "$python" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)'; then
    echo "ttedu needs Python 3.11 or newer. This computer has $("$python" --version 2>&1)."
    exit 1
  fi
  if ! "$python" -m venv .venv; then
    echo
    echo "Python couldn't create a virtual environment. On Ubuntu or Debian, install the venv package first:"
    echo "  sudo apt install python3-venv"
    exit 1
  fi
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi

.venv/bin/ttedu --version
echo "Installed. Run .venv/bin/ttedu --help, or activate the environment first: source .venv/bin/activate"
