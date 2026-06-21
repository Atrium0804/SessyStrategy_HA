# Deploy SessyStrategy files to Home Assistant over SSH.
# Copy .env.example to .env and fill in your values, then run: .\deploy.ps1

# Load .env if present
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

if (-not $env:HA_HOST)            { throw "Set HA_HOST in .env or environment" }
if (-not $env:APPDAEMON_APPS_DIR) { throw "Set APPDAEMON_APPS_DIR in .env or environment" }
if (-not $env:PKG_DIR)            { throw "Set PKG_DIR in .env or environment" }

$HA_HOST            = $env:HA_HOST
$HA_USER            = if ($env:HA_USER) { $env:HA_USER } else { "root" }
$HA_CONFIG          = if ($env:HA_CONFIG) { $env:HA_CONFIG } else { "/config" }
$APPDAEMON_APPS_DIR = $env:APPDAEMON_APPS_DIR
$PKG_DIR            = $env:PKG_DIR

Write-Host "Deploying to ${HA_USER}@${HA_HOST} ..."

scp files/sessy_strategy.py  "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/sessy_strategy.py"
scp files/apps.yaml          "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/apps.yaml"
scp files/sessy_helpers.yaml "${HA_USER}@${HA_HOST}:${PKG_DIR}/sessy_helpers.yaml"

# Home Battery custom integration (creates the device + entities).
ssh "${HA_USER}@${HA_HOST}" "mkdir -p ${HA_CONFIG}/custom_components/home_battery"
scp -r files/custom_components/home_battery/* "${HA_USER}@${HA_HOST}:${HA_CONFIG}/custom_components/home_battery/"

Write-Host ""
Write-Host "Restarting Home Assistant ..."
ssh "${HA_USER}@${HA_HOST}" "cd /srv/homeassistant && sudo docker compose restart"

Write-Host ""
Write-Host "Done. Home Assistant is restarting. AppDaemon will come back up with it."
Write-Host "If this is a first-time deploy, add the Home Battery integration under"
Write-Host "Settings -> Devices & Services once HA is back online."
