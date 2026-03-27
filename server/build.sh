#!/bin/bash
# ============================================================================
# build.sh — Full build + start for Project Genesis
#
# MUST run this before "docker compose up" on a fresh machine.
# After first run, "docker compose up" alone is sufficient (uses cached layers).
#
# Usage:
#   ./build.sh              First-time build + start everything
#   ./build.sh --no-cache   Force full rebuild from scratch
#   ./build.sh base         Rebuild base images only
#   ./build.sh up           Start containers (assumes images already built)
# ============================================================================

set -e
cd "$(dirname "$0")"

NO_CACHE=""
if [[ "$1" == "--no-cache" ]]; then
    NO_CACHE="--no-cache"
    shift
fi
MODE="${1:-all}"

build_base() {
    echo ""
    echo "[1/2] Building base image (project-genesis-base)..."
    docker build $NO_CACHE -f docker/Dockerfile.base -t project-genesis-base:latest .

    echo ""
    echo "[2/2] Building ML base image (project-genesis-base-ml)..."
    docker build $NO_CACHE -f docker/Dockerfile.base-ml -t project-genesis-base-ml:latest .

    echo ""
    echo "Base images ready."
}

case "$MODE" in
    base)
        build_base
        ;;
    up)
        echo "Starting containers (using cached images)..."
        docker compose up -d
        ;;
    all|*)
        build_base
        echo ""
        echo "[3/3] Building all service images + starting containers..."
        docker compose up --build -d
        echo ""
        echo "All services started. Run 'docker compose logs -f' to follow logs."
        ;;
esac
