#!/bin/bash
# Start the Deep Brain — Qwen3.5-4B on GPU (port 8090)
# Settings derived from proven Jarvis config, adapted for Pepper

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"
# MMPROJ="$HOME/models/mmproj-F16.gguf"  # Uncomment on 6GB GPU

if [ ! -f "$MODEL" ]; then
    echo "  ✗ Model not found: $MODEL"
    exit 1
fi

echo "============================================"
echo "  DEEP BRAIN — Qwen3.5-4B Q4_K_M"
echo "  Port: 8090  |  GPU (26 layers)  |  8K ctx"
echo "============================================"

"$LLAMA_BIN" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port 8090 \
  -ngl 26 \
  -np 1 \
  -c 8192 \
  -fa on \
  -ctk q4_0 \
  -ctv q4_0 \
  --swa-full \
  --no-mmap \
  -fit off \
  --jinja \
  --threads 8 \
  --threads-batch 16 \
  --reasoning-budget 1024 \
  --spec-type ngram-mod \
  --draft-max 48 \
  --draft-min 0 \
  --spec-ngram-size-n 12 \
  --spec-ngram-size-m 48

# ─── 6GB GPU version: increase -ngl to 32 (all layers) ───
# ─── and add --mmproj "$MMPROJ" for vision ───
