#!/usr/bin/env bash
# ==============================================================================
#   START CORE MICROSERVICES (PROJECT GENESIS)
#   Runs: Gateway (:8000), Auth (:8001), User (:8002),
#         Email (:8004), Inbox (:8005), Automation (:8009)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Check .env
if [ ! -f ".env" ]; then
    echo "[ERROR] .env file not found in $SCRIPT_DIR"
    exit 1
fi

# 2. Activate virtual environment
if [ -f "$SCRIPT_DIR/venv/Scripts/activate" ]; then
    source "$SCRIPT_DIR/venv/Scripts/activate"
elif [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "[WARNING] venv not found. Using system python3."
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
mkdir -p "$SCRIPT_DIR/logs"

PIDS=()

cleanup() {
    echo ""
    echo "================================================================================"
    echo "  STOPPING ALL SERVICES..."
    echo "================================================================================"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
        fi
    done
    wait 2>/dev/null
    echo "  All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "================================================================================"
echo "  STARTING 6 CORE SERVICES"
echo "================================================================================"

# 1. Gateway Service (:8000)
echo "[1/6] Starting Gateway Service (Port 8000)..."
(cd "$SCRIPT_DIR/services/gateway-service" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/gateway-service" python main.py) > "$SCRIPT_DIR/logs/gateway.log" 2>&1 &
PIDS+=($!)
sleep 2

# 2. Auth Service (:8001)
echo "[2/6] Starting Auth Service (Port 8001)..."
(cd "$SCRIPT_DIR/services/auth-service" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/auth-service" python main.py) > "$SCRIPT_DIR/logs/auth.log" 2>&1 &
PIDS+=($!)
sleep 2

# 3. User Service (:8002)
echo "[3/6] Starting User Service (Port 8002)..."
(cd "$SCRIPT_DIR/services/user-service" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/user-service" python main.py) > "$SCRIPT_DIR/logs/user.log" 2>&1 &
PIDS+=($!)
sleep 2

# 4. Email Service (:8004)
echo "[4/6] Starting Email Service (Port 8004)..."
(cd "$SCRIPT_DIR/services/emailservice" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/emailservice" python main.py) > "$SCRIPT_DIR/logs/email.log" 2>&1 &
PIDS+=($!)
sleep 2

# 5. Inbox Service (:8005)
echo "[5/6] Starting Inbox Service (Port 8005)..."
(cd "$SCRIPT_DIR/services/inbox-service" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/inbox-service" python main.py) > "$SCRIPT_DIR/logs/inbox.log" 2>&1 &
PIDS+=($!)
sleep 2

# 6. Automation Service (:8009)
echo "[6/6] Starting Automation Service (Port 8009)..."
(cd "$SCRIPT_DIR/services/automationservice" && PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/services/automationservice" python main.py) > "$SCRIPT_DIR/logs/automation.log" 2>&1 &
PIDS+=($!)
sleep 2

echo ""
echo "================================================================================"
echo "  ALL 6 SERVICES RUNNING (Press Ctrl+C to stop all)"
echo "================================================================================"
echo "  - Gateway:    http://localhost:8000/health"
echo "  - Auth:       http://localhost:8001/health"
echo "  - User:       http://localhost:8002/health"
echo "  - Email:      http://localhost:8004/health"
echo "  - Inbox:      http://localhost:8005/health"
echo "  - Automation: http://localhost:8009/health"
echo "================================================================================"

wait
