# Connect Script for BN-BY Project
# Usage: ./connect.ps1
# Establishes SSH Tunnel to Server

# Load Configuration
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = "." }
. "$ScriptDir\server.conf.ps1"

Write-Host ">>> Connecting to $TargetIP as $TargetUser..." -ForegroundColor Cyan
Write-Host ">>> Forwarding ports: 3000 (UI), 8000 (API)" -ForegroundColor Yellow
Write-Host ">>> Press Ctrl+C to disconnect." -ForegroundColor Gray

# Execute SSH with Tunneling
ssh -L 3000:localhost:3000 -L 8000:localhost:8000 "${TargetUser}@${TargetIP}"
