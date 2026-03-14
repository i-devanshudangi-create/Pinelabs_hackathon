#!/bin/bash
# PlurAgent — One-command startup for demo
# Usage: ./start.sh

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()
LOG_DIR="$DIR/.logs"
mkdir -p "$LOG_DIR"

# Load environment variables
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

cleanup() {
    echo ""
    echo "Shutting down all services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # Kill any orphans on our ports
    lsof -ti :8000 -ti :8001 -ti :8002 -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true
    wait 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# Kill anything already on our ports
echo "Cleaning up stale processes..."
lsof -ti :8000 -ti :8001 -ti :8002 -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║     PlurAgent — Agentic Commerce Demo     ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# 1. Pine Labs Service (port 8002)
echo "[1/4] Starting Pine Labs Service on :8002 ..."
(cd "$DIR/services/pinelabs" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8002 > "$LOG_DIR/pinelabs.log" 2>&1) &
PIDS+=($!)
sleep 2

# 2. Agent Service (port 8001)
echo "[2/4] Starting Agent Service on :8001 ..."
(cd "$DIR/services/agent" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 > "$LOG_DIR/agent.log" 2>&1) &
PIDS+=($!)
sleep 2

# 3. Gateway Service (port 8000)
echo "[3/4] Starting Gateway on :8000 ..."
(cd "$DIR/services/gateway" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/gateway.log" 2>&1) &
PIDS+=($!)
sleep 2

# 4. Frontend (port 5173)
echo "[4/4] Starting Frontend on :5173 ..."
(cd "$DIR/frontend" && npm run dev > "$LOG_DIR/frontend.log" 2>&1) &
PIDS+=($!)
sleep 3

# Health checks
echo ""
echo "Running health checks..."
ALL_OK=true

for svc in "Pine Labs:8002" "Agent:8001" "Gateway:8000"; do
    name="${svc%%:*}"
    port="${svc##*:}"
    if curl -s "http://localhost:$port/health" > /dev/null 2>&1 || curl -s "http://localhost:$port/api/health" > /dev/null 2>&1; then
        echo "  ✓ $name (:$port) — running"
    else
        echo "  ✗ $name (:$port) — FAILED (check $LOG_DIR/)"
        ALL_OK=false
    fi
done

if curl -s "http://localhost:5173" > /dev/null 2>&1; then
    echo "  ✓ Frontend (:5173) — running"
else
    echo "  ✗ Frontend (:5173) — FAILED (check $LOG_DIR/frontend.log)"
    ALL_OK=false
fi

echo ""
if [ "$ALL_OK" = true ]; then
    echo "═══════════════════════════════════════════"
    echo "  All services running!"
    echo ""
    echo "  Frontend  → http://localhost:5173"
    echo "  Gateway   → http://localhost:8000"
    echo "  Agent     → http://localhost:8001"
    echo "  Pine Labs → http://localhost:8002"
    echo ""
    echo "  Logs      → $LOG_DIR/"
    echo "═══════════════════════════════════════════"
else
    echo "⚠ Some services failed to start. Check logs in $LOG_DIR/"
fi

echo ""
echo "Press Ctrl+C to stop all services."
echo ""

wait
