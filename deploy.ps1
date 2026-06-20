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
$APPDAEMON_APPS_DIR = $env:APPDAEMON_APPS_DIR
$PKG_DIR            = $env:PKG_DIR

Write-Host "Deploying to ${HA_USER}@${HA_HOST} ..."

scp files/sessy_strategy.py  "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/sessy_strategy.py"
scp files/apps.yaml          "${HA_USER}@${HA_HOST}:${APPDAEMON_APPS_DIR}/apps.yaml"
scp files/sessy_helpers.yaml "${HA_USER}@${HA_HOST}:${PKG_DIR}/sessy_helpers.yaml"

Write-Host ""
Write-Host "Done. Restart AppDaemon in HA to pick up changes."
