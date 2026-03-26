#!/bin/bash
echo "Starting auth-service on port 8001..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
