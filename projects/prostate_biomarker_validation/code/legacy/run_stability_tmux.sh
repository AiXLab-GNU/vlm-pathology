#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/jinhyun/prj_ws/prj_jin/vlm-pathology"
PYTHON_BIN="$PROJECT_ROOT/resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python"
LOG_DIR="$PROJECT_ROOT/resources/projects/prostate_biomarker_validation/model_workspace/stability_runs/logs"
export HF_HOME="/home/jinhyun/.cache/huggingface-jhkim"
export PYTHONUNBUFFERED=1
mkdir -p "$LOG_DIR"
cd "$PROJECT_ROOT"

case "${1:?runner name required}" in
  tcga_conch)
    CUDA_VISIBLE_DEVICES=1 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_tcga.py \
      --encoder CONCH --seeds 0 1 2 3 4 --mpps 0.88 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/tcga_conch.log"
    ;;
  tcga_virchow)
    CUDA_VISIBLE_DEVICES=2 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_tcga.py \
      --encoder Virchow --seeds 0 1 2 3 4 --mpps 0.44 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/tcga_virchow.log"
    ;;
  nadt_conch)
    CUDA_VISIBLE_DEVICES=3 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_nadt.py \
      --encoder CONCH --seeds 0 1 2 3 4 --mpps 0.88 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/nadt_conch.log"
    ;;
  nadt_virchow)
    CUDA_VISIBLE_DEVICES=4 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_nadt.py \
      --encoder Virchow --seeds 0 1 2 3 4 --mpps 0.44 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/nadt_virchow.log"
    ;;
  marker7)
    CUDA_VISIBLE_DEVICES=5 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_marker7.py \
      --encoder CONCH --seeds 0 1 2 3 4 --mpps 0.88 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/marker7_conch.log"
    CUDA_VISIBLE_DEVICES=5 "$PYTHON_BIN" resources/projects/prostate_biomarker_validation/model_workspace/run_stability_marker7.py \
      --encoder Virchow --seeds 0 1 2 3 4 --mpps 0.44 1.76 \
      --tile-counts 16 32 64 --output-tag full 2>&1 | tee -a "$LOG_DIR/marker7_virchow.log"
    ;;
  *)
    echo "unknown runner: $1" >&2
    exit 2
    ;;
esac
