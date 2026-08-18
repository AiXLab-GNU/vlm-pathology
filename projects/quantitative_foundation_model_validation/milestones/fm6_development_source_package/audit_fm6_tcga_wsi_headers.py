#!/usr/bin/env python3
"""Audit TCGA-PRAD development WSI headers without using outcome labels."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import tifffile


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MILESTONE_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = MILESTONE_ROOT / "outputs"
LOCAL_ROOT = (
    REPOSITORY_ROOT
    / "resources/data/quantitative_foundation_model_validation/local-data"
    / "tcga_prad_current_gdc_bcr"
)
SLIDE_TABLE = LOCAL_ROOT / "development_slides.csv"
SLIDE_ROOT = REPOSITORY_ROOT / "resources/data/shared/opendataset/TCGA-PRAD/slides"
LOCAL_HEADER_QC = LOCAL_ROOT / "development_wsi_header_qc.csv"
PROTOCOL_ID = "QFMV-FM6-TCGA-WSI-QC-2026-08-15-001"
FOV_UM = 394.24


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def aperio_value(description: str, key: str) -> str:
    match = re.search(rf"(?:^|\|){re.escape(key)}\s*=\s*([^|\r\n]+)", description)
    return match.group(1).strip() if match else ""


def thumbnail_qc(series: Any) -> tuple[bool, float | str, str]:
    try:
        level = series.levels[-1]
        shape = level.shape
        if len(shape) < 2 or int(np.prod(shape[:2])) > 32_000_000:
            return False, "", "smallest_pyramid_level_too_large"
        array = level.asarray()
        if array.ndim == 2:
            rgb = np.repeat(array[..., None], 3, axis=-1)
        else:
            rgb = array[..., :3]
        rgb = rgb.astype(np.float32) / 255.0
        maximum = rgb.max(axis=-1)
        minimum = rgb.min(axis=-1)
        saturation = (maximum - minimum) / np.maximum(maximum, 1e-6)
        tissue = (maximum < 0.95) & (saturation > 0.05)
        return True, round(float(tissue.mean()), 8), ""
    except Exception as error:
        return False, "", f"{type(error).__name__}:{error}"


def audit_slide(row: dict[str, str]) -> dict[str, Any]:
    path = SLIDE_ROOT / row["file_name"]
    result: dict[str, Any] = {
        "file_id": row["file_id"],
        "file_name": row["file_name"],
        "case_id": row["case_id"],
        "header_status": "FAIL",
        "thumbnail_decode_status": "FAIL",
        "error": "",
        "width_px": "",
        "height_px": "",
        "n_pages": "",
        "n_pyramid_levels": "",
        "mpp": "",
        "app_mag": "",
        "scanner_id": "",
        "compression": "",
        "is_tiled": "",
        "thumbnail_tissue_fraction_proxy": "",
        "native_pixels_for_394_24um": "",
    }
    if not path.is_file():
        result["error"] = "missing_local_file"
        return result
    try:
        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            description = str(page.description or "")
            mpp_text = aperio_value(description, "MPP")
            mpp = float(mpp_text) if mpp_text else None
            decoded, tissue_fraction, decode_error = thumbnail_qc(tif.series[0])
            result.update(
                {
                    "header_status": "PASS",
                    "thumbnail_decode_status": "PASS" if decoded else "FAIL",
                    "error": decode_error,
                    "width_px": int(page.imagewidth),
                    "height_px": int(page.imagelength),
                    "n_pages": len(tif.pages),
                    "n_pyramid_levels": len(tif.series[0].levels),
                    "mpp": mpp if mpp is not None else "",
                    "app_mag": aperio_value(description, "AppMag"),
                    "scanner_id": aperio_value(description, "ScanScope ID"),
                    "compression": str(page.compression.name),
                    "is_tiled": bool(page.is_tiled),
                    "thumbnail_tissue_fraction_proxy": tissue_fraction,
                    "native_pixels_for_394_24um": (
                        round(FOV_UM / mpp, 6) if mpp is not None and mpp > 0 else ""
                    ),
                }
            )
    except Exception as error:
        result["error"] = f"{type(error).__name__}:{error}"
    return result


def main() -> int:
    started = time.time()
    rows = read_csv(SLIDE_TABLE)
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        result = audit_slide(row)
        results.append(result)
        print(
            f"[{index}/{len(rows)}] {row['file_name']}: "
            f"header={result['header_status']} thumbnail={result['thumbnail_decode_status']}",
            flush=True,
        )
    write_csv(LOCAL_HEADER_QC, results, list(results[0]))

    header_pass = sum(row["header_status"] == "PASS" for row in results)
    decode_pass = sum(row["thumbnail_decode_status"] == "PASS" for row in results)
    mpp_complete = sum(row["mpp"] != "" for row in results)
    status_rows = [
        {"check": "local_slide_count", "value": len(results), "denominator": len(results), "status": "PASS"},
        {"check": "header_readable", "value": header_pass, "denominator": len(results), "status": "PASS" if header_pass == len(results) else "FAIL"},
        {"check": "thumbnail_decodable", "value": decode_pass, "denominator": len(results), "status": "PASS" if decode_pass == len(results) else "FAIL"},
        {"check": "mpp_complete", "value": mpp_complete, "denominator": len(results), "status": "PASS" if mpp_complete == len(results) else "FAIL"},
    ]
    status_path = OUTPUT_DIR / "fm6_tcga_wsi_header_qc_summary.csv"
    write_csv(status_path, status_rows, list(status_rows[0]))

    distribution_rows: list[dict[str, Any]] = []
    for field in ("mpp", "app_mag", "scanner_id", "compression", "n_pyramid_levels"):
        counts = Counter(str(row[field]) if row[field] != "" else "missing" for row in results)
        distribution_rows.extend(
            {"field": field, "value": value, "n_slides": count}
            for value, count in sorted(counts.items())
        )
    distribution_path = OUTPUT_DIR / "fm6_tcga_wsi_technical_distribution.csv"
    write_csv(distribution_path, distribution_rows, list(distribution_rows[0]))

    report_path = OUTPUT_DIR / "fm6-tcga-wsi-qc-report.md"
    report_path.write_text(
        f"""---
