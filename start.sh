#!/bin/bash
# ================= Configuration =================
# Modify JAVA_HOME if needed, or rely on system java
# export JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
JAVA_OPTS="-Xmx512m -Xms256m"
ENGINE_SCRIPT="trading-engine/build/install/trading-engine/bin/trading-engine"
# =================================================

# Colors
# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function kill_processes() {
    echo -e "${GREEN}[0/2] Cleaning up old processes...${NC}"
    pkill -f "python.*backend/run.py"
    pkill -f "node.*next"
    sleep 1
    echo "      Cleaned."
}

function start_python() {
    echo -e "${GREEN}[1/2] Starting Python Backend...${NC}"
    
    # 1. Setup Virtual Environment (auto-heal if broken)
    VENV_DIR=".venv"
    if [ -d "$VENV_DIR" ] && [ ! -x "$VENV_DIR/bin/pip3" ]; then
        echo "      Detected broken venv, deleting and recreating..."
        rm -rf "$VENV_DIR"
    fi
    if [ ! -d "$VENV_DIR" ]; then
        echo "      Creating Python virtual environment..."
        if ! python3 -m venv $VENV_DIR; then
             echo -e "${RED}ERROR: python3-venv missing. Run: sudo apt install python3-venv${NC}"
             exit 1
        fi
    fi
    
    # 2. Use Venv Python/Pip
    PYTHON_CMD="$VENV_DIR/bin/python3"
    PIP_CMD="$VENV_DIR/bin/pip3"

    # 3. Install/Update Dependencies
    if [ -f "backend/requirements.txt" ]; then
        echo "      Checking/Installing dependencies in venv..."
        # Capture output to log file for debugging
        if ! $PIP_CMD install -r backend/requirements.txt > pip_install.log 2>&1; then
             echo -e "${RED}ERROR: Dependency install failed. See pip_install.log${NC}"
             cat pip_install.log
             exit 1
        fi
    fi
    
    # 4. Start Backend
    nohup $PYTHON_CMD backend/run.py > backend.log 2>&1 &
    PID=$!
    echo "      Python started (pid $PID) in venv. Logs: backend.log"
    sleep 3
}

function start_frontend() {
    echo -e "${GREEN}[2/2] Starting Frontend...${NC}"
    mkdir -p logs
    cd frontend || exit
    
    # Smart Install: Only if missing
    if [ ! -d "node_modules" ]; then
        echo "      Installing frontend dependencies (npm install)..."
        # Use taobao registry for speed
        npm install --registry=https://registry.npmmirror.com --silent --no-audit --no-fund
    fi
    
    export NODE_OPTIONS="--max-old-space-size=512"
    
    # 强制清理 Next.js 生产缓存，避免缓存残留导致代码不更新
    echo "      Clearing frontend cache (.next)..."
    rm -rf .next
    
    SHOULD_BUILD=true

    if [ "$SHOULD_BUILD" = true ]; then
         echo "      Building frontend (detected changes)..."
         npm run build
    fi
    
    # FIX: Force listen on 0.0.0.0 for SSH Tunnel compatibility
    nohup npm start -- -p 3000 -H 0.0.0.0 > ../logs/frontend.log 2>&1 &
    echo "      Frontend started (pid $!). Logs: logs/frontend.log"
    cd ..
}

echo "=== BN-BY System Launcher (Python Only) ==="
kill_processes
start_python
start_frontend

echo -e "\n${GREEN}System started!${NC}"
echo "Use 'tail -f backend.log' to monitor logs."
