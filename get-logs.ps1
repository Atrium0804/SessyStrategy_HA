# Download Home Assistant and AppDaemon logs over SSH for debugging.
# Uses the same .env as deploy.ps1. Run: .\get-logs.ps1

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

if (-not $env:HA_HOST) { throw "Set HA_HOST in .env or environment" }

$HA_HOST   = $env:HA_HOST
$HA_USER   = if ($env:HA_USER)   { $env:HA_USER }   else { "root" }
$HA_CONFIG = if ($env:HA_CONFIG) { $env:HA_CONFIG } else { "/config" }

Write-Host "Fetching logs from ${HA_USER}@${HA_HOST} ..."

# HA_LOG can be overridden in .env for non-standard installs
# (e.g. HA_LOG=/srv/homeassistant/ha/config/home-assistant.log)
$HA_LOG = if ($env:HA_LOG) { $env:HA_LOG } else { "${HA_CONFIG}/home-assistant.log" }
$AD_LOG = if ($env:AD_LOG) { $env:AD_LOG } else { "${HA_CONFIG}/appdaemon/logs/appdaemon.log" }

# ── Home Assistant log ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== home-assistant.log (last 200 lines) ==="
ssh "${HA_USER}@${HA_HOST}" "tail -200 ${HA_LOG}"

# ── AppDaemon log ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== appdaemon.log (last 100 lines) ==="
ssh "${HA_USER}@${HA_HOST}" "tail -100 ${AD_LOG} 2>/dev/null || echo '(not found)'"

# ── Filter: home_battery errors only ─────────────────────────────────────────
Write-Host ""
Write-Host "=== home_battery errors in home-assistant.log ==="
ssh "${HA_USER}@${HA_HOST}" "grep -i 'home_battery\|custom_components.home_battery' ${HA_LOG} | tail -50"
