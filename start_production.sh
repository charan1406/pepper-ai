#!/bin/bash
# Production: both brains on 6GB GPU + vision
# 4B: all layers + mmproj + thinking | 0.8B: all layers + no thinking

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
DEEP_MODEL="$HOME/models/Qwen3.5-4B-Q4_K_M.gguf"
FAST_MODEL="$HOME/models/Qwen3.5-0.8B.Q4_K_M.gguf"
MMPROJ="$HOME/models/mmproj-F16.gguf"

echo "============================================"
echo "  PEPPER AI — Production Mode (6GB VRAM)"
echo "  Deep: thinking=ON + vision"
echo "  Fast: thinking=OFF (instant responses)"
echo "============================================"

"$LLAMA_BIN" \
  -m "$DEEP_MODEL" \
  --mmproj "$MMPROJ" \
  --host 0.0.0.0 --port 8090 \
  -ngl 32 -np 1 -c 8192 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --swa-full --no-mmap -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024 \
  --threads 8 --threads-batch 16 \
  --spec-type ngram-mod --draft-max 48 --draft-min 0 \
  --spec-ngram-size-n 12 --spec-ngram-size-m 48 &

DEEP_PID=$!
for i in $(seq 1 60); do
    curl -s http://localhost:8090/health > /dev/null 2>&1 && break; sleep 1
done
echo "  ✓ Deep brain ready (PID: $DEEP_PID)"

"$LLAMA_BIN" \
  -m "$FAST_MODEL" \
  --host 0.0.0.0 --port 8091 \
  -ngl 99 -np 1 -c 2048 \
  -fa on -ctk q4_0 -ctv q4_0 \
  -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --threads 8 --threads-batch 16 &

FAST_PID=$!
for i in $(seq 1 30); do
    curl -s http://localhost:8091/health > /dev/null 2>&1 && break; sleep 1
done
echo "  ✓ Fast brain ready (PID: $FAST_PID)"
echo ""
echo "  Press Ctrl+C to stop"
wait
