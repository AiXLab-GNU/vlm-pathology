#!/usr/bin/env python3
"""Acquire and verify the locked PAR primary-scanner WSI source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

import tifffile


ROOT = Path(__file__).resolve().parents[4]
LOCAL_ROOT = ROOT / "resources/data/quantitative_foundation_model_validation/local-data/par_s_biad2323"
FILE_LIST = LOCAL_ROOT / "file_list_component_B.tsv"
WSI_ROOT = LOCAL_ROOT / "hamamatsu"
REMOTE_INVENTORY = LOCAL_ROOT / "hamamatsu_remote_inventory.csv"
LOCAL_AUDIT = LOCAL_ROOT / "hamamatsu_local_audit.json"
BASE_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/biostudies/S-BIAD/323/S-BIAD2323/Files/"
)
USER_AGENT = "vlm-pathology-qfm-par-acquisition/1.0"


def read_source_paths() -> list[str]:
    with FILE_LIST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    paths = [row["Files"].strip() for row in rows if row.get("Files", "").strip()]
    if len(paths) != 339 or len(paths) != len(set(paths)):
        raise ValueError(f"expected 339 unique Hamamatsu paths, observed {len(paths)}")
    if any(not path.endswith("_hamamatsu.ndpi") for path in paths):
        raise ValueError("non-Hamamatsu file in primary-scanner list")
    return paths


def patient_id(path: str) -> str:
    match = re.search(r"/c(\d{3})(?:[ab])?_hamamatsu\.ndpi$", path, re.IGNORECASE)
    if not match:
        raise ValueError(path)
    return f"C{match.group(1)}"


def request(path: str, method: str = "HEAD", range_start: int | None = None):
    headers = {"User-Agent": USER_AGENT}
    if range_start is not None and range_start > 0:
        headers["Range"] = f"bytes={range_start}-"
    return urllib.request.Request(BASE_URL + path, method=method, headers=headers)


def head_one(path: str, retries: int = 5) -> dict[str, object]:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request(path), timeout=60) as response:
                return {
                    "patient_id": patient_id(path),
                    "remote_path": path,
                    "file_name": Path(path).name,
                    "expected_bytes": int(response.headers["Content-Length"]),
                    "etag": response.headers.get("ETag", "").strip('"'),
                    "last_modified": response.headers.get("Last-Modified", ""),
                    "status": "REMOTE_READY",
                }
        except (OSError, urllib.error.URLError) as error:
            if attempt + 1 == retries:
                raise RuntimeError(f"HEAD failed for {path}: {error}") from error
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def write_inventory(rows: Sequence[dict[str, object]]) -> None:
    fields = [
        "patient_id",
        "remote_path",
        "file_name",
        "expected_bytes",
        "etag",
        "last_modified",
        "status",
    ]
    with REMOTE_INVENTORY.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: str(row["file_name"])))


def build_remote_inventory(workers: int) -> list[dict[str, object]]:
    paths = read_source_paths()
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(head_one, path): path for path in paths}
        for future in as_completed(futures):
            rows.append(future.result())
    if len({row["patient_id"] for row in rows}) != 185:
        raise ValueError("PAR patient identity contract did not yield 185 patients")
    write_inventory(rows)
    print(
        "PAR remote inventory: "
        f"files={len(rows)} patients=185 bytes={sum(int(row['expected_bytes']) for row in rows)}"
    )
    return rows


def read_inventory() -> list[dict[str, str]]:
    if not REMOTE_INVENTORY.is_file():
        raise FileNotFoundError(f"run audit-remote first: {REMOTE_INVENTORY}")
    with REMOTE_INVENTORY.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 339:
        raise ValueError(f"expected 339 inventory rows, observed {len(rows)}")
    return rows


def download_one(row: dict[str, str], retries: int = 8) -> str:
    WSI_ROOT.mkdir(parents=True, exist_ok=True)
    final_path = WSI_ROOT / row["file_name"]
    partial_path = final_path.with_suffix(final_path.suffix + ".partial")
    expected = int(row["expected_bytes"])
    if final_path.is_file() and final_path.stat().st_size == expected:
        return "EXISTING_COMPLETE"
    if final_path.exists():
        raise ValueError(f"wrong-size completed path: {final_path}")

    for attempt in range(retries):
        start = partial_path.stat().st_size if partial_path.exists() else 0
        try:
            with urllib.request.urlopen(request(row["remote_path"], "GET", start), timeout=180) as response:
                if start and response.status != 206:
                    start = 0
                mode = "ab" if start and response.status == 206 else "wb"
                with partial_path.open(mode) as handle:
                    while True:
                        chunk = response.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            if partial_path.stat().st_size == expected:
                os.replace(partial_path, final_path)
                return "DOWNLOADED_COMPLETE"
            if partial_path.stat().st_size > expected:
                raise ValueError(f"download exceeds expected size: {partial_path}")
        except (OSError, urllib.error.URLError) as error:
            if attempt + 1 == retries:
                raise RuntimeError(f"download failed for {row['file_name']}: {error}") from error
        time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"incomplete after retries: {row['file_name']}")


def download_all(workers: int) -> None:
    rows = read_inventory()
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_one, row): row["file_name"] for row in rows}
        for index, future in enumerate(as_completed(futures), start=1):
            status = future.result()
            counts[status] = counts.get(status, 0) + 1
            if index % 10 == 0 or index == len(rows):
                print(f"PAR download progress: {index}/{len(rows)} {counts}", flush=True)
    audit_local(hash_files=False)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_openability(path: Path) -> tuple[bool, str]:
    import openslide

    try:
        with tifffile.TiffFile(path) as tif:
            page = tif.series[0].levels[0].pages[0]
            if not page.is_tiled or page.samplesperpixel < 3:
                return False, "level0_not_tiled_rgb"
            expected_dimensions = (int(page.imagewidth), int(page.imagelength))
        slide = openslide.OpenSlide(str(path))
        try:
            if slide.dimensions != expected_dimensions:
                return False, "openslide_tifffile_dimension_mismatch"
            width, height = slide.dimensions
            region = slide.read_region(
                (max((width - 256) // 2, 0), max((height - 256) // 2, 0)),
                0,
                (min(256, width), min(256, height)),
            ).convert("RGB")
            if region.size[0] <= 0 or region.size[1] <= 0:
                return False, "openslide_center_region_empty"
        finally:
            slide.close()
        return True, ""
    except Exception as error:  # source audit must preserve exact failing file/error
        return False, f"{type(error).__name__}: {error}"


def audit_local(hash_files: bool) -> dict[str, object]:
    rows = read_inventory()
    complete = []
    missing = []
    wrong_size = []
    file_hashes: dict[str, str] = {}
    openability_errors: dict[str, str] = {}
    openable_files = 0
    for row in rows:
        path = WSI_ROOT / row["file_name"]
        if not path.is_file():
            missing.append(row["file_name"])
            continue
        if path.stat().st_size != int(row["expected_bytes"]):
            wrong_size.append(row["file_name"])
            continue
        complete.append(row["file_name"])
        if hash_files:
            file_hashes[row["file_name"]] = file_sha256(path)
            openable, error = decode_openability(path)
            if openable:
                openable_files += 1
            else:
                openability_errors[row["file_name"]] = error
    complete_payload = len(complete) == len(rows) and not wrong_size
    verified_payload = (
        complete_payload
        and hash_files
        and len(file_hashes) == len(rows)
        and openable_files == len(rows)
        and not openability_errors
    )
    result = {
        "expected_files": len(rows),
        "expected_patients": len({row["patient_id"] for row in rows}),
        "expected_bytes": sum(int(row["expected_bytes"]) for row in rows),
        "complete_files": len(complete),
        "missing_files": len(missing),
        "wrong_size_files": len(wrong_size),
        "complete_bytes": sum((WSI_ROOT / name).stat().st_size for name in complete),
        "hash_mode": hash_files,
        "openability_decoder": "openslide",
        "openslide_version": openslide_version(),
        "file_sha256": file_hashes,
        "openable_files": openable_files,
        "openability_errors": openability_errors,
        "status": (
            "PASS_HASHED_OPENABLE"
            if verified_payload
            else "COMPLETE_UNHASHED"
            if complete_payload
            else "NOT_READY"
        ),
    }
    LOCAL_AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"PAR local audit: {result['status']} complete={len(complete)}/{len(rows)} "
        f"wrong_size={len(wrong_size)}"
    )
    return result


def openslide_version() -> str:
    import openslide

    return f"python={openslide.__version__};library={openslide.__library_version__}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("audit-remote", "download", "audit-local"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--hash", action="store_true", help="hash every completed WSI during local audit")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    if args.stage == "audit-remote":
        build_remote_inventory(args.workers)
    elif args.stage == "download":
        download_all(args.workers)
    else:
        audit_local(args.hash)


if __name__ == "__main__":
    main()
