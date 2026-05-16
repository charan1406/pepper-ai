#!/bin/bash
# Start the Fast Brain — Qwen3.5-0.8B on CPU (port 8091)
# CUDA hidden to preserve all VRAM for the deep brain

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-0.8B.Q4_K_M.gguf"

if [ ! -f "$MODEL" ]; then
    echo "  ✗ Model not found: $MODEL"
    exit 1
fi

echo "============================================"
echo "  FAST BRAIN — Qwen3.5-0.8B Q4_K_M"
echo "  Port: 8091  |  CPU only  |  2K ctx"
echo "  Reasoning: enabled (budget 256)"
echo "============================================"

CUDA_VISIBLE_DEVICES="" "$LLAMA_BIN" \
  -m "$MODEL" \
  --host 0.0.0.0 \
  --port 8091 \
  -ngl 0 \
  -np 1 \
  -c 2048 \
  -fa on \
  -ctk q4_0 \
  -ctv q4_0 \
  --no-mmap \
  -fit off \
  --jinja \
  --threads $(nproc) \
  --threads-batch $(nproc) \
  --reasoning-budget 256
