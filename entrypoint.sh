#!/bin/bash
set -e

echo "[*] Creating vcluster: my-vcluster-test-15..."
# kubectl config use-context kind-test-15

vcluster create my-vcluster-test-15 -n vcluster-my-vcluster-test-15 --connect=false

echo "[*] Starting home.py script..."
/venv/bin/python /app2/home.py


