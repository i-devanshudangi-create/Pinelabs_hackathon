#!/bin/bash
# PlurAgent — Stop all services
echo "Stopping all PlurAgent services..."
lsof -ti :8000 -ti :8001 -ti :8002 -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
echo "All services stopped."
