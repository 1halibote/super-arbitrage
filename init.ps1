# Init Server Script (Universal)
# Usage: ./init.ps1

# Load Configuration
$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = "." }
. "$ScriptDir\server.conf.ps1"

$HOST_IP = $TargetIP
$USER = $TargetUser

Write-Host ">>> Installing Environment on $HOST_IP (User: $USER)..." -ForegroundColor Cyan

# Determine if sudo is needed
$SUDO = ""
if ($User -ne "root") {
    $SUDO = "sudo"
}

# Command:
# Check if unzip, python3, node exist. If not, install them.
# Using 'command -v' to check existence silently.
$CMD = "$SUDO apt-get update && \
$SUDO apt-get install -y unzip dos2unix python3-pip python3-venv && \
if ! command -v node &> /dev/null; then \
    echo 'Installing Node.js...'; \
    $SUDO apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    $SUDO apt-get install -y nodejs; \
else \
    echo 'Node.js is already installed.'; \
fi && \
echo '>>> SUCCESS: Environment Ready!'".Replace("`r`n", "`n")

ssh "${USER}@${HOST_IP}" $CMD

Write-Host "Done! Now run ./deploy.ps1 to verify." -ForegroundColor Green
