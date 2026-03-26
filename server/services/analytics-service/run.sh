#!/bin/bash
echo "Starting analytics-service on port 8008..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
