#!/bin/bash
echo "Starting user-service on port 8002..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
