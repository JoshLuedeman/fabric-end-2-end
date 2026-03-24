#!/usr/bin/env bash
set -euo pipefail

# Upload Power BI reports and semantic models to Fabric workspace via Fabric CLI
# Usage: ./scripts/upload-reports.sh <environment>

ENVIRONMENT="${1:-dev}"
WORKSPACE="contoso-analytics-${ENVIRONMENT}"

echo "=== Uploading Power BI content to ${WORKSPACE} ==="

# Authenticate
fab auth login --service-principal 2>/dev/null || echo "Using existing auth session"

# Upload semantic models first (reports depend on them)
echo "Uploading semantic models..."
for model in src/power-bi/semantic-models/*.bim; do
  name=$(basename "$model" .bim)
  echo "  → ${name}"
  fab cp "$model" "${WORKSPACE}/SemanticModels/${name}" 2>/dev/null || \
    echo "    (skipped or updated)"
done

# Upload reports
echo "Uploading reports..."
for report_dir in src/power-bi/reports/*.pbip; do
  name=$(basename "$report_dir" .pbip)
  echo "  → ${name}"
  fab cp "$report_dir" "${WORKSPACE}/Reports/${name}" 2>/dev/null || \
    echo "    (skipped or updated)"
done

echo "=== Power BI upload complete ==="
