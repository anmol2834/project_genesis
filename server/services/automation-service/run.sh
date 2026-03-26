#!/bin/bash
echo "Starting automation-service on port 8009..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
