#!/bin/bash
# Pepper AI Simulator — Setup & Launch Script
# For Arch Linux (and any PEP 668 compliant distro)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

echo "============================================"
echo "  Pepper AI — Environment Setup"
echo "============================================"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/3] Creating virtual environment..."
    python -m venv "$VENV_DIR"
else
    echo "[1/3] Virtual environment exists."
fi

# Activate and install deps
echo "[2/3] Installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet websockets opencv-python numpy pyaudio 2>/dev/null || {
    echo "[WARN] pyaudio failed — trying without it (mic will be simulated)"
    pip install --quiet websockets opencv-python numpy
}

# Launch bridge
echo "[3/3] Starting simulator bridge..."
echo ""
cd "$SCRIPT_DIR"
python sim_bridge.py
