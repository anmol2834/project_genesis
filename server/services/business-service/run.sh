#!/bin/bash
echo "Starting business-service on port 8003..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
