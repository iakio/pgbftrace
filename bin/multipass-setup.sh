#!/bin/bash
set -e

VM_NAME="pgbftrace"
CPUS=2
MEMORY="4G"
DISK="20G"

echo "=== pgbftrace Multipass Setup ==="
echo ""

# Check if multipass is installed
if ! command -v multipass &> /dev/null; then
    echo "ERROR: multipass is not installed."
    echo "Install it with: brew install multipass"
    exit 1
fi

# Check if VM already exists
if multipass list | grep -q "^${VM_NAME}"; then
    echo "VM '${VM_NAME}' already exists."
    echo "Use 'multipass shell ${VM_NAME}' to connect."
    echo "Or delete it with: multipass delete ${VM_NAME} && multipass purge"
    exit 0
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CLOUD_INIT="${SCRIPT_DIR}/cloud-init.yaml"

echo "Creating Ubuntu VM with cloud-init..."
echo "  Name: ${VM_NAME}"
echo "  CPUs: ${CPUS}"
echo "  Memory: ${MEMORY}"
echo "  Disk: ${DISK}"
echo ""

# Create VM with cloud-init
multipass launch 22.04 \
    --name "${VM_NAME}" \
    --cpus "${CPUS}" \
    --memory "${MEMORY}" \
    --disk "${DISK}" \
    --cloud-init "${CLOUD_INIT}"

echo ""
echo "Waiting for cloud-init to complete..."
multipass exec "${VM_NAME}" -- cloud-init status --wait

echo ""
echo "Mounting project directory..."
multipass mount "${PROJECT_DIR}" "${VM_NAME}:/home/ubuntu/pgbftrace"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "VM IP address:"
multipass info "${VM_NAME}" | grep IPv4

echo ""
echo "Next steps:"
echo "  1. Connect to VM:  multipass shell ${VM_NAME}"
echo "  2. Start the app:  cd ~/pgbftrace && ./bin/multipass-run.sh"
echo "  3. Open browser:   http://<VM_IP>:8000"
echo ""
