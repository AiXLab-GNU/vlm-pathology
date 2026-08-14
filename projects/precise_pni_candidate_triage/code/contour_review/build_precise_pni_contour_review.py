"""Build and validate the approved PRECISE PNI contour-review package.

The build stage creates private case provenance, QuPath-compatible locator-only
GeoJSON files, and blank status templates. It never creates pathology contours.
The validate stage checks completed specialist exports without repairing them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import PIL
import tifffile

from projects.precise_pni_candidate_triage.code.morphology_rereview.build_precise_pni_morphology_review import (
    centered_crop_origins,
    crop_with_padding,
    jpeg_uri,
)


ROOT = Path(__file__).resolve().parents[4]
PRECISE = ROOT / "resources/data/shared/opendataset/PRECISE"
MORPHOLOGY_ROOT = PRECISE / "pni_morphology_rereview"
LOCKED_ROOT = MORPHOLOGY_ROOT / "locked"
DEFAULT_MAPPING = MORPHOLOGY_ROOT / "private_case_mapping.csv"
DEFAULT_LOCKED_REVIEW = LOCKED_ROOT / "normalized_morphology_review.csv"
DEFAULT_ELIGIBILITY = LOCKED_ROOT / "contour_eligibility_table.csv"
DEFAULT_LOCK_CONFIG = LOCKED_ROOT / "run_config.json"
DEFAULT_PROTOCOL = ROOT / "projects/precise_pni_candidate_triage/docs/pathologist_protocol/PRECISE_PNI_CONTOUR_PROTOCOL_KO.md"
DEFAULT_IMMUTABLE_REVIEW = PRECISE / "precise_pni_review (1).csv"
DEFAULT_OUTPUT = PRECISE / "pni_contour_review"
EXPECTED_IMMUTABLE_REVIEW_SHA256 = "c1dd522b4ff4f233b3a23630bf9074da881bb7b9145996fc47c3383a0448d2a3"
PROTOCOL_VERSION = "1.0"
CONTACT_TOLERANCE_UM = 1.0
COORDINATE_SYSTEM = "H&E_WSI_level0_pixels_origin_top_left"

MANIFEST_REQUIRED = [
    "temporary_id", "candidate_id", "subject_id", "image_id", "x0", "y0",
    "window_px", "window_um",
]
LOCKED_REQUIRED = [
    "temporary_id", "pni_status", "overall_relation", "nerve_multiplicity",
]
ELIGIBILITY_REQUIRED = [
    "temporary_id", "contour_disposition", "unresolved_morphology_fields",
]
WSI_REQUIRED = [
    "image_id", "wsi_path", "wsi_sha256", "width_px", "height_px", "mpp_x", "mpp_y",
]

STATUS_COLUMNS = [
    "temporary_id", "candidate_id", "image_id", "review_stream", "locked_pni_status",
    "locked_overall_relation", "m5_contour_disposition", "index_nerve_annotation_id",
    "required_object_completeness", "contour_status", "approval_status",
    "adjudication_required", "adjudication_result", "evidence_mode", "ihc_used",
    "registration_qc", "partial_or_not_evaluable_reason", "index_nerve_uncertain",
    "reviewer_id", "revision_number", "review_timestamp_utc", "reviewer_notes",
]

FEATURE_REQUIRED_PROPERTIES = [
    "annotation_id", "temporary_id", "object_type", "object_role",
    "parent_annotation_id", "reviewer_id", "review_stage", "evidence_mode",
    "source", "approval_status", "contour_completeness", "revision_number",
    "reviewer_notes",
]

OBJECT_GEOMETRIES = {
    "nerve_outer_boundary": {"Polygon"},
    "additional_nerve_boundary": {"Polygon"},
    "tumor_boundary": {"Polygon", "MultiPolygon"},
    "contact_segment": {"LineString"},
    "encasement_arc": {"LineString"},
    "intraneural_region": {"Polygon"},
    "longitudinal_tracking_segment": {"LineString"},
    "branch_point": {"Point"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"missing {label} columns: {sorted(missing)}")


def wsi_path(image_id: str) -> Path:
    subject, session = image_id.rsplit("_", 1)
    return PRECISE / "extracted/data" / subject / session / "wsi_h-e" / f"{image_id}_h-e.ome.tif"


def read_wsi_metadata(path: Path) -> tuple[int, int, float, float]:
    with tifffile.TiffFile(path) as tiff:
        page = tiff.pages[0]
        metadata = tiff.ome_metadata
        if not metadata:
            raise ValueError(f"missing OME metadata: {path}")
        root = ET.fromstring(metadata)
        pixels = next((element for element in root.iter() if element.tag.endswith("Pixels")), None)
        if pixels is None:
            raise ValueError(f"missing OME Pixels metadata: {path}")
        mpp_x = float(pixels.attrib["PhysicalSizeX"])
        mpp_y = float(pixels.attrib["PhysicalSizeY"])
        unit_x = pixels.attrib.get("PhysicalSizeXUnit", "")
        unit_y = pixels.attrib.get("PhysicalSizeYUnit", "")
        if unit_x not in {"µm", "um", "micrometer"} or unit_y not in {"µm", "um", "micrometer"}:
            raise ValueError(f"unexpected OME physical-size units: {unit_x}, {unit_y}")
        return int(page.imagewidth), int(page.imagelength), mpp_x, mpp_y


class TiledTiffSource:
    """Read level-0 RGB regions without the zarr synchronous compatibility layer."""

    def __init__(self, page: tifffile.TiffPage):
        if not page.is_tiled or len(page.shape) != 3 or page.samplesperpixel != page.shape[2]:
            raise ValueError("contour H&E source must be a tiled interleaved image")
        self.page = page
        self.shape = page.shape

    def __getitem__(self, key):
        if (not isinstance(key, tuple) or len(key) < 2 or
                not all(isinstance(value, slice) for value in key[:2])):
            raise TypeError("TiledTiffSource requires y/x slice access")
        y_slice, x_slice = key[:2]
        if y_slice.step not in (None, 1) or x_slice.step not in (None, 1):
            raise ValueError("TiledTiffSource does not support strided access")
        height, width = self.shape[:2]
        y0, y1, _ = y_slice.indices(height)
        x0, x1, _ = x_slice.indices(width)
        output = np.zeros((y1 - y0, x1 - x0, self.shape[2]), dtype=self.page.dtype)
        if y1 <= y0 or x1 <= x0:
            return output

        tile_width = int(self.page.tilewidth)
        tile_height = int(self.page.tilelength)
        tiles_across = math.ceil(width / tile_width)
        handle = self.page.parent.filehandle
        for tile_y in range(y0 // tile_height, math.ceil(y1 / tile_height)):
            for tile_x in range(x0 // tile_width, math.ceil(x1 / tile_width)):
                tile_index = tile_y * tiles_across + tile_x
                handle.seek(self.page.dataoffsets[tile_index])
                encoded = handle.read(self.page.databytecounts[tile_index])
                decoded = self.page.decode(encoded, tile_index)[0]
                if decoded is None:
                    raise ValueError(f"failed to decode TIFF tile {tile_index}")
                tile = decoded[0] if decoded.ndim == 4 else decoded
                global_x0, global_y0 = tile_x * tile_width, tile_y * tile_height
                global_x1 = min(global_x0 + tile_width, width)
                global_y1 = min(global_y0 + tile_height, height)
                intersection_x0, intersection_x1 = max(x0, global_x0), min(x1, global_x1)
                intersection_y0, intersection_y1 = max(y0, global_y0), min(y1, global_y1)
                output[
                    intersection_y0 - y0:intersection_y1 - y0,
                    intersection_x0 - x0:intersection_x1 - x0,
                ] = tile[
                    intersection_y0 - global_y0:intersection_y1 - global_y0,
                    intersection_x0 - global_x0:intersection_x1 - global_x0,
                ]
        return output


def collect_wsi_records(mapping: pd.DataFrame) -> pd.DataFrame:
    records = []
    for image_id in sorted(mapping.image_id.astype(str).unique()):
        path = wsi_path(image_id)
        if not path.exists():
            raise FileNotFoundError(path)
        width, height, mpp_x, mpp_y = read_wsi_metadata(path)
        digest = sha256_file(path)
        records.append({
            "image_id": image_id,
            "wsi_path": str(path.resolve()),
            "wsi_sha256": digest,
            "width_px": width,
            "height_px": height,
            "mpp_x": mpp_x,
            "mpp_y": mpp_y,
            "wsi_size_bytes": path.stat().st_size,
        })
        print(f"hashed H&E WSI {image_id}: {digest}", flush=True)
    return pd.DataFrame(records)


def build_case_manifest(mapping: pd.DataFrame, locked: pd.DataFrame,
                        eligibility: pd.DataFrame, wsi_records: pd.DataFrame,
                        expected_count: int = 14) -> pd.DataFrame:
    require_columns(mapping, MANIFEST_REQUIRED, "mapping")
    require_columns(locked, LOCKED_REQUIRED, "locked review")
    require_columns(eligibility, ELIGIBILITY_REQUIRED, "eligibility")
    require_columns(wsi_records, WSI_REQUIRED, "WSI")
    for frame, label in [(mapping, "mapping"), (locked, "locked review"),
                         (eligibility, "eligibility")]:
        if frame.temporary_id.duplicated().any():
            raise ValueError(f"duplicate temporary ID in {label}")
    if mapping.candidate_id.duplicated().any():
        raise ValueError("duplicate candidate ID in mapping")
    expected_ids = set(mapping.temporary_id)
    if set(locked.temporary_id) != expected_ids or set(eligibility.temporary_id) != expected_ids:
        raise ValueError("temporary ID sets do not reconcile")
    if len(mapping) != expected_count:
        raise ValueError(f"expected {expected_count} contour cases, found {len(mapping)}")
    if wsi_records.image_id.duplicated().any():
        raise ValueError("duplicate image ID in WSI records")

    locked_part = locked[LOCKED_REQUIRED]
    eligibility_part = eligibility[ELIGIBILITY_REQUIRED]
    manifest = (mapping[MANIFEST_REQUIRED]
                .merge(locked_part, on="temporary_id", validate="one_to_one")
                .merge(eligibility_part, on="temporary_id", validate="one_to_one")
                .merge(wsi_records, on="image_id", validate="many_to_one"))
    if manifest[WSI_REQUIRED[1:]].isna().any().any():
        raise ValueError("one or more contour cases lack WSI metadata")
    manifest["review_stream"] = manifest.contour_disposition.map({
        "eligible_for_contouring": "primary_contour",
        "adjudication_required": "adjudication",
        "wider_context_required": "wider_context",
        "not_evaluable": "not_evaluable",
    })
    if manifest.review_stream.isna().any():
        raise ValueError("unknown contour disposition")
    manifest["locator_center_x"] = (
        pd.to_numeric(manifest.x0) + pd.to_numeric(manifest.window_px) / 2
    )
    manifest["locator_center_y"] = (
        pd.to_numeric(manifest.y0) + pd.to_numeric(manifest.window_px) / 2
    )
    manifest["coordinate_system"] = COORDINATE_SYSTEM
    manifest["contact_qc_tolerance_um"] = CONTACT_TOLERANCE_UM
    manifest["contour_task"] = [
        ("adjudicate_then_contour" if disposition == "adjudication_required"
         else "nerve_control" if pni == "absent" else "nerve_tumor_interface")
        for disposition, pni in zip(manifest.contour_disposition, manifest.pni_status)
    ]
    return manifest.sort_values("temporary_id").reset_index(drop=True)


def locator_feature_collection(row: pd.Series) -> dict:
    """Return a public locator-only feature with no private identity or locked label."""
    return {
        "type": "FeatureCollection",
        "name": f"{row.temporary_id} locator only - not an approved contour",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row.locator_center_x), float(row.locator_center_y)],
            },
            "properties": {
                "temporary_id": str(row.temporary_id),
                "object_type": "candidate_locator",
                "locator_only": True,
                "approved_contour": False,
                "review_stream": str(row.review_stream),
                "coordinate_system": COORDINATE_SYSTEM,
                "classification": {"name": "LOCATOR_ONLY_NOT_CONTOUR", "color": [255, 165, 0]},
            },
        }],
    }


def build_status_template(manifest: pd.DataFrame) -> pd.DataFrame:
    status = pd.DataFrame({
        "temporary_id": manifest.temporary_id,
        "candidate_id": manifest.candidate_id,
        "image_id": manifest.image_id,
        "review_stream": manifest.review_stream,
        "locked_pni_status": manifest.pni_status,
        "locked_overall_relation": manifest.overall_relation,
        "m5_contour_disposition": manifest.contour_disposition,
        "index_nerve_annotation_id": "",
        "required_object_completeness": "pending",
        "contour_status": "pending",
        "approval_status": "pending",
        "adjudication_required": manifest.contour_disposition.map(
            lambda value: "yes" if value == "adjudication_required" else "no"
        ),
        "adjudication_result": "",
        "evidence_mode": "H&E_only",
        "ihc_used": "no",
        "registration_qc": "not_applicable",
        "partial_or_not_evaluable_reason": "",
        "index_nerve_uncertain": "no",
        "reviewer_id": "",
        "revision_number": "",
        "review_timestamp_utc": "",
        "reviewer_notes": "",
    })
    return status[STATUS_COLUMNS]


def embed_contour_cases(manifest: pd.DataFrame) -> list[dict]:
    """Embed three H&E contexts while retaining level-0 WSI coordinates."""
    cases = []
    for image_id, group in manifest.groupby("image_id", sort=True):
        path = wsi_path(str(image_id))
        with tifffile.TiffFile(path) as tiff:
            source = TiledTiffSource(tiff.pages[0])
            for _, row in group.iterrows():
                base = int(float(row.window_px))
                sizes = [base, 2 * base, 4 * base]
                origins = centered_crop_origins(int(float(row.x0)), int(float(row.y0)),
                                                base, sizes)
                view_specs = [("300", 1600, 95), ("600", 2000, 92), ("1200", 2200, 90)]
                views = {}
                for (label, max_px, quality), (origin, size) in zip(
                        view_specs, zip(origins, sizes)):
                    crop = crop_with_padding(source, origin[0], origin[1], size)
                    views[label] = {
                        "uri": jpeg_uri(crop, max_px=max_px, quality=quality),
                        "x0": origin[0], "y0": origin[1], "size": size,
                    }
                cases.append({
                    "temporary_id": str(row.temporary_id),
                    "review_stream": str(row.review_stream),
                    "locked_pni_status": str(row.pni_status),
                    "locked_overall_relation": str(row.overall_relation),
                    "nerve_multiplicity": str(row.nerve_multiplicity),
                    "unresolved_morphology_fields": str(row.unresolved_morphology_fields),
                    "contour_task": str(row.contour_task),
                    "wsi_width": int(row.width_px), "wsi_height": int(row.height_px),
                    "locator_center_x": float(row.locator_center_x),
                    "locator_center_y": float(row.locator_center_y),
                    "views": views,
                })
        print(f"embedded contour H&E views from {image_id}", flush=True)
    return sorted(cases, key=lambda item: item["temporary_id"])


CONTOUR_HTML_TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PRECISE PNI 전문의 Contour 검토</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f4;color:#16232b;font-family:Arial,"Noto Sans KR",sans-serif}header{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;padding:11px 18px;background:#17364d;color:#fff}header h1{font-size:18px;margin:0 auto 0 0}.pill{border-radius:99px;padding:5px 9px;background:#d9e9f2;color:#17364d;font-size:12px;font-weight:bold}main{max-width:1800px;margin:14px auto;padding:0 14px}.panel,.intro{background:#fff;border:1px solid #c6d3da;border-radius:9px;padding:13px;margin-bottom:12px}.intro summary{font-weight:bold;font-size:16px;cursor:pointer}.roadmap{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin:12px 0}.stage{padding:8px;border-radius:6px;background:#edf1f3;font-size:12px}.stage.done{background:#dff1e5}.stage.now{background:#ffebad;border:2px solid #cb8d00}.notice{padding:10px;border-left:5px solid #d19b18;background:#fff5d9;margin:10px 0}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.toolbar input,.toolbar select,button,.button,textarea{border:1px solid #8198a6;border-radius:5px;background:#fff;padding:7px 9px}button,.button{cursor:pointer}.workspace{display:grid;grid-template-columns:minmax(650px,1fr) 410px;gap:12px}.viewer-panel{background:#172229;border-radius:9px;padding:10px;color:#fff}.case-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}.case-head h2{margin:0 auto 0 0;font-size:19px}.views,.drawing-tools{display:flex;gap:6px;flex-wrap:wrap;margin:7px 0}.views button.active,.drawing-tools button.active{background:#ffcf5a}#viewer{width:100%;height:72vh;min-height:540px;background:#0b1115;touch-action:none;cursor:crosshair}#viewer.pan{cursor:grab}.side{max-height:calc(100vh - 90px);overflow:auto}.side h3{margin:4px 0 8px}.task{background:#eaf5fa;border:1px solid #b8d8e7;border-radius:6px;padding:9px;margin-bottom:9px}.guide{font-size:12px;line-height:1.45;background:#f5f7f8;padding:8px;border-radius:6px}.formgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.formgrid label{font-size:12px}.formgrid select,.formgrid input,.formgrid textarea{width:100%;margin-top:3px}.full{grid-column:1/-1}.annotation-list{width:100%;min-height:110px}.warning{white-space:pre-wrap;background:#fff5d9;border:1px solid #d9b95c;border-radius:5px;padding:8px;font-size:12px}.ok{color:#14713e}.bad{color:#9a4e00}.export{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.muted{color:#62737e;font-size:12px}@media(max-width:1050px){.workspace{grid-template-columns:1fr}.side{max-height:none}.roadmap{grid-template-columns:1fr 1fr}#viewer{height:65vh}}
</style></head><body><header><h1>PRECISE PNI 전문의 Contour 검토</h1><span id="progress" class="pill"></span></header><main>
<details class="intro" open><summary>연구 목적·전체 진행 단계·이번 검토의 역할</summary>
<h2>프로젝트의 최종 목표</h2><p>AI가 공간적으로 중복되지 않는 PNI 의심 후보를 우선 제시하고, 병리전문의가 후보를 확인·형태 분류·윤곽화한 뒤, 승인된 경계에서 신경 크기·암–신경 접촉·포위율과 공간 미세환경을 재현성 있게 정량화하는 병리의사 참여형 연구 체계를 구축하는 것입니다.</p>
<div class="roadmap"><div class="stage done">M1<br>후보 생성</div><div class="stage done">M2<br>Frozen audit</div><div class="stage done">M3–M4<br>14건 블라인드 형태 재판독</div><div class="stage done">M5<br>공식 잠금·전이 분석</div><div class="stage now">M6 현재 위치<br>전문의 contour·adjudication</div><div class="stage">M7<br>형태계측·공간 분석</div><div class="stage">M8–M10<br>확장·임상·외부검증</div></div>
<h2>이번 검토로 달성할 것</h2><p>13개 primary focus의 실제 신경 외곽과 필요한 암–신경 interface를 확정하고, probable PNI 1건은 별도 adjudication합니다. 이 결과가 있어야만 직경, 면적, 접촉 길이, 포위율을 계산할 수 있습니다.</p>
<div class="notice"><b>범위와 주의:</b> locator는 탐색 표식일 뿐 contour가 아닙니다. 불확실하거나 평가할 수 없는 경계를 억지로 연결하지 마십시오. 이 14건은 선택된 방법개발 focus이며 PRECISE 환자의 형태 분포, whole-slide 민감도, 예후 또는 외부 타당성을 뜻하지 않습니다.</div></details>
<section class="panel toolbar"><label>Reviewer ID <input id="reviewer" autocomplete="off"></label><label>Case <select id="caseSelect"></select></label><button id="prev">← 이전</button><button id="next">다음 →</button><button id="nextIncomplete">다음 미완료</button><button id="backup">JSON 백업</button><label class="button">JSON 불러오기<input hidden type="file" id="importer" accept="application/json"></label></section>
<div class="workspace"><section class="viewer-panel"><div class="case-head"><h2 id="caseTitle"></h2><span id="stream" class="pill"></span><span id="caseState"></span></div><div class="task" id="task"></div>
<div class="views"><b>H&amp;E 문맥:</b><button data-view="300">300 µm</button><button data-view="600" class="active">600 µm</button><button data-view="1200">1200 µm</button><button id="resetView">화면 맞춤</button><button id="fullscreen">전체화면</button><label><input type="checkbox" id="showLocator" checked> locator 표시</label></div>
<div class="drawing-tools"><b>도구:</b><button data-tool="pan" class="active">이동</button><button data-tool="nerve_outer_boundary">Index nerve</button><button data-tool="additional_nerve_boundary">Additional nerve</button><button data-tool="tumor_boundary">Tumor</button><button data-tool="contact_segment">Contact</button><button data-tool="encasement_arc">Encasement</button><button data-tool="intraneural_region">Intraneural</button><button data-tool="longitudinal_tracking_segment">Longitudinal</button><button data-tool="branch_point">Branch point</button></div>
<svg id="viewer" class="pan"><image id="slideImage" preserveAspectRatio="none"></image><g id="overlay"></g></svg><p class="muted">마우스 휠: 확대/축소 · 이동 도구: drag · 그리기: click로 점 추가, double-click/Enter로 완료 · Esc 취소 · Ctrl/Cmd+Z 마지막 점 취소</p></section>
<aside class="panel side"><h3>현재 잠금 정보와 작업</h3><div id="lockedInfo" class="guide"></div><h3>그리기 설정</h3><div class="formgrid"><label>Object role<select id="objectRole"><option value="index">index</option><option value="related">related</option><option value="additional">additional</option></select></label><label>Parent nerve<select id="parentId"><option value="">없음</option></select></label></div><div class="export"><button id="finish">현재 객체 완료</button><button id="undoPoint">마지막 점 취소</button><button id="cancel">그리기 취소</button></div>
<h3>작성 객체</h3><select id="annotationList" class="annotation-list" size="6"></select><div class="export"><button id="deleteAnnotation">선택 객체 삭제</button></div>
<h3>Case 상태</h3><div class="formgrid"><label>Required objects<select data-status="required_object_completeness"><option>pending</option><option>complete</option><option>incomplete</option><option>not_evaluable</option></select></label><label>Contour status<select data-status="contour_status"><option>pending</option><option>complete</option><option>partial</option><option>not_evaluable</option></select></label><label>Approval<select data-status="approval_status"><option>pending</option><option>approved</option><option>modified</option><option>rejected</option><option>not_evaluable</option></select></label><label>Evidence<select data-status="evidence_mode"><option>H&amp;E_only</option><option>H&amp;E_plus_IHC</option></select></label><label>IHC used<select data-status="ihc_used"><option>no</option><option>yes</option></select></label><label>Registration QC<select data-status="registration_qc"><option>not_applicable</option><option>pass</option><option>uncertain</option><option>fail</option></select></label><label id="adjWrap">Adjudication result<select data-status="adjudication_result"><option value=""></option><option>definite</option><option>absent</option><option>uncertain</option><option>not_evaluable</option></select></label><label>Index uncertain<select data-status="index_nerve_uncertain"><option>no</option><option>yes</option></select></label><label>Revision<input data-status="revision_number" inputmode="numeric"></label><label>Review timestamp<input data-status="review_timestamp_utc" placeholder="자동 입력"></label><label class="full">Partial/not-evaluable 사유<textarea data-status="partial_or_not_evaluable_reason"></textarea></label><label class="full">Reviewer notes<textarea data-status="reviewer_notes"></textarea></label></div>
<h3>실시간 확인</h3><div id="warnings" class="warning"></div><div class="export"><button id="currentGeoJSON">현재 case GeoJSON</button><button id="allGeoJSON">전체 GeoJSON</button><button id="statusCSV">상태 CSV</button></div>
<h3>객체 가이드</h3><div class="guide"><b>모든 대상:</b> index nerve polygon<br><b>Definite:</b> 관련 tumor polygon<br><b>Touching:</b> contact line<br><b>Surrounding:</b> contact line + encasement arc<br><b>Absent control:</b> nerve contour 유지<br><b>MORPH-003:</b> H&amp;E adjudication 우선, 필요할 때만 IHC</div></aside></div></main>
<script>
const CASES=__CASES__,NS="http://www.w3.org/2000/svg",KEY="precise-pni-contour-html-v1";
const OBJECTS={nerve_outer_boundary:{g:"Polygon",c:"#00e5ff"},additional_nerve_boundary:{g:"Polygon",c:"#36d399"},tumor_boundary:{g:"Polygon",c:"#ff4d6d"},contact_segment:{g:"LineString",c:"#ffd166"},encasement_arc:{g:"LineString",c:"#ff9f1c"},intraneural_region:{g:"Polygon",c:"#c77dff"},longitudinal_tracking_segment:{g:"LineString",c:"#7bf1a8"},branch_point:{g:"Point",c:"#ffffff"}};
let state={reviewer_id:"",cases:{}},idx=0,view="600",tool="pan",draft=[],box=null,panning=false,moved=false,last=null;
try{state=JSON.parse(localStorage.getItem(KEY))||state}catch(e){}
const q=x=>document.querySelector(x),qa=x=>[...document.querySelectorAll(x)],svg=q("#viewer"),overlay=q("#overlay"),img=q("#slideImage");
function C(){return CASES[idx]}function S(){let id=C().temporary_id;return state.cases[id]||(state.cases[id]={annotations:[],status:{required_object_completeness:"pending",contour_status:"pending",approval_status:"pending",adjudication_result:"",evidence_mode:"H&E_only",ihc_used:"no",registration_qc:"not_applicable",partial_or_not_evaluable_reason:"",index_nerve_uncertain:"no",revision_number:"",review_timestamp_utc:"",reviewer_notes:"",index_nerve_annotation_id:""}})}
function save(){state.reviewer_id=q("#reviewer").value.trim();localStorage.setItem(KEY,JSON.stringify(state));progress()}
function progress(){let done=CASES.filter(c=>{let x=state.cases[c.temporary_id];return state.reviewer_id&&x&&x.status.contour_status!=="pending"&&x.status.approval_status!=="pending"}).length;q("#progress").textContent=`상태 완료 ${done}/${CASES.length}`}
function setView(name){view=name;let v=C().views[name];box={x:v.x0,y:v.y0,w:v.size,h:v.size};img.setAttribute("href",v.uri);img.setAttribute("x",v.x0);img.setAttribute("y",v.y0);img.setAttribute("width",v.size);img.setAttribute("height",v.size);applyBox();qa("[data-view]").forEach(b=>b.classList.toggle("active",b.dataset.view===name));renderOverlay()}
function applyBox(){svg.setAttribute("viewBox",`${box.x} ${box.y} ${box.w} ${box.h}`)}
function point(evt){let p=svg.createSVGPoint();p.x=evt.clientX;p.y=evt.clientY;let z=p.matrixTransform(svg.getScreenCTM().inverse());return [Math.round(z.x*10)/10,Math.round(z.y*10)/10]}
function element(name,attrs={}){let e=document.createElementNS(NS,name);for(let[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e}
function renderOverlay(){overlay.replaceChildren();if(q("#showLocator").checked){let c=C(),s=Math.max(box.w/80,8);overlay.append(element("line",{x1:c.locator_center_x-s,y1:c.locator_center_y,x2:c.locator_center_x+s,y2:c.locator_center_y,stroke:"#ffea00","stroke-width":Math.max(box.w/500,2),"stroke-dasharray":"6 4","vector-effect":"non-scaling-stroke"}));overlay.append(element("line",{x1:c.locator_center_x,y1:c.locator_center_y-s,x2:c.locator_center_x,y2:c.locator_center_y+s,stroke:"#ffea00","stroke-width":Math.max(box.w/500,2),"stroke-dasharray":"6 4","vector-effect":"non-scaling-stroke"}))}for(let a of S().annotations)draw(a.geometry,a.object_type,false,a.annotation_id);if(draft.length&&tool!=="pan")draw({type:OBJECTS[tool].g,coordinates:OBJECTS[tool].g==="Polygon"?[draft]:draft},tool,true,"")}
function draw(g,t,isDraft,id){let cfg=OBJECTS[t],e;if(g.type==="Polygon")e=element("polygon",{points:g.coordinates[0].map(p=>p.join(",")).join(" ")});else if(g.type==="LineString")e=element("polyline",{points:g.coordinates.map(p=>p.join(",")).join(" "),fill:"none"});else e=element("circle",{cx:g.coordinates[0],cy:g.coordinates[1],r:Math.max(box.w/180,4)});e.setAttribute("stroke",cfg.c);e.setAttribute("stroke-width",isDraft?3:2);e.setAttribute("vector-effect","non-scaling-stroke");e.setAttribute("fill",g.type==="Polygon"?cfg.c+"33":g.type==="Point"?cfg.c:"none");if(isDraft)e.setAttribute("stroke-dasharray","6 4");if(id)e.dataset.id=id;overlay.append(e)}
function setTool(value){tool=value;draft=[];moved=false;qa("[data-tool]").forEach(b=>b.classList.toggle("active",b.dataset.tool===value));svg.classList.toggle("pan",value==="pan");if(value==="nerve_outer_boundary")q("#objectRole").value="index";else if(value==="additional_nerve_boundary")q("#objectRole").value="additional";else if(value!=="pan")q("#objectRole").value="related";renderOverlay()}
function finish(){if(tool==="pan"||!draft.length)return;let cfg=OBJECTS[tool],min=cfg.g==="Polygon"?3:cfg.g==="LineString"?2:1;if(draft.length<min){alert(`최소 ${min}개 점이 필요합니다.`);return}let used=S().annotations.filter(a=>a.object_type===tool).map(a=>Number(a.annotation_id.split("-").at(-1))||0),n=Math.max(0,...used)+1,id=`${C().temporary_id}-${tool}-${String(n).padStart(3,"0")}`,coords=cfg.g==="Polygon"?[[...draft,draft[0]]]:cfg.g==="Point"?draft[0]:[...draft];let role=tool==="nerve_outer_boundary"?"index":q("#objectRole").value;let a={annotation_id:id,object_type:tool,object_role:role,parent_annotation_id:q("#parentId").value,geometry:{type:cfg.g,coordinates:coords}};S().annotations.push(a);if(tool==="nerve_outer_boundary"&&!S().status.index_nerve_annotation_id)S().status.index_nerve_annotation_id=id;draft=[];save();renderCase()}
function renderList(){let list=q("#annotationList");list.replaceChildren();for(let a of S().annotations){let o=document.createElement("option");o.value=a.annotation_id;o.textContent=`${a.annotation_id} · ${a.geometry.type}`;list.append(o)}let parent=q("#parentId"),old=parent.value;parent.innerHTML='<option value="">없음</option>';for(let a of S().annotations.filter(x=>["nerve_outer_boundary","additional_nerve_boundary"].includes(x.object_type))){let o=document.createElement("option");o.value=a.annotation_id;o.textContent=a.annotation_id;parent.append(o)}parent.value=old}
function renderStatus(){for(let e of qa("[data-status]"))e.value=S().status[e.dataset.status]??"";q("#adjWrap").style.display=C().review_stream==="adjudication"?"block":"none"}
function renderCase(){let c=C();q("#caseTitle").textContent=`${c.temporary_id} (${idx+1}/${CASES.length})`;q("#caseSelect").value=c.temporary_id;q("#stream").textContent=c.review_stream;q("#task").textContent=c.contour_task==="nerve_control"?"PNI-absent nerve control: 실제 index nerve 외곽을 contour합니다. 음성이라는 이유로 제외하지 마십시오.":c.contour_task==="adjudicate_then_contour"?"Probable PNI adjudication: H&E로 먼저 재평가하고, 불명확할 때만 IHC를 별도 기록 후 참고합니다.":"Definite PNI: index nerve, 관련 tumor, contact/encasement 객체를 locked relation에 맞게 작성합니다.";q("#lockedInfo").innerHTML=`Locked PNI: <b>${c.locked_pni_status}</b><br>Locked relation: <b>${c.locked_overall_relation}</b><br>Nerve multiplicity: <b>${c.nerve_multiplicity}</b><br>보존된 미평가 항목: <b>${c.unresolved_morphology_fields||"없음"}</b>`;setView(view);renderList();renderStatus();warnings();progress();q("#caseState").textContent=S().status.contour_status}
function warnings(){let c=C(),s=S(),types=s.annotations.map(a=>a.object_type),w=[];if(!state.reviewer_id)w.push("Reviewer ID가 필요합니다.");if(s.status.contour_status==="complete"&&!types.includes("nerve_outer_boundary"))w.push("Index nerve polygon이 없습니다.");let effective=c.review_stream==="adjudication"?(s.status.adjudication_result||c.locked_pni_status):c.locked_pni_status;if(effective==="definite"&&!types.includes("tumor_boundary"))w.push("Definite PNI에는 tumor boundary가 필요합니다.");if(effective==="definite"&&["touching","surrounding_encasement"].includes(c.locked_overall_relation)&&!types.includes("contact_segment"))w.push("Locked relation에 contact segment가 필요합니다.");if(effective==="definite"&&c.locked_overall_relation==="surrounding_encasement"&&!types.includes("encasement_arc"))w.push("Surrounding relation에 encasement arc가 필요합니다.");if(c.review_stream==="adjudication"&&!s.status.adjudication_result)w.push("Adjudication result가 필요합니다.");q("#warnings").textContent=w.length?w.join("\n"):"현재 입력에서 발견된 기본 누락이 없습니다. 최종 제출은 Python validator로 확인하십시오.";q("#warnings").className="warning "+(w.length?"bad":"ok")}
function feature(a,c){let s=state.cases[c.temporary_id],st=s.status;return{type:"Feature",geometry:a.geometry,properties:{annotation_id:a.annotation_id,temporary_id:c.temporary_id,object_type:a.object_type,object_role:a.object_role,parent_annotation_id:a.parent_annotation_id||"",reviewer_id:state.reviewer_id||"",review_stage:c.review_stream, evidence_mode:st.evidence_mode,source:"pathologist_drawn",approval_status:st.approval_status,contour_completeness:st.contour_status==="complete"?"complete":st.contour_status,revision_number:st.revision_number||"",reviewer_notes:st.reviewer_notes||""}}}
function collection(c){let s=state.cases[c.temporary_id]||{annotations:[],status:{}};return{type:"FeatureCollection",name:`${c.temporary_id} specialist contours`,protocol_version:"1.0",coordinate_system:"H&E_WSI_level0_pixels_origin_top_left",features:s.annotations.map(a=>feature(a,c))}}
function esc(x){x=String(x??"");return /[",\n]/.test(x)?`"${x.replaceAll('"','""')}"`:x}function dl(name,type,text){let a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function downloadCurrent(){dl(`${C().temporary_id}_contours.geojson`,"application/geo+json",JSON.stringify(collection(C()),null,2))}function downloadAll(){dl("precise_pni_contours_combined.geojson","application/geo+json",JSON.stringify({type:"FeatureCollection",name:"PRECISE PNI specialist contours",protocol_version:"1.0",coordinate_system:"H&E_WSI_level0_pixels_origin_top_left",features:CASES.flatMap(c=>collection(c).features)},null,2))}
function statusRows(){return CASES.map(c=>{let s=(state.cases[c.temporary_id]||{status:{}}).status||{};return{temporary_id:c.temporary_id,candidate_id:"",image_id:"",review_stream:c.review_stream,locked_pni_status:c.locked_pni_status,locked_overall_relation:c.locked_overall_relation,m5_contour_disposition:c.review_stream==="adjudication"?"adjudication_required":"eligible_for_contouring",index_nerve_annotation_id:s.index_nerve_annotation_id||"",required_object_completeness:s.required_object_completeness||"pending",contour_status:s.contour_status||"pending",approval_status:s.approval_status||"pending",adjudication_required:c.review_stream==="adjudication"?"yes":"no",adjudication_result:s.adjudication_result||"",evidence_mode:s.evidence_mode||"H&E_only",ihc_used:s.ihc_used||"no",registration_qc:s.registration_qc||"not_applicable",partial_or_not_evaluable_reason:s.partial_or_not_evaluable_reason||"",index_nerve_uncertain:s.index_nerve_uncertain||"no",reviewer_id:state.reviewer_id||"",revision_number:s.revision_number||"",review_timestamp_utc:s.review_timestamp_utc||"",reviewer_notes:s.reviewer_notes||""}})}
const STATUS_HEADERS=["temporary_id","candidate_id","image_id","review_stream","locked_pni_status","locked_overall_relation","m5_contour_disposition","index_nerve_annotation_id","required_object_completeness","contour_status","approval_status","adjudication_required","adjudication_result","evidence_mode","ihc_used","registration_qc","partial_or_not_evaluable_reason","index_nerve_uncertain","reviewer_id","revision_number","review_timestamp_utc","reviewer_notes"];
function downloadStatus(){let rows=statusRows();dl("precise_pni_contour_review_status.csv","text/csv;charset=utf-8","\ufeff"+[STATUS_HEADERS.join(","),...rows.map(r=>STATUS_HEADERS.map(h=>esc(r[h])).join(","))].join("\n"))}
svg.addEventListener("click",e=>{if(tool==="pan"||moved||e.detail>1)return;let p=point(e),c=C();if(p[0]<0||p[1]<0||p[0]>c.wsi_width||p[1]>c.wsi_height){alert("WSI 범위 밖입니다.");return}draft.push(p);if(OBJECTS[tool].g==="Point")finish();else renderOverlay()});svg.addEventListener("dblclick",e=>{e.preventDefault();if(tool!=="pan")finish()});svg.addEventListener("wheel",e=>{e.preventDefault();let p=point(e),f=e.deltaY<0?.8:1.25,nw=Math.max(80,Math.min(C().views["1200"].size*1.5,box.w*f)),nh=nw;box.x=p[0]-(p[0]-box.x)*nw/box.w;box.y=p[1]-(p[1]-box.y)*nh/box.h;box.w=nw;box.h=nh;applyBox();renderOverlay()},{passive:false});svg.addEventListener("pointerdown",e=>{if(tool!=="pan")return;panning=true;moved=false;last=[e.clientX,e.clientY];svg.setPointerCapture(e.pointerId)});svg.addEventListener("pointermove",e=>{if(!panning)return;let dx=(e.clientX-last[0])*box.w/svg.clientWidth,dy=(e.clientY-last[1])*box.h/svg.clientHeight;if(Math.abs(dx)+Math.abs(dy)>1)moved=true;box.x-=dx;box.y-=dy;last=[e.clientX,e.clientY];applyBox();renderOverlay()});svg.addEventListener("pointerup",()=>panning=false);
qa("[data-view]").forEach(b=>b.onclick=()=>setView(b.dataset.view));qa("[data-tool]").forEach(b=>b.onclick=()=>setTool(b.dataset.tool));q("#resetView").onclick=()=>setView(view);q("#showLocator").onchange=renderOverlay;q("#finish").onclick=finish;q("#undoPoint").onclick=()=>{draft.pop();renderOverlay()};q("#cancel").onclick=()=>{draft=[];renderOverlay()};q("#deleteAnnotation").onclick=()=>{let id=q("#annotationList").value;if(!id)return;S().annotations=S().annotations.filter(a=>a.annotation_id!==id);if(S().status.index_nerve_annotation_id===id)S().status.index_nerve_annotation_id="";save();renderCase()};q("#fullscreen").onclick=()=>q(".viewer-panel").requestFullscreen();
q("#reviewer").value=state.reviewer_id||"";q("#reviewer").oninput=()=>{save();warnings()};for(let c of CASES){let o=document.createElement("option");o.value=c.temporary_id;o.textContent=`${c.temporary_id} · ${c.review_stream}`;q("#caseSelect").append(o)}q("#caseSelect").onchange=e=>{idx=CASES.findIndex(c=>c.temporary_id===e.target.value);renderCase()};q("#prev").onclick=()=>{idx=(idx-1+CASES.length)%CASES.length;renderCase()};q("#next").onclick=()=>{idx=(idx+1)%CASES.length;renderCase()};q("#nextIncomplete").onclick=()=>{for(let k=1;k<=CASES.length;k++){let j=(idx+k)%CASES.length,s=state.cases[CASES[j].temporary_id];if(!s||s.status.contour_status==="pending"||s.status.approval_status==="pending"){idx=j;renderCase();return}}alert("모든 case 상태가 완료되었습니다.")};
for(let e of qa("[data-status]"))e.onchange=e.oninput=()=>{S().status[e.dataset.status]=e.value;if(e.dataset.status==="contour_status"&&e.value!=="pending"&&!S().status.review_timestamp_utc)S().status.review_timestamp_utc=new Date().toISOString();save();renderStatus();warnings()};q("#currentGeoJSON").onclick=downloadCurrent;q("#allGeoJSON").onclick=downloadAll;q("#statusCSV").onclick=downloadStatus;q("#backup").onclick=()=>dl("precise_pni_contour_backup.json","application/json",JSON.stringify(state,null,2));q("#importer").onchange=e=>{let r=new FileReader();r.onload=()=>{state=JSON.parse(r.result);localStorage.setItem(KEY,JSON.stringify(state));q("#reviewer").value=state.reviewer_id||"";renderCase()};r.readAsText(e.target.files[0])};window.addEventListener("keydown",e=>{if(e.key==="Enter"&&tool!=="pan")finish();if(e.key==="Escape"){draft=[];renderOverlay()}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"&&draft.length){e.preventDefault();draft.pop();renderOverlay()}});renderCase();
</script></body></html>'''


def build_contour_html(cases: list[dict]) -> str:
    return CONTOUR_HTML_TEMPLATE.replace(
        "__CASES__", json.dumps(cases, ensure_ascii=False, separators=(",", ":"))
    )


def _issue(temporary_id: str, code: str, detail: str, severity: str = "error") -> dict:
    return {"temporary_id": temporary_id, "severity": severity,
            "issue_code": code, "detail": detail}


def _segments_intersect(a, b, c, d) -> bool:
    def orientation(p, q, r):
        value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if abs(value) < 1e-12:
            return 0
        return 1 if value > 0 else 2

    def on_segment(p, q, r):
        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    o1, o2 = orientation(a, b, c), orientation(a, b, d)
    o3, o4 = orientation(c, d, a), orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and on_segment(a, c, b)) or (o2 == 0 and on_segment(a, d, b)) or
            (o3 == 0 and on_segment(c, a, d)) or (o4 == 0 and on_segment(c, b, d)))


def _ring_self_intersects(ring: list) -> bool:
    segments = list(zip(ring[:-1], ring[1:]))
    for first, (a, b) in enumerate(segments):
        for second in range(first + 1, len(segments)):
            if abs(first - second) <= 1 or {first, second} == {0, len(segments) - 1}:
                continue
            c, d = segments[second]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _point_segment_distance(point, start, end) -> float:
    px, py = point[:2]
    x1, y1 = start[:2]
    x2, y2 = end[:2]
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    fraction = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    nearest_x, nearest_y = x1 + fraction * dx, y1 + fraction * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def _line_follows_polygon_boundary(line: list, polygon: dict, mpp_x: float,
                                   mpp_y: float, tolerance_um: float) -> bool:
    rings = polygon.get("coordinates", []) if polygon.get("type") == "Polygon" else []
    segments = [
        ([start[0] * mpp_x, start[1] * mpp_y], [end[0] * mpp_x, end[1] * mpp_y])
        for ring in rings for start, end in zip(ring[:-1], ring[1:])
    ]
    if not segments:
        return False
    sampled_points = []
    for start, end in zip(line[:-1], line[1:]):
        start_um = [start[0] * mpp_x, start[1] * mpp_y]
        end_um = [end[0] * mpp_x, end[1] * mpp_y]
        length_um = math.hypot(end_um[0] - start_um[0], end_um[1] - start_um[1])
        sample_count = max(1, math.ceil(length_um / tolerance_um))
        sampled_points.extend([
            [
                start_um[0] + (end_um[0] - start_um[0]) * index / sample_count,
                start_um[1] + (end_um[1] - start_um[1]) * index / sample_count,
            ]
            for index in range(sample_count)
        ])
    sampled_points.append([line[-1][0] * mpp_x, line[-1][1] * mpp_y])
    return all(
        min(_point_segment_distance(point, start, end) for start, end in segments)
        <= tolerance_um
        for point in sampled_points
    )


def _all_points(geometry: dict) -> list[list[float]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point":
        return [coordinates]
    if geometry_type == "LineString":
        return coordinates
    if geometry_type == "Polygon":
        return [point for ring in coordinates for point in ring]
    if geometry_type == "MultiPolygon":
        return [point for polygon in coordinates for ring in polygon for point in ring]
    return []


def _geometry_issues(temporary_id: str, geometry: dict, width: int, height: int) -> list[dict]:
    issues = []
    geometry_type = geometry.get("type") if isinstance(geometry, dict) else None
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not geometry_type or coordinates in (None, []):
        return [_issue(temporary_id, "empty_geometry", "Geometry is missing or empty")]
    points = _all_points(geometry)
    if not points:
        return [_issue(temporary_id, "unsupported_geometry", f"Unsupported geometry {geometry_type}")]
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            issues.append(_issue(temporary_id, "invalid_coordinate", "Coordinate must contain x and y"))
            continue
        x, y = point[:2]
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or not math.isfinite(x) or not math.isfinite(y):
            issues.append(_issue(temporary_id, "invalid_coordinate", "Coordinate must be finite numeric x/y"))
        elif x < 0 or y < 0 or x >= width or y >= height:
            issues.append(_issue(temporary_id, "coordinate_out_of_bounds",
                                 f"Coordinate ({x}, {y}) outside {width}x{height}"))
    if geometry_type == "LineString" and len({tuple(point[:2]) for point in points}) < 2:
        issues.append(_issue(temporary_id, "invalid_linestring", "LineString needs two unique points"))
    polygons = ([coordinates] if geometry_type == "Polygon" else coordinates
                if geometry_type == "MultiPolygon" else [])
    for polygon in polygons:
        for ring in polygon:
            if len(ring) < 4 or ring[0][:2] != ring[-1][:2] or len({tuple(x[:2]) for x in ring[:-1]}) < 3:
                issues.append(_issue(temporary_id, "invalid_polygon_ring",
                                     "Polygon ring must be closed with three unique vertices"))
            elif _ring_self_intersects(ring):
                issues.append(_issue(temporary_id, "self_intersection", "Polygon ring self-intersects"))
    return issues


def validate_case_annotations(collection: dict, manifest_row: pd.Series,
                              status_row: pd.Series) -> list[dict]:
    temporary_id = str(manifest_row.temporary_id)
    issues: list[dict] = []
    if collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        return [_issue(temporary_id, "invalid_feature_collection", "Expected GeoJSON FeatureCollection")]
    features = [item for item in collection["features"]
                if not item.get("properties", {}).get("locator_only", False)]
    annotation_ids = []
    types = []
    props_by_id = {}
    geometry_by_id = {}
    for item in features:
        properties = item.get("properties", {})
        missing = [name for name in FEATURE_REQUIRED_PROPERTIES if name not in properties]
        if missing:
            issues.append(_issue(temporary_id, "missing_feature_properties",
                                 f"Missing properties: {'|'.join(missing)}"))
        for name in [x for x in FEATURE_REQUIRED_PROPERTIES
                     if x not in {"parent_annotation_id", "reviewer_notes"}]:
            if properties.get(name, "") in ("", None):
                issues.append(_issue(temporary_id, "blank_feature_property", f"Blank property: {name}"))
        if str(properties.get("temporary_id", "")) != temporary_id:
            issues.append(_issue(temporary_id, "feature_case_mismatch", "Feature temporary_id mismatch"))
        annotation_id = str(properties.get("annotation_id", ""))
        annotation_ids.append(annotation_id)
        props_by_id[annotation_id] = properties
        geometry_by_id[annotation_id] = item.get("geometry", {})
        object_type = properties.get("object_type")
        types.append(object_type)
        geometry = item.get("geometry", {})
        geometry_type = geometry.get("type") if isinstance(geometry, dict) else None
        if object_type not in OBJECT_GEOMETRIES:
            issues.append(_issue(temporary_id, "unknown_object_type", f"Unknown object type {object_type}"))
        elif geometry_type not in OBJECT_GEOMETRIES[object_type]:
            issues.append(_issue(temporary_id, "geometry_type_mismatch",
                                 f"{object_type} cannot use {geometry_type}"))
        issues.extend(_geometry_issues(temporary_id, geometry, int(manifest_row.width_px),
                                       int(manifest_row.height_px)))
    duplicates = sorted({value for value in annotation_ids if annotation_ids.count(value) > 1})
    if duplicates:
        issues.append(_issue(temporary_id, "duplicate_annotation_id", "|".join(duplicates)))
    id_set = set(annotation_ids)
    for annotation_id, properties in props_by_id.items():
        parent = properties.get("parent_annotation_id")
        if properties.get("object_type") in {"contact_segment", "encasement_arc"} and not parent:
            issues.append(_issue(temporary_id, "missing_interface_parent",
                                 f"{annotation_id} must reference a nerve boundary"))
        if parent and parent not in id_set:
            issues.append(_issue(temporary_id, "unknown_parent_annotation",
                                 f"{annotation_id} references {parent}"))
        if properties.get("object_type") in {"contact_segment", "encasement_arc"} and parent in id_set:
            parent_properties = props_by_id[parent]
            if parent_properties.get("object_type") not in {
                    "nerve_outer_boundary", "additional_nerve_boundary"}:
                issues.append(_issue(temporary_id, "contact_parent_not_nerve",
                                     f"{annotation_id} parent is not a nerve boundary"))
            else:
                line = geometry_by_id[annotation_id].get("coordinates", [])
                if not _line_follows_polygon_boundary(
                        line, geometry_by_id[parent], float(manifest_row.mpp_x),
                        float(manifest_row.mpp_y), CONTACT_TOLERANCE_UM):
                    issues.append(_issue(temporary_id, "contact_not_on_nerve_boundary",
                                         f"{annotation_id} exceeds {CONTACT_TOLERANCE_UM} um tolerance"))
    if any(value in {"contact_segment", "encasement_arc"} for value in types) and "tumor_boundary" not in types:
        issues.append(_issue(temporary_id, "interface_without_tumor_boundary",
                             "Contact/encasement annotation requires a tumor boundary"))

    approved = str(status_row.get("approval_status", "")) in {"approved", "modified"}
    complete = str(status_row.get("contour_status", "")) == "complete"
    if approved and complete:
        for field in ["index_nerve_annotation_id", "reviewer_id", "revision_number",
                      "review_timestamp_utc"]:
            if str(status_row.get(field, "")).strip() == "":
                issues.append(_issue(temporary_id, "missing_status_value", f"Missing {field}"))
        index_id = str(status_row.get("index_nerve_annotation_id", ""))
        index_properties = props_by_id.get(index_id, {})
        if (index_properties.get("object_type") != "nerve_outer_boundary" or
                index_properties.get("object_role") != "index"):
            issues.append(_issue(temporary_id, "invalid_index_nerve",
                                 "Index nerve must reference an index nerve_outer_boundary"))
        effective_pni = str(manifest_row.pni_status)
        adjudication_result = str(status_row.get("adjudication_result", "")).strip()
        if str(manifest_row.review_stream) == "adjudication" and adjudication_result:
            effective_pni = adjudication_result
        required = {"nerve_outer_boundary"}
        if effective_pni == "definite":
            required.add("tumor_boundary")
            if str(manifest_row.overall_relation) in {"touching", "surrounding_encasement"}:
                required.add("contact_segment")
            if str(manifest_row.overall_relation) == "surrounding_encasement":
                required.add("encasement_arc")
        for object_type in sorted(required):
            if object_type not in types:
                issues.append(_issue(temporary_id, f"missing_{object_type}",
                                     f"Approved complete case requires {object_type}"))
    return issues


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def write_json(value: dict, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_locked_outputs(config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not config.get("locked") or config.get("case_count") != 14:
        raise ValueError("morphology run configuration is not the official 14-case lock")
    for name, expected in config.get("outputs", {}).items():
        path = config_path.parent / name
        if not path.exists() or sha256_file(path) != expected:
            raise ValueError(f"locked morphology output hash mismatch: {name}")
    return config


def annotation_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PRECISE PNI contour GeoJSON feature collection",
        "type": "object",
        "required": ["type", "features"],
        "properties": {
            "type": {"const": "FeatureCollection"},
            "features": {"type": "array"},
        },
        "protocol_version": PROTOCOL_VERSION,
        "coordinate_system": "H&E WSI level-0 pixels; top-left origin",
        "allowed_object_types": sorted(OBJECT_GEOMETRIES),
        "required_feature_properties": FEATURE_REQUIRED_PROPERTIES,
    }


def review_readme() -> str:
    return """# PRECISE PNI 전문의 contour package

