#!/usr/bin/env bash
# Downloads Quilt-LLaVA (weights + inference codebase) for the VLM-bridge experiments
# discussed alongside the NADT-Prostate H&E structural-density validation.
#
# Weights:  wisdomik/Quilt-Llava-v1.5-7b (Hugging Face, ~14GB)
# Code:     https://github.com/aldraus/quilt-llava
# Paper:    https://arxiv.org/abs/2312.04746
#
# Usage: ./resources/projects/prostate_biomarker_validation/model_workspace/download_quilt_llava.sh   (run from repo root or anywhere; paths are
#                                             resolved relative to this script's location)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/.venv/bin/python"
MODELS_DIR="$REPO_ROOT/models"
WEIGHTS_DIR="$MODELS_DIR/Quilt-Llava-v1.5-7b"
CODE_DIR="$MODELS_DIR/quilt-llava-code"

if [ ! -x "$VENV_PY" ]; then
    echo "error: $VENV_PY not found -- run this from a checkout with .venv already set up." >&2
    exit 1
fi

echo "== disk space check =="
df -h "$REPO_ROOT"

echo "== 1/3: ensuring huggingface_hub is installed in .venv =="
"$VENV_PY" -c "import huggingface_hub" 2>/dev/null || uv pip install --python "$VENV_PY" huggingface_hub

echo "== 2/3: downloading model weights to $WEIGHTS_DIR (~14GB) =="
if [ -d "$WEIGHTS_DIR" ] && [ -n "$(ls -A "$WEIGHTS_DIR" 2>/dev/null)" ]; then
    echo "  already present, skipping (delete $WEIGHTS_DIR to force re-download)"
else
    "$VENV_PY" -c "
from huggingface_hub import snapshot_download
snapshot_download('wisdomik/Quilt-Llava-v1.5-7b', local_dir='$WEIGHTS_DIR')
"
fi

echo "== 3/3: cloning inference codebase to $CODE_DIR =="
if [ -d "$CODE_DIR" ]; then
    echo "  already present, skipping (git pull manually inside $CODE_DIR to update)"
else
    git clone https://github.com/aldraus/quilt-llava.git "$CODE_DIR"
fi

echo ""
echo "Done."
echo "Weights: $WEIGHTS_DIR"
echo "Code:    $CODE_DIR (see its README/requirements.txt before running inference --"
echo "         LLaVA-based repos typically pin specific torch/transformers versions)"
