#!/bin/bash
echo "Starting inbox-service on port 8005..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
