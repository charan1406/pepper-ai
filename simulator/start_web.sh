#!/bin/bash
# Pepper AI — Start the 3D Web Frontend

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$SCRIPT_DIR/web"

cd "$WEB_DIR"

if [ ! -d "node_modules" ]; then
    echo "[1/2] Installing npm dependencies..."
    npm install
else
    echo "[1/2] Dependencies already installed."
fi

echo "[2/2] Starting 3D frontend on http://localhost:5002"
npm run dev