이 package는 protocol v1.0에 따라 선택된 14개 focus의 실제 신경 및 암–신경 interface contour를 수집합니다. `primary/`의 13건과 `adjudication/`의 MORPH-003을 섞지 마십시오.

가장 간편한 검토 방법은 `precise_pni_contour_review.html`을 최신 브라우저에서 여는 것입니다. 연구 목적과 현재 단계, 세 가지 H&E 문맥, contour 도구, 자동저장 및 GeoJSON/CSV export가 한 파일에 포함되어 있습니다. 정식 제출 전에는 가능하면 QuPath one-case round-trip으로 level-0 좌표를 확인하십시오.

## 중요 원칙

- 각 locator Point는 탐색용이며 승인 신경 contour가 아닙니다.
- score, rank, stratum 또는 모델 출력은 사용하지 않습니다.
- 원본 H&E WSI level-0 pixel 좌표로 그립니다.
- uncertain/not-evaluable을 no로 바꾸지 않습니다.
- locked morphology CSV를 수정하지 않습니다.
- absent nerve control도 신경 contour 대상입니다.

## 작업 순서

1. HTML을 사용하는 경우 reviewer ID를 입력하고 각 case에서 300/600/1200 µm H&E를 전환해 contour합니다.
2. QuPath을 사용하는 경우 `private_contour_case_manifest.csv`에서 temporary ID에 대응하는 H&E WSI를 열고 locator GeoJSON을 불러옵니다.
3. locator는 탐색용이므로 승인 annotation export에서 제외합니다.
4. protocol의 객체 이름과 feature properties로 contour를 작성합니다.
5. case별 또는 전체 GeoJSON, 상태 CSV 및 JSON 백업을 저장합니다.
6. MORPH-003은 H&E adjudication을 먼저 수행하고, 필요한 경우에만 IHC 사용과 registration QC를 기록합니다.
7. 제출 전 validate 명령으로 오류를 확인합니다. Validator는 오류를 자동 수정하지 않습니다.

