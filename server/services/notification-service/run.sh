#!/bin/bash
echo "Starting notification-service on port 8011..."
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/../.."
python main.py
