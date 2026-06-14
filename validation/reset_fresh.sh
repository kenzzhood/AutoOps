#!/usr/bin/env bash
# Reset AutoOps runtime state to mimic a fresh machine (keeps repo .env).
set -euo pipefail
echo "Stopping AutoOps containers..."
docker rm -f autoops-splunk autoops-otel-collector 2>/dev/null || true
echo "Clearing ~/.autoops runtime state..."
rm -f ~/.autoops/state.json ~/.autoops/architecture.json
rm -rf ~/.autoops/incidents ~/.autoops/logs
rm -f ~/.autoops/config.json
echo "Done. Run: python3 scripts/seed_provider_from_env.py && autoops configure --repo validation/shopverse-platform"
