#!/usr/bin/env bash
set -euo pipefail
echo "Installing AutoOps AI..."
if command -v pipx >/dev/null 2>&1; then
  pipx install -e .
  echo "Installed via pipx. Run: autoops setup"
elif command -v pip3 >/dev/null 2>&1; then
  pip3 install -e ".[dev]"
  echo "Installed via pip. Run: autoops setup"
else
  echo "Install Python 3.11+ and pip/pipx first."
  exit 1
fi
