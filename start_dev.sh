#!/bin/bash
# Dev mode: both brains sharing 4GB VRAM
# Both think — small models NEED chain-of-thought for quality
# 4B: reasoning_budget=1024 | 0.8B: reasoning_budget=512

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
DEEP_MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"
FAST_MODEL="$HOME/models/Qwen3.5-0.8B.Q4_K_M.gguf"

MODE="${1:-both}"

start_deep() {
    echo "  Starting Deep Brain (4B, think=ON, budget=1024) on :8090..."
    "$LLAMA_BIN" \
      -m "$DEEP_MODEL" \
      --host 0.0.0.0 --port 8090 \
      -ngl 24 -np 1 -c 8192 \
      -fa on -ctk q4_0 -ctv q4_0 \
      --swa-full --no-mmap -fit off \
      --jinja \
      --chat-template-kwargs '{"enable_thinking":true}' \
      --reasoning-budget 1024 \
      --threads 8 --threads-batch 16 \
      --spec-type ngram-mod --draft-max 48 --draft-min 0 \
      --spec-ngram-size-n 12 --spec-ngram-size-m 48
}

start_fast() {
    echo "  Starting Fast Brain (0.8B, think=ON, budget=512) on :8091..."
    "$LLAMA_BIN" \
      -m "$FAST_MODEL" \
      --host 0.0.0.0 --port 8091 \
      -ngl 10 -np 1 -c 2048 \
      -fa on -ctk q4_0 -ctv q4_0 \
      -fit off \
      --jinja \
      --chat-template-kwargs '{"enable_thinking":true}' \
      --reasoning-budget 512 \
      --threads 8 --threads-batch 16
}

case "$MODE" in
    deep)  start_deep ;;
    fast)  start_fast ;;
    both)
        echo "============================================"
        echo "  PEPPER AI — Dev Mode (4GB shared VRAM)"
        echo "  Both brains think (small models need it)"
        echo "  4B budget=1024 | 0.8B budget=512"
        echo "============================================"
        start_deep &
        for i in $(seq 1 60); do
            curl -s http://localhost:8090/health > /dev/null 2>&1 && break; sleep 1
        done
        echo "  ✓ Deep brain ready"
        start_fast &
        for i in $(seq 1 90); do
            curl -s http://localhost:8091/health > /dev/null 2>&1 && break; sleep 1
        done
        echo "  ✓ Fast brain ready"
        echo ""
        echo "  Both brains running!"
        echo "  Press Ctrl+C to stop"
        wait
        ;;
    *)
        echo "Usage: $0 [deep|fast|both]"
        ;;
esac
