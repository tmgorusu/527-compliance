#!/usr/bin/env bash
# Copy pipeline packages into backend/ for the Vercel Python service root.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -rf backend/src backend/contract backend/config backend/spec
cp -R src contract config spec backend/
find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find backend -name OWNER.txt -delete
echo "Vendored src/contract/config/spec → backend/"
