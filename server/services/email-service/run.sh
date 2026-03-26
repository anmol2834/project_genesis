#!/bin/bash
echo "Starting email-service on port 8004..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
