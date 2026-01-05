#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== pgbftrace Runner (Multipass) ==="
echo ""

# Check if running inside Multipass VM (Linux)
if [[ "$(uname)" != "Linux" ]]; then
    echo "ERROR: This script should be run inside the Multipass VM."
    echo "Run: multipass shell pgbftrace"
    exit 1
fi

# Check PostgreSQL USDT probes
echo "Checking PostgreSQL USDT probes..."
POSTGRES_BIN=$(find /usr/lib/postgresql -name "postgres" -type f 2>/dev/null | head -1)
if [[ -z "$POSTGRES_BIN" ]]; then
    echo "ERROR: PostgreSQL binary not found."
    exit 1
fi

echo "PostgreSQL binary: ${POSTGRES_BIN}"

# Check if USDT probes are available
if sudo bpftrace -l "usdt:${POSTGRES_BIN}:*" 2>/dev/null | grep -q "buffer__read"; then
    echo "USDT probes available!"
else
    echo "WARNING: USDT probes not found. Tracing may not work."
    echo "PostgreSQL may need to be built with --enable-dtrace"
fi

# Update bpftrace script path for this environment
BPFTRACE_SCRIPT="${PROJECT_DIR}/server/trace_buffer_read.bt"
echo ""
echo "Updating bpftrace script for this environment..."

# Create a local copy with correct path
cat > /tmp/trace_buffer_read.bt << EOF
usdt:${POSTGRES_BIN}:buffer__read__done
{
    printf("%08x%08x\n", arg4, arg1);
}
EOF

echo "Trace script created at /tmp/trace_buffer_read.bt"

# Build frontend if needed
if [[ ! -d "${PROJECT_DIR}/frontend/dist" ]]; then
    echo ""
    echo "Building frontend..."
    cd "${PROJECT_DIR}/frontend"
    npm install
    npm run build
fi

# Ensure PostgreSQL is running
echo ""
echo "Ensuring PostgreSQL is running..."
sudo systemctl start postgresql || true
sudo systemctl status postgresql --no-pager || true

# Start the server
echo ""
echo "Starting pgbftrace server..."
echo "Access at: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Press Ctrl+C to stop."
echo ""

cd "${PROJECT_DIR}/server"

export BPFTRACE_SCRIPT="/tmp/trace_buffer_read.bt"

# Use sudo for bpftrace access
sudo -E /home/ubuntu/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
