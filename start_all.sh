#!/bin/bash
# Pepper AI — Launch Everything in Kitty tabs

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo "  PEPPER AI — Full Stack Launch"
echo "============================================"
echo ""
echo "  Opening Kitty with 3 tabs..."
echo ""
echo "  Tab 1: Simulator Bridge    :5001"
echo "  Tab 2: Brain (4B GPU)      :8090"
echo "  Tab 3: 3D Web Frontend     :5002"
echo ""
echo "  3D UI: http://localhost:5002"
echo "============================================"

kitty --session "$PROJECT_DIR/pepper_session.conf"
