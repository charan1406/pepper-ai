#!/bin/bash
# Production: single 4B brain on 6GB GPU + vision
# Full GPU offload, mmproj enabled, larger context

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"
MMPROJ="$HOME/models/mmproj-F16.gguf"

echo "============================================"
echo "  PEPPER AI — Production Mode (6GB VRAM)"
echo "  4B: thinking=ON + vision"
echo "============================================"

"$LLAMA_BIN" \
  -m "$MODEL" \
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
  --spec-ngram-size-n 12 --spec-ngram-size-m 48
