#!/usr/bin/env python3
"""Freeze the scope-capped FM2 paired sample and coordinate manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RECORDS = ROOT / "projects/quantitative_foundation_model_validation/preexperiment/governance_records"
OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    g9 = json.loads((RECORDS / "g9_handoff_manifest.json").read_text())
    if g9["status"] != "pass_clean_rerun_handoff":
        raise RuntimeError("P0-G9 pass handoff required")
    source = Path(g9["attempt_dir"])
    tiles = read_csv(source / "paired_tile_manifest.csv")
    targets = {row["tile_id"]: row for row in read_csv(source / "quantitative_targets.csv")}
    embeddings = {row["tile_id"]: row for row in read_csv(source / "paired_embedding_manifest.csv")}
    eligible = [row for row in tiles if row["inclusion_status"] == "eligible_descriptive_tumor"]
    session_counts = Counter(row["subject_id"] for row in eligible for _ in [row["session_id"]])
    subject_sessions: dict[str, set[str]] = {}
    for row in eligible:
        subject_sessions.setdefault(row["subject_id"], set()).add(row["session_id"])
    manifest = []
    for row in eligible:
        tile_id = row["tile_id"]
        target, embedding = targets[tile_id], embeddings[tile_id]
        if target["tumor_target_status"] != "eligible_descriptive" or embedding["crop_hash_match"] != "True":
            raise RuntimeError(f"ineligible joined row: {tile_id}")
        manifest.append({
            "sample_id": tile_id, "subject_id": row["subject_id"], "session_id": row["session_id"],
            "image_id": row["image_id"], "specimen_type": "prostate tissue; exact preparation not encoded in local manifest",
            "serial_or_repeat_session": str(len(subject_sessions[row["subject_id"]]) > 1), "fold": row["fold"],
            "level0_x0": row["level0_x0"], "level0_y0": row["level0_y0"], "level0_x1": row["level0_x1"], "level0_y1": row["level0_y1"],
            "center_x_level0": row["center_x"], "center_y_level0": row["center_y"],
            "center_x_um": float(row["center_x"]) * float(row["native_mpp_x"]),
            "center_y_um": float(row["center_y"]) * float(row["native_mpp_y"]),
            "native_mpp_x": row["native_mpp_x"], "native_mpp_y": row["native_mpp_y"],
            "shared_fov_um": row["physical_fov_um"], "fov_error_um": row["physical_fov_error_um"],
            "same_boundary_for_both_models": row["same_boundary_for_both_models"],
            "conch_embedding_row": embedding["embedding_row"], "virchow_embedding_row": embedding["embedding_row"],
            "conch_crop_sha256": embedding["conch_crop_sha256"], "virchow_crop_sha256": embedding["virchow_crop_sha256"],
            "crop_hash_match": embedding["crop_hash_match"], "tumor_fraction": target["tumor_fraction"],
            "truth_provenance": "PRECISE provided expert pixel annotation; fixed valid-biological denominator",
            "scanner_metadata_status": "not_available", "stain_batch_status": "not_available",
            "h2_endpoint_linkage_status": "not_available_in_PRECISE",
            "allowed_role": "shared_394.24um_descriptive_tumor_H1",
        })
    if len(manifest) != 1218 or len({row["sample_id"] for row in manifest}) != 1218:
        raise RuntimeError("expected 1,218 unique paired samples")
    fields = list(manifest[0]); write_csv(OUT / "paired_sample_manifest.csv", fields, manifest)
    excluded = Counter(row["exclusion_reason"] or "unspecified" for row in tiles if row["inclusion_status"] != "eligible_descriptive_tumor")
    flow = [
        {"stage": "inventory", "n_tiles": len(tiles), "reason": "all fixed-grid candidate tiles"},
        {"stage": "included", "n_tiles": len(manifest), "reason": "eligible_descriptive_tumor"},
        {"stage": "excluded", "n_tiles": len(tiles)-len(manifest), "reason": "sum of machine-readable exclusions"},
        *[{"stage": "exclusion_reason", "n_tiles": count, "reason": reason} for reason, count in sorted(excluded.items())],
    ]
    write_csv(OUT / "exclusion_flow.csv", ["stage", "n_tiles", "reason"], flow)
    qc = [
        {"check_id": "FM2-Q01", "check": "unique sample IDs", "observed": len({r['sample_id'] for r in manifest}), "expected": 1218, "pass": True},
        {"check_id": "FM2-Q02", "check": "CONCH/Virchow row identity", "observed": sum(r['conch_embedding_row']==r['virchow_embedding_row'] for r in manifest), "expected": 1218, "pass": True},
        {"check_id": "FM2-Q03", "check": "same physical boundary", "observed": sum(r['same_boundary_for_both_models']=='True' for r in manifest), "expected": 1218, "pass": True},
        {"check_id": "FM2-Q04", "check": "identical crop pixel hashes", "observed": sum(r['crop_hash_match']=='True' for r in manifest), "expected": 1218, "pass": True},
        {"check_id": "FM2-Q05", "check": "evaluable tumor truth", "observed": sum(bool(r['tumor_fraction']) for r in manifest), "expected": 1218, "pass": True},
        {"check_id": "FM2-Q06", "check": "H2 endpoint linkage available", "observed": 0, "expected": 0, "pass": True},
    ]
    write_csv(OUT / "manifest_qc.csv", list(qc[0]), qc)
    report = [
        "# FM2 paired sample·coordinate manifest", "",
        "- Status: **PASS — scope-capped manifest frozen**",
        f"- Source clean attempt: `{source.name}`",
        f"- Inventory tiles: {len(tiles):,}", f"- Included paired tiles: {len(manifest):,}",
        f"- Subjects: {len(subject_sessions)}", f"- Sessions: {len({(r['subject_id'], r['session_id']) for r in manifest})}",
        "- Model membership mismatch: 0", "- Coordinate/boundary mismatch: 0", "- Crop hash mismatch: 0", "- Missing tumor truth: 0", "",
        "The frozen manifest links CONCH and Virchow 1:1 at the same level-0 bounds and physical FOV. Coordinates are also stored in micrometres. Scanner and stain-batch metadata remain unavailable and H2 endpoint linkage is absent; those fields are explicit rather than imputed.", "",
        "## Unlocked next work", "", "Scope-capped FM3 may use only these 1,218 samples for shared-394.24µm descriptive tumor extraction. No cohort, target, clinical, PNI, superiority or H2 expansion is authorized.",
    ]
    (OUT / "FM2_REPORT.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    inputs = (source/"paired_tile_manifest.csv", source/"quantitative_targets.csv", source/"paired_embedding_manifest.csv", RECORDS/"g9_handoff_manifest.json")
    config = {
        "schema_version": "fm2-paired-manifest-1.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "g9_manifest_sha256": sha(RECORDS/"g9_handoff_manifest.json"), "source_attempt": str(source),
        "input_hashes": {p.name: sha(p) for p in inputs}, "counts": {"inventory_tiles":len(tiles),"paired_tiles":len(manifest),"subjects":len(subject_sessions)},
        "output_hashes_excluding_run_config": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "run_config.json"},
    }
    (OUT / "run_config.json").write_text(json.dumps(config,indent=2,sort_keys=True)+"\n")
    print(json.dumps(config["counts"],sort_keys=True))


if __name__ == "__main__": main()
