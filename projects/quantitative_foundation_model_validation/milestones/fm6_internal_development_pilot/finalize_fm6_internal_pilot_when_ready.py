#!/usr/bin/env python3
"""Persistently assemble and analyze the FM6 pilot after all GPU shards finish."""
from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MILESTONE = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot"
EXTRACT = MILESTONE / "run_fm6_tcga_internal_pilot.py"
ANALYZE = MILESTONE / "analyze_fm6_tcga_internal_pilot.py"
RENDER = MILESTONE / "render_fm6_internal_pilot_figures.py"
OUTPUTS = MILESTONE / "outputs"
LOCAL = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot/slide_cache"
PYTHON = ROOT / "resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python"
EXPECTED_SLIDES = 437


def stamp(message: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def count(encoder: str) -> int:
    path = LOCAL / encoder
    return sum(1 for _ in path.glob("*.npz")) if path.exists() else 0


def run(command: list[str]) -> None:
    stamp("RUN " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    last = None
    while True:
        state = (count("conch"), count("virchow"))
        if state != last:
            stamp(f"cache progress conch={state[0]}/{EXPECTED_SLIDES} virchow={state[1]}/{EXPECTED_SLIDES}")
            last = state
        if state == (EXPECTED_SLIDES, EXPECTED_SLIDES):
            break
        time.sleep(30)
    run([str(PYTHON), str(EXTRACT), "assemble", "--encoder", "conch"])
    run([str(PYTHON), str(EXTRACT), "assemble", "--encoder", "virchow"])
    run([str(PYTHON), str(ANALYZE)])
    run([str(PYTHON), str(RENDER)])
    stamp("FM6 internal pilot pipeline complete")


if __name__ == "__main__":
    main()
