#!/bin/bash
echo "Starting gateway-service on port 8000..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
