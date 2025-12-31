#!/bin/bash

# ホストのカーネルバージョンを確認し、bpftraceが利用可能か確認します。
echo "Checking host kernel version for BPF compatibility..."
uname_r=$(uname -r)
echo "Host Kernel Version: $uname_r"
kernel_major=$(echo "$uname_r" | cut -d'.' -f1)
kernel_minor=$(echo "$uname_r" | cut -d'.' -f2)

if [ "$kernel_major" -lt 4 ] || ([ "$kernel_major" -eq 4 ] && [ "$kernel_minor" -lt 9 ]); then
  echo "WARNING: BPF generally requires kernel 4.9+ (5.x+ recommended). Your kernel might be too old."
  echo "Proceeding anyway, but bpftrace might not function correctly."
else
  echo "Host kernel version seems compatible with BPF."
fi

echo ""
echo "Starting bpftrace development container..."
echo "Note: This container requires '--privileged' or specific capabilities and volume mounts to access BPF features."

docker run --rm -d \
  --privileged \
  -v /sys/kernel/debug:/sys/kernel/debug:ro \
  -v /sys/fs/bpf:/sys/fs/bpf \
  -v /usr/src:/usr/src:ro \
  -v "$PWD":/app \
  -p 8000:8000 \
  --name pgbftrace_app \
  bpftrace-dev
