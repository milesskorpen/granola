#!/usr/bin/env bash
set -euo pipefail

# Build the Granola Sync .app using py2app.
# This script generates the .icns and then runs py2app.

PYTHON=${PYTHON:-python3}

$PYTHON -m venv .venv
source .venv/bin/activate
pip install -e .[app]

./scripts/make_icns.sh app_icon.png macos/Granola.icns

$PYTHON setup.py py2app

echo "App built at dist/Granola Sync.app"
