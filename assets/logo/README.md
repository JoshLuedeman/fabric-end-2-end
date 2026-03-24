# Tales & Timber — Brand Assets

This directory contains logo files for the Tales & Timber demo environment.

## Files

| File | Format | Use Case |
|------|--------|----------|
| `tales-and-timber.svg` | SVG | README, docs, web (scalable) |
| `tales-and-timber.png` | PNG | Power BI reports, Fabric workspace icons (replace placeholder) |

## Replacing the Placeholder Logo

The SVG is a placeholder. To use your own logo:

1. Replace `tales-and-timber.svg` with your custom SVG
2. Export a 256×256 PNG as `tales-and-timber.png` for Fabric workspace icons
3. Export a wide PNG (800×200) as `tales-and-timber-wide.png` for report headers

## Where the Logo is Referenced

- `README.md` — hero image at top of file
- `src/power-bi/reports/*/report.json` — report header logo
- `scripts/deploy-fab-cli.sh` — workspace icon upload (if PNG exists)
- Fabric workspace settings — uploaded via REST API in `scripts/post-deploy-config.sh`
