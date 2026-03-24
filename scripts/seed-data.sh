#!/usr/bin/env bash
# =============================================================================
# seed-data.sh
# Generates synthetic data for the Contoso Global Retail & Supply Chain demo
# and uploads the resulting Parquet files to the Fabric Lakehouse bronze layer.
#
# FabCon / SQLCon 2026 — populates data for:
#   - Sales transactions, customers, products, stores (for Sales Analyst Agent)
#   - Suppliers, shipments, inventory (for Supply Chain Advisor Agent)
#   - Graph relationships (for GraphQL / supply-chain graph)
#
# Prerequisites:
#   - Python 3.10+ with dependencies: pip install -r data/requirements.txt
#   - Fabric CLI (fab) or azcopy authenticated
#   - Environment variables (see below) configured
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FABRIC_WORKSPACE="${FABRIC_WORKSPACE:?Set FABRIC_WORKSPACE to the target workspace name or ID}"
LAKEHOUSE_NAME="${LAKEHOUSE_NAME:-bronze_lakehouse}"
ONELAKE_PATH="${ONELAKE_PATH:-}"  # e.g. https://<account>.dfs.fabric.microsoft.com/<workspace>/<lakehouse>/Files

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
OUTPUT_DIR="$DATA_DIR/generated"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\n\033[1;34m>>> %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || err "'$1' is required but not found in PATH."
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
log "Running pre-flight checks"
require_cmd python3
require_cmd fab

# ---------------------------------------------------------------------------
# Step 1 — Install Python dependencies
# ---------------------------------------------------------------------------
log "Installing Python data-generation dependencies"
if [ -f "$DATA_DIR/requirements.txt" ]; then
  python3 -m pip install --quiet -r "$DATA_DIR/requirements.txt"
else
  log "  No requirements.txt found — assuming dependencies are installed"
fi

# ---------------------------------------------------------------------------
# Step 2 — Run data generators
# ---------------------------------------------------------------------------
log "Generating synthetic data → ${OUTPUT_DIR}"
mkdir -p "$OUTPUT_DIR"

# Each generator script writes Parquet files into OUTPUT_DIR.
# Generators are expected to live under data/generators/.
GENERATORS_DIR="$DATA_DIR/generators"

if [ ! -d "$GENERATORS_DIR" ]; then
  err "Generators directory not found: ${GENERATORS_DIR}"
fi

for generator in "$GENERATORS_DIR"/*.py; do
  gen_name="$(basename "$generator" .py)"
  log "  Running generator: ${gen_name}"
  python3 "$generator" --output-dir "$OUTPUT_DIR"
done

# ---------------------------------------------------------------------------
# Step 3 — List generated files
# ---------------------------------------------------------------------------
log "Generated Parquet files:"
find "$OUTPUT_DIR" -name '*.parquet' -print | sort | while read -r f; do
  size=$(du -h "$f" | cut -f1)
  printf '  %-50s %s\n' "$(basename "$f")" "$size"
done

PARQUET_COUNT=$(find "$OUTPUT_DIR" -name '*.parquet' | wc -l)
if [ "$PARQUET_COUNT" -eq 0 ]; then
  err "No Parquet files were generated. Check generator scripts."
fi
log "Total files: ${PARQUET_COUNT}"

# ---------------------------------------------------------------------------
# Step 4 — Upload to Lakehouse bronze layer
# ---------------------------------------------------------------------------
log "Uploading Parquet files to Lakehouse '${LAKEHOUSE_NAME}' (bronze layer)"

if [ -n "$ONELAKE_PATH" ]; then
  # Use azcopy for bulk upload to OneLake endpoint
  log "  Using azcopy to upload to: ${ONELAKE_PATH}/bronze/"
  require_cmd azcopy

  azcopy copy \
    "${OUTPUT_DIR}/*.parquet" \
    "${ONELAKE_PATH}/bronze/" \
    --recursive=false \
    --overwrite=true \
    --log-level=WARNING
else
  # Use Fabric CLI item-level upload
  log "  Using Fabric CLI to upload files"
  for parquet_file in "$OUTPUT_DIR"/*.parquet; do
    fname="$(basename "$parquet_file")"
    log "    Uploading: ${fname}"
    fab item upload \
      --workspace "$FABRIC_WORKSPACE" \
      --item-name "$LAKEHOUSE_NAME" \
      --item-type Lakehouse \
      --source "$parquet_file" \
      --destination "Files/bronze/${fname}" \
      --overwrite
  done
fi

# ---------------------------------------------------------------------------
# Step 5 — Trigger Lakehouse table discovery (optional)
# ---------------------------------------------------------------------------
log "Triggering table discovery on '${LAKEHOUSE_NAME}'"
fab item run-command \
  --workspace "$FABRIC_WORKSPACE" \
  --item-name "$LAKEHOUSE_NAME" \
  --item-type Lakehouse \
  --command "tables.refresh" \
  2>/dev/null || log "  Table refresh not available via CLI — discover tables manually in the portal"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Seed data generation and upload complete!"
log "  Workspace:  ${FABRIC_WORKSPACE}"
log "  Lakehouse:  ${LAKEHOUSE_NAME}"
log "  Files:      ${PARQUET_COUNT} Parquet files in bronze layer"
log ""
log "Next steps:"
log "  1. Open the Lakehouse in Fabric portal to verify bronze-layer files"
log "  2. Run the medallion-architecture notebooks to transform bronze → silver → gold"
log "  3. Deploy semantic models with: scripts/deploy-fab-cli.sh"