document_id: fm6-tcga-wsi-qc-report
owner_project: quantitative_foundation_model_validation
document_type: report
status: active
created: 2026-08-15
canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_development_source_package/outputs/fm6-tcga-wsi-qc-report.md
---

# FM6 TCGA-PRAD WSI 기술 QC 보고서

- Protocol: `{PROTOCOL_ID}`
- local slide: {len(results)}
- TIFF/SVS header readable: {header_pass}/{len(results)}
- lowest-pyramid thumbnail decode: {decode_pass}/{len(results)}
- MPP present: {mpp_complete}/{len(results)}
- physical FOV: `{FOV_UM} micrometre`; slide별 MPP에서 native pixel crop을 계산

thumbnail tissue fraction은 파일 decode와 gross tissue 존재를 확인하는 QC proxy일 뿐 tumor
mask나 사람 정량지표가 아니다. scanner ID, MPP와 pyramid 분포는 기술적 교란 층으로만
사용한다. 환자·slide별 header 표는 `never_serve` local-data이며 aggregate 표만
`project_internal`이다.
""",
        encoding="utf-8",
    )
    outputs = [status_path, distribution_path, report_path]
    config = {
        "protocol_id": PROTOCOL_ID,
        "fov_um": FOV_UM,
        "n_slides": len(results),
        "n_header_pass": header_pass,
        "n_thumbnail_decode_pass": decode_pass,
        "n_mpp_complete": mpp_complete,
        "local_header_qc_sha256": sha256_file(LOCAL_HEADER_QC),
        "script_sha256": sha256_file(Path(__file__)),
        "output_sha256": {path.name: sha256_file(path) for path in outputs},
        "execution_time_seconds": round(time.time() - started, 6),
        "volatile_fields": ["execution_time_seconds"],
    }
    config_path = OUTPUT_DIR / "fm6_tcga_wsi_qc_run_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(config, indent=2, sort_keys=True), flush=True)
    return 0 if header_pass == decode_pass == mpp_complete == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
