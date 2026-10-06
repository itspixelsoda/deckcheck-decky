#!/bin/sh
# Builds out/deckcheck.zip in the layout Decky expects: one top-level folder holding the plugin files.
set -e
cd "$(dirname "$0")/.."
rm -rf out
mkdir -p out/deckcheck
cp -R dist plugin.json package.json main.py py_modules LICENSE README.md out/deckcheck/
find out/deckcheck -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd out && zip -qr deckcheck.zip deckcheck)
rm -rf out/deckcheck
echo "out/deckcheck.zip"