```bash
.venv/bin/python -m projects.precise_pni_candidate_triage.code.contour_review.build_precise_pni_contour_review validate \
  --annotation-dir precise_pni_contours_combined.geojson \
  --status precise_pni_contour_review_status.csv
```

QuPath 실제 버전과 level-0 GeoJSON round-trip은 첫 WSI dry run에서 기록해야 합니다. 승인 contour 전에는 직경, 포위율, 접촉 길이 또는 공간 gradient를 확정 계산하지 않습니다.
"""


def build_package(mapping_path: Path, locked_review_path: Path, eligibility_path: Path,
                  lock_config_path: Path, protocol_path: Path, immutable_review_path: Path,
                  output_dir: Path) -> dict:
    protocol_text = protocol_path.read_text(encoding="utf-8")
    if "상태: **승인됨" not in protocol_text or "Contour Protocol v1.0" not in protocol_text:
        raise ValueError("contour protocol is not approved v1.0")
    lock_config = verify_locked_outputs(lock_config_path)
    immutable_before = sha256_file(immutable_review_path)
    if immutable_before != EXPECTED_IMMUTABLE_REVIEW_SHA256:
        raise ValueError("immutable 120-candidate clinician source SHA256 mismatch")
    mapping = pd.read_csv(mapping_path, dtype="string", keep_default_na=False)
    locked = pd.read_csv(locked_review_path, dtype="string", keep_default_na=False)
    eligibility = pd.read_csv(eligibility_path, dtype="string", keep_default_na=False)
    mapping_hash = sha256_file(mapping_path)
    locked_mapping_hash = lock_config["inputs"]["private_mapping"]["sha256"]
    if mapping_hash != locked_mapping_hash:
        raise ValueError("private mapping differs from morphology lock provenance")
    wsi_records = collect_wsi_records(mapping)
    manifest = build_case_manifest(mapping, locked, eligibility, wsi_records)

    checks = [
        ("protocol_approved", True, PROTOCOL_VERSION, PROTOCOL_VERSION, ""),
        ("case_count", len(manifest) == 14, len(manifest), 14, ""),
        ("unique_temporary_ids", manifest.temporary_id.is_unique,
         manifest.temporary_id.nunique(), 14, ""),
        ("unique_candidate_ids", manifest.candidate_id.is_unique,
         manifest.candidate_id.nunique(), 14, ""),
        ("primary_case_count", int(manifest.review_stream.eq("primary_contour").sum()) == 13,
         int(manifest.review_stream.eq("primary_contour").sum()), 13, ""),
        ("adjudication_case_count", int(manifest.review_stream.eq("adjudication").sum()) == 1,
         int(manifest.review_stream.eq("adjudication").sum()), 1, ""),
        ("wsi_count", manifest.image_id.nunique() == 10, manifest.image_id.nunique(), 10, ""),
        ("mpp_x_consistent", wsi_records.mpp_x.nunique() == 1,
         wsi_records.mpp_x.nunique(), 1, ""),
        ("mpp_y_consistent", wsi_records.mpp_y.nunique() == 1,
         wsi_records.mpp_y.nunique(), 1, ""),
    ]
    qc = pd.DataFrame(checks, columns=["check", "passed", "observed", "expected", "detail"])
    if not qc.passed.all():
        raise RuntimeError("contour package pre-write QC failed")

    public_cases = embed_contour_cases(manifest)
    html = build_contour_html(public_cases)
    leaked_private_values = sorted({
        value for column in ["candidate_id", "subject_id", "image_id"]
        for value in manifest[column].astype(str).unique() if value and value in html
    })
    if leaked_private_values:
        raise RuntimeError(f"private identity leaked into contour HTML: {leaked_private_values}")
    qc = pd.concat([qc, pd.DataFrame([
        ("html_case_count", len(public_cases) == 14, len(public_cases), 14, ""),
        ("html_private_identity_leaks", not leaked_private_values,
         len(leaked_private_values), 0, ""),
    ], columns=qc.columns)], ignore_index=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    primary_dir = output_dir / "primary"
    adjudication_dir = output_dir / "adjudication"
    primary_dir.mkdir(exist_ok=True)
    adjudication_dir.mkdir(exist_ok=True)
    manifest_path = output_dir / "private_contour_case_manifest.csv"
    status_path = output_dir / "contour_review_status_template.csv"
    template_path = output_dir / "contour_review_template.geojson"
    schema_path = output_dir / "contour_annotation_schema.json"
    readme_path = output_dir / "CONTOUR_REVIEW_README_KO.md"
    qc_path = output_dir / "contour_qc_report.csv"
    html_path = output_dir / "precise_pni_contour_review.html"
    write_csv(manifest, manifest_path)
    write_csv(build_status_template(manifest), status_path)
    write_json({
        "type": "FeatureCollection", "features": [],
        "name": "PRECISE PNI empty contour export template",
        "protocol_version": PROTOCOL_VERSION,
        "coordinate_system": COORDINATE_SYSTEM,
    }, template_path)
    write_json(annotation_schema(), schema_path)
    readme_path.write_text(review_readme(), encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    locator_paths = []
    for _, row in manifest.iterrows():
        target = primary_dir if row.review_stream == "primary_contour" else adjudication_dir
        path = target / f"{row.temporary_id}_locator.geojson"
        write_json(locator_feature_collection(row), path)
        locator_paths.append(path)
    write_csv(qc, qc_path)

    immutable_after = sha256_file(immutable_review_path)
    if immutable_after != immutable_before:
        raise RuntimeError("immutable clinician source changed during contour package build")
    output_paths = [manifest_path, status_path, template_path, schema_path, readme_path, qc_path,
                    html_path,
                    *locator_paths]
    input_paths = {
        "entrypoint_script": Path(__file__),
        "private_mapping": mapping_path,
        "locked_morphology_review": locked_review_path,
        "locked_contour_eligibility": eligibility_path,
        "morphology_lock_config": lock_config_path,
        "approved_contour_protocol": protocol_path,
        "immutable_120_candidate_review": immutable_review_path,
    }
    config = {
        "study": "PRECISE PNI specialist contour pilot",
        "stage": "M6_contour_package_build",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_status": "approved",
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": "not_applicable",
        "case_count": len(manifest),
        "primary_case_count": int(manifest.review_stream.eq("primary_contour").sum()),
        "adjudication_case_count": int(manifest.review_stream.eq("adjudication").sum()),
        "wsi_count": int(manifest.image_id.nunique()),
        "coordinate_system": COORDINATE_SYSTEM,
        "contact_qc_tolerance_um": CONTACT_TOLERANCE_UM,
        "qupath_roundtrip_status": "pending_external_dry_run",
        "immutable_source_sha256_before": immutable_before,
        "immutable_source_sha256_after": immutable_after,
        "inputs": {name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
                   for name, path in input_paths.items()},
        "wsi_inputs": {
            row.image_id: {
                "path": row.wsi_path, "sha256": row.wsi_sha256,
                "size_bytes": int(row.wsi_size_bytes), "width_px": int(row.width_px),
                "height_px": int(row.height_px), "mpp_x": float(row.mpp_x),
                "mpp_y": float(row.mpp_y),
            }
            for _, row in wsi_records.iterrows()
        },
        "software": {"python": platform.python_version(), "platform": platform.platform(),
                     "pandas": pd.__version__, "pillow": PIL.__version__,
                     "tifffile": tifffile.__version__, "numpy": np.__version__,
                     "qupath": "not_available_in_build_environment"},
        "command": ".venv/bin/python -m projects.precise_pni_candidate_triage.code.contour_review.build_precise_pni_contour_review build",
        "outputs": {str(path.relative_to(output_dir)): sha256_file(path)
                    for path in sorted(output_paths)},
    }
    write_json(config, output_dir / "contour_run_config.json")
    return config


def validate_submission(annotation_dir: Path, status_path: Path,
                        manifest_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path, dtype="string", keep_default_na=False)
    status = pd.read_csv(status_path, dtype="string", keep_default_na=False)
    require_columns(status, STATUS_COLUMNS, "status")
    if status.temporary_id.duplicated().any():
        raise ValueError("duplicate temporary ID in contour status")
    if set(status.temporary_id) != set(manifest.temporary_id):
        raise ValueError("status and manifest temporary ID sets differ")
    combined = None
    if annotation_dir.is_file():
        combined = json.loads(annotation_dir.read_text(encoding="utf-8"))
    elif (annotation_dir / "precise_pni_contours_combined.geojson").exists():
        combined = json.loads(
            (annotation_dir / "precise_pni_contours_combined.geojson").read_text(encoding="utf-8")
        )
    if combined is not None and (combined.get("type") != "FeatureCollection" or
                                 not isinstance(combined.get("features"), list)):
        raise ValueError("combined annotation export is not a GeoJSON FeatureCollection")
    all_issues = []
    for _, row in manifest.iterrows():
        if combined is not None:
            collection = {
                "type": "FeatureCollection",
                "features": [feature for feature in combined["features"]
                             if str(feature.get("properties", {}).get("temporary_id", "")) ==
                             str(row.temporary_id)],
            }
        else:
            candidates = sorted(annotation_dir.rglob(f"{row.temporary_id}*.geojson"))
            candidates = [path for path in candidates if "locator" not in path.name]
            if len(candidates) != 1:
                all_issues.append(_issue(str(row.temporary_id), "annotation_file_count",
                                         f"Expected one submitted GeoJSON, found {len(candidates)}"))
                continue
            collection = json.loads(candidates[0].read_text(encoding="utf-8"))
        status_row = status.loc[status.temporary_id.eq(row.temporary_id)].iloc[0]
        all_issues.extend(validate_case_annotations(collection, row, status_row))
    return pd.DataFrame(all_issues, columns=["temporary_id", "severity", "issue_code", "detail"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    build.add_argument("--locked-review", type=Path, default=DEFAULT_LOCKED_REVIEW)
    build.add_argument("--eligibility", type=Path, default=DEFAULT_ELIGIBILITY)
    build.add_argument("--lock-config", type=Path, default=DEFAULT_LOCK_CONFIG)
    build.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    build.add_argument("--immutable-review", type=Path, default=DEFAULT_IMMUTABLE_REVIEW)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    validate = sub.add_parser("validate")
    validate.add_argument("--annotation-dir", type=Path, required=True)
    validate.add_argument("--status", type=Path, required=True)
    validate.add_argument("--manifest", type=Path,
                          default=DEFAULT_OUTPUT / "private_contour_case_manifest.csv")
    validate.add_argument("--output", type=Path,
                          default=DEFAULT_OUTPUT / "completed_contour_qc_report.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "build":
        config = build_package(
            args.mapping, args.locked_review, args.eligibility, args.lock_config,
            args.protocol, args.immutable_review, args.output_dir,
        )
        print(json.dumps({key: config[key] for key in
                          ["case_count", "primary_case_count", "adjudication_case_count",
                           "wsi_count"]}))
    else:
        issues = validate_submission(args.annotation_dir, args.status, args.manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_csv(issues, args.output)
        print(json.dumps({"issue_count": len(issues)}))


if __name__ == "__main__":
    main()
