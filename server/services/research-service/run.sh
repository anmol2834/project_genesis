#!/bin/bash
echo "Starting research-service on port 8010..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
