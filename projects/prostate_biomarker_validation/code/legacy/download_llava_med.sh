#!/usr/bin/env bash
# Downloads LLaVA-Med (weights + inference codebase) for the 4-model VLM hallucination
# benchmark (see docs/05_vlm_benchmark_task_prompt.md). Modeled directly on
# resources/projects/prostate_biomarker_validation/model_workspace/download_quilt_llava.sh -- same layout, same steps.
#
# Weights:  microsoft/llava-med-v1.5-mistral-7b (Hugging Face, full standalone weights,
#           NOT a delta -- no separate Vicuna/Mistral base merge needed, ~15GB)
# Code:     https://github.com/microsoft/LLaVA-Med.git
#
# IMPORTANT (naming): the local weights dir MUST have "mistral" in its basename --
# llava-med-code/llava/mm_utils.py's get_model_name_from_path() derives the model name
# from the last path component, and llava/model/builder.py branches on 'mistral' in
# that name to pick LlavaMistralForCausalLM. Hence WEIGHTS_DIR below is
# "llava-med-v1.5-mistral-7b", not a generic "llava-med-weights".
#
# IMPORTANT (venv): LLaVA-Med v1.5's pyproject.toml pins transformers==4.36.2 /
# tokenizers>=0.15.0, which conflicts with resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt's transformers==4.31.0 /
# tokenizers==0.13.3 (required by the older quilt-llava-code fork). Per project policy,
# .venv-quilt is left untouched -- this script targets a SEPARATE venv,
# resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed. To build it from scratch:
#   uv venv --python 3.11 resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed
#   uv pip install --python resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python torch torchvision
#   uv pip install --python resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python -e resources/projects/prostate_biomarker_validation/model_workspace/llava-med-code
#   uv pip install --python resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python -U bitsandbytes
# The last line is required: llava-med-code's pyproject pins bitsandbytes==0.41.0, which
# hard-crashes at import time on this machine's CUDA 13.x driver/torch build ("CUDA Setup
# failed despite GPU being available"). bitsandbytes is only used for optional 8bit/4bit
# quantization (unused by our fp16 inference path), so upgrading it to latest (tested with
# 0.50.0) is safe and unblocks the import chain (transformers -> accelerate -> bitsandbytes).
#
# NOTE: at first inference, llava/model/multimodal_encoder/clip_encoder.py pulls the
# CLIP vision tower (openai/clip-vit-large-patch14-336, ~1.7GB) from the HF hub
# automatically via from_pretrained() -- requires internet access at model-load time.
#
# Usage: ./resources/projects/prostate_biomarker_validation/model_workspace/download_llava_med.sh   (run from repo root or anywhere; paths are
#                                           resolved relative to this script's location)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/resources/projects/prostate_biomarker_validation/model_workspace/.venv-llavamed/bin/python"
MODELS_DIR="$REPO_ROOT/models"
WEIGHTS_DIR="$MODELS_DIR/llava-med-v1.5-mistral-7b"
CODE_DIR="$MODELS_DIR/llava-med-code"

if [ ! -x "$VENV_PY" ]; then
    echo "error: $VENV_PY not found -- create it first, e.g.:" >&2
    echo "    uv venv --python 3.11 $MODELS_DIR/.venv-llavamed" >&2
    echo "    uv pip install --python $VENV_PY torch torchvision" >&2
    echo "    uv pip install --python $VENV_PY -e $CODE_DIR   (after cloning below)" >&2
    exit 1
fi

echo "== disk space check =="
df -h "$REPO_ROOT"

echo "== 1/3: ensuring huggingface_hub is installed in .venv-llavamed =="
"$VENV_PY" -c "import huggingface_hub" 2>/dev/null || uv pip install --python "$VENV_PY" huggingface_hub

echo "== 2/3: downloading model weights to $WEIGHTS_DIR (~15GB) =="
if [ -d "$WEIGHTS_DIR" ] && [ -n "$(ls -A "$WEIGHTS_DIR" 2>/dev/null)" ]; then
    echo "  already present, skipping (delete $WEIGHTS_DIR to force re-download)"
else
    "$VENV_PY" -c "
from huggingface_hub import snapshot_download
snapshot_download('microsoft/llava-med-v1.5-mistral-7b', local_dir='$WEIGHTS_DIR')
"
fi

echo "== 3/3: cloning inference codebase to $CODE_DIR =="
if [ -d "$CODE_DIR" ]; then
    echo "  already present, skipping (git pull manually inside $CODE_DIR to update)"
else
    git clone https://github.com/microsoft/LLaVA-Med.git "$CODE_DIR"
fi

echo ""
echo "Done."
echo "Weights: $WEIGHTS_DIR"
echo "Code:    $CODE_DIR"
echo "Next:    uv pip install --python $VENV_PY -e $CODE_DIR"
echo "         (pins transformers==4.36.2, tokenizers>=0.15.0 -- separate venv from .venv-quilt)"
echo "         uv pip install --python $VENV_PY -U bitsandbytes"
echo "         (required -- the pinned bitsandbytes==0.41.0 crashes on import with this"
echo "         machine's CUDA 13.x driver; upgrading is safe since 8bit/4bit are unused here)"
