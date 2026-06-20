#!/usr/bin/env bash
# Deploy SessyStrategy files to Home Assistant over SSH.
# Copy .env.example to .env and fill in your values, then run: ./deploy.sh
set -euo pipefail

# Load local config
if [[ -f .env ]]; then
  # shellcheck source=.env
  source .env
fi

HA_HOST="${HA_HOST:?Set HA_HOST in .env or environment}"
HA_USER="${HA_USER:-root}"
HA_CONFIG="${HA_CONFIG:-/config}"
APPDAEMON_APPS_DIR="${APPDAEMON_APPS_DIR:?Set APPDAEMON_APPS_DIR in .env or environment}"
PKG_DIR="${PKG_DIR:?Set PKG_DIR in .env or environment}"

echo "Deploying to ${HA_USER}@${HA_HOST} ..."

rsync -av files/sessy_strategy.py  "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/sessy_strategy.py"
rsync -av files/apps.yaml          "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/apps.yaml"
rsync -av files/sessy_helpers.yaml "${HA_USER}@${HA_HOST}:${PKG_DIR}/sessy_helpers.yaml"

# Home Battery custom integration (creates the device + entities).
rsync -av --delete files/custom_components/home_battery/ \
  "${HA_USER}@${HA_HOST}:${HA_CONFIG}/custom_components/home_battery/"

echo ""
echo "Done. Restart AppDaemon, and restart Home Assistant once to load the"
echo "Home Battery integration (then add it under Settings → Devices & Services)."
