#!/bin/bash
echo "Starting campaign-service on port 8006..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
