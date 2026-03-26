#!/bin/bash
echo "Starting leads-service on port 8007..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
