#!/bin/bash
# Dev mode: single 4B brain on 4GB VRAM
# Thinking ON, reasoning_budget=1024, ctx=8192
# Pinned llama.cpp: build 8861 (cf8b0dbda) — do not update without testing

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"

echo "============================================"
echo "  PEPPER AI — Dev Mode (4GB VRAM)"
echo "  4B: thinking=ON, budget=1024, ngl=99"
echo "============================================"

"$LLAMA_BIN" \
  -m "$MODEL" \
  --host 0.0.0.0 --port 8090 \
  -ngl 99 -np 1 -c 8192 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --swa-full --no-mmap -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024 \
  --threads 8 --threads-batch 16 \
  --spec-type ngram-mod --draft-max 48 --draft-min 0 \
  --spec-ngram-size-n 12 --spec-ngram-size-m 48
