# Deploy Script for BN-BY Project
# Usage: ./deploy.ps1 [-Restart]

param (
    [switch]$Restart = $false
)

# Load Configuration
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = "." }
. "$ScriptDir\server.conf.ps1"

$HOST_IP = $TargetIP
$USER = $TargetUser

# Determine Remote Directory based on User
$REMOTE_DIR = "/home/$USER/bn-by"
if ($USER -eq "root") {
    $REMOTE_DIR = "/root/bn-by"
}

# Auto-commit changes if any
Write-Host ">>> [0/3] Auto-committing changes..." -ForegroundColor Cyan
git add .
git commit -m "Auto-deploy update"

Write-Host ">>> [1/3] Packaging project..." -ForegroundColor Cyan
git archive --format=zip --output=deploy.zip HEAD:

Write-Host ">>> [2/3] Uploading to server ($HOST_IP) as $USER..." -ForegroundColor Cyan
scp deploy.zip "${USER}@${HOST_IP}:~/"

Write-Host ">>> [3/3] Deploying on server..." -ForegroundColor Cyan

# Command: Unzip -> Fix ownership -> Fix Line Endings (optional) -> Start
$CMD = "unzip -o deploy.zip -d bn-by && sudo chown -R ${USER}:${USER} bn-by && cd $REMOTE_DIR && (dos2unix start.sh 2>/dev/null || true) && chmod +x start.sh && ./start.sh"

ssh "${USER}@${HOST_IP}" $CMD

Write-Host ">>> DONE! System is running." -ForegroundColor Green
Write-Host "Ensure SSH tunnel is active: ssh -L 3000:localhost:3000 -L 8000:localhost:8000 ${USER}@${HOST_IP}" -ForegroundColor Yellow
