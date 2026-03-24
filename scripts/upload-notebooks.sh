#!/usr/bin/env bash
set -euo pipefail

# Upload notebooks to Fabric workspace via Fabric CLI
# Usage: ./scripts/upload-notebooks.sh <environment>

ENVIRONMENT="${1:-dev}"
WORKSPACE_PREFIX="tt-data-engineering-${ENVIRONMENT}"

echo "=== Uploading notebooks to ${WORKSPACE_PREFIX} ==="

# Authenticate (assumes az login or SPN credentials are available)
fab auth login --service-principal 2>/dev/null || echo "Using existing auth session"

# Upload bronze notebooks
echo "Uploading bronze notebooks..."
for notebook in src/notebooks/bronze/*.py; do
  name=$(basename "$notebook" .py)
  echo "  → ${name}"
  fab cp "$notebook" "${WORKSPACE_PREFIX}/Notebooks/${name}" 2>/dev/null || \
    echo "    (skipped or updated)"
done

# Upload silver notebooks
echo "Uploading silver notebooks..."
for notebook in src/notebooks/silver/*.py; do
  name=$(basename "$notebook" .py)
  echo "  → ${name}"
  fab cp "$notebook" "${WORKSPACE_PREFIX}/Notebooks/${name}" 2>/dev/null || \
    echo "    (skipped or updated)"
done

# Upload gold notebooks
echo "Uploading gold notebooks..."
for notebook in src/notebooks/gold/*.py; do
  name=$(basename "$notebook" .py)
  echo "  → ${name}"
  fab cp "$notebook" "${WORKSPACE_PREFIX}/Notebooks/${name}" 2>/dev/null || \
    echo "    (skipped or updated)"
done

echo "=== Notebook upload complete ==="
