#!/bin/bash
# PlurAgent Microservices Launcher
# Starts all 3 backend services + frontend dev server

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
    echo ""
    echo "Shutting down all services..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

echo "=== PlurAgent Microservices ==="
echo ""

# 1. Pine Labs Service (port 8002) — must start first
echo "[1/4] Starting Pine Labs Service on :8002 ..."
(cd "$DIR/services/pinelabs" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8002) &
PIDS+=($!)
sleep 1

# 2. Agent Service (port 8001)
echo "[2/4] Starting Agent Service on :8001 ..."
(cd "$DIR/services/agent" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8001) &
PIDS+=($!)
sleep 1

# 3. Gateway Service (port 8000)
echo "[3/4] Starting Gateway on :8000 ..."
(cd "$DIR/services/gateway" && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000) &
PIDS+=($!)
sleep 1

# 4. Frontend (port 5173)
echo "[4/4] Starting Frontend on :5173 ..."
(cd "$DIR/frontend" && npm run dev) &
PIDS+=($!)

echo ""
echo "All services running:"
echo "  Pine Labs : http://localhost:8002"
echo "  Agent     : http://localhost:8001"
echo "  Gateway   : http://localhost:8000"
echo "  Frontend  : http://localhost:5173"
echo ""
echo "Open http://localhost:5173 in your browser."
echo "Press Ctrl+C to stop all services."
echo ""

wait
