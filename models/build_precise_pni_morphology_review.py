"""Build and finalize the blinded PRECISE 14-focus PNI morphology rereview.

The build stage contains no new pathology conclusions. It creates a standalone
H&E reviewer whose public records contain temporary IDs only. The private
mapping and prior labels remain separate until a completed review is finalized.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import zarr
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRECISE = ROOT / "opendataset/PRECISE"
DEFAULT_REVIEW = PRECISE / "precise_pni_review (1).csv"
DEFAULT_AUDIT = PRECISE / "pni_frozen_score_audit/candidate_audit_table.csv"
DEFAULT_OUTPUT = PRECISE / "pni_morphology_rereview"
DEFAULT_SEED = 20260806

RESPONSE_COLUMNS = [
    "temporary_id", "reviewer_id", "nerve_present", "pni_status",
    "overall_relation", "touching_component", "surrounding_component",
    "intraneural_component", "section_orientation", "longitudinal_tracking",
    "branch_point_involvement", "nerve_multiplicity", "field_adequacy",
    "overall_confidence", "reviewer_notes",
]

ALLOWED = {
    "nerve_present": {"yes", "no", "uncertain", "not_evaluable"},
    "pni_status": {"definite", "probable", "absent", "uncertain", "not_evaluable"},
    "overall_relation": {"none", "adjacent", "touching", "surrounding_encasement",
                         "intraneural", "mixed", "uncertain", "not_evaluable"},
    "touching_component": {"yes", "no", "uncertain", "not_evaluable"},
    "surrounding_component": {"yes", "no", "uncertain", "not_evaluable"},
    "intraneural_component": {"yes", "no", "uncertain", "not_evaluable"},
    "section_orientation": {"transverse", "oblique", "longitudinal", "mixed",
                            "uncertain", "not_evaluable"},
    "longitudinal_tracking": {"yes", "no", "uncertain", "not_evaluable"},
    "branch_point_involvement": {"yes", "no", "uncertain", "not_evaluable"},
    "nerve_multiplicity": {"single", "multiple", "uncertain", "not_evaluable"},
    "field_adequacy": {"adequate", "wider_context_needed", "not_evaluable"},
    "overall_confidence": {"high", "medium", "low"},
}

GEOMETRY = ["candidate_id", "review_order", "image_id", "x0", "y0", "window_px", "window_um"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def derive_fixed_set(review: pd.DataFrame, audit: pd.DataFrame,
                     expected_count: int = 14) -> pd.DataFrame:
    """Select prior nerve-positive rows and strictly reconcile their geometry."""
    missing_review = set(GEOMETRY + ["nerve_present", "pni_present",
                                    "tumor_nerve_relation"]) - set(review.columns)
    missing_audit = set(GEOMETRY + ["subject_id"]) - set(audit.columns)
    if missing_review or missing_audit:
        raise ValueError(f"missing columns: review={sorted(missing_review)}, audit={sorted(missing_audit)}")
    if review.candidate_id.duplicated().any() or audit.candidate_id.duplicated().any():
        raise ValueError("duplicate candidate ID in source")
    selected = review.loc[review.nerve_present.astype("string").str.strip().str.lower() == "yes"].copy()
    if len(selected) != expected_count:
        raise ValueError(f"expected {expected_count} nerve-positive cases, found {len(selected)}")
    merged = selected.merge(audit, on="candidate_id", how="left", suffixes=("_review", "_audit"),
                            validate="one_to_one")
    if merged.subject_id.isna().any():
        raise ValueError("candidate missing from audit table")
    for column in GEOMETRY[1:]:
        left, right = merged[f"{column}_review"], merged[f"{column}_audit"]
        if column in {"x0", "y0", "window_px", "review_order"}:
            equal = pd.to_numeric(left, errors="coerce").eq(pd.to_numeric(right, errors="coerce"))
        elif column == "window_um":
            equal = np.isclose(pd.to_numeric(left), pd.to_numeric(right), rtol=0, atol=1e-8)
        else:
            equal = left.astype(str).eq(right.astype(str))
        if not bool(np.all(equal)):
            raise ValueError(f"geometry mismatch for {column}")
    result = pd.DataFrame({"candidate_id": merged.candidate_id})
    for column in GEOMETRY[1:]:
        result[column] = merged[f"{column}_review"]
    result["subject_id"] = merged.subject_id
    pni_column = "pni_present_review" if "pni_present_review" in merged else "pni_present"
    relation_column = ("tumor_nerve_relation_review" if "tumor_nerve_relation_review" in merged
                       else "tumor_nerve_relation")
    result["previous_pni_status"] = merged[pni_column].map(
        {"yes": "definite", "no": "absent", "uncertain": "uncertain"}
    ).fillna(merged[pni_column])
    result["previous_relation"] = merged[relation_column]
    return result.sort_values("review_order").reset_index(drop=True)


def assign_blinded_ids(fixed: pd.DataFrame, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(fixed))
    blinded = fixed.iloc[order].reset_index(drop=True).copy()
    blinded.insert(0, "temporary_id", [f"MORPH-{i:03d}" for i in range(1, len(blinded) + 1)])
    blinded.insert(1, "morphology_review_order", np.arange(1, len(blinded) + 1))
    return blinded


def centered_crop_origins(x0: int, y0: int, base_size: int,
                          sizes: list[int]) -> list[tuple[int, int]]:
    center_x, center_y = x0 + base_size // 2, y0 + base_size // 2
    return [(center_x - size // 2, center_y - size // 2) for size in sizes]


def crop_with_padding(source, x0: int, y0: int, size: int) -> Image.Image:
    height, width = source.shape[:2]
    x1, y1 = x0 + size, y0 + size
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
    canvas = Image.new("RGB", (size, size), "white")
    if sx1 > sx0 and sy1 > sy0:
        pixels = np.asarray(source[sy0:sy1, sx0:sx1])
        canvas.paste(Image.fromarray(pixels).convert("RGB"), (sx0 - x0, sy0 - y0))
    return canvas


def jpeg_uri(image: Image.Image, max_px: int = 900, quality: int = 90) -> str:
    resized = image.copy()
    resized.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    resized.save(buffer, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def wsi_path(image_id: str) -> Path:
    subject, session = image_id.rsplit("_", 1)
    return PRECISE / "extracted/data" / subject / session / "wsi_h-e" / f"{image_id}_h-e.ome.tif"


def embed_case_images(blinded: pd.DataFrame) -> list[dict]:
    cases: list[dict] = []
    for image_id, group in blinded.groupby("image_id", sort=True):
        path = wsi_path(str(image_id))
        if not path.exists():
            raise FileNotFoundError(path)
        with tifffile.TiffFile(path) as tiff:
            source = zarr.open(tiff.pages[0].aszarr(), mode="r")
            for _, row in group.iterrows():
                base = int(row.window_px)
                sizes = [base, 2 * base, 4 * base]
                origins = centered_crop_origins(int(row.x0), int(row.y0), base, sizes)
                uris = [jpeg_uri(crop_with_padding(source, x, y, size), max_px=900,
                                 quality=90 if index == 0 else 87)
                        for index, ((x, y), size) in enumerate(zip(origins, sizes))]
                cases.append({
                    "temporary_id": row.temporary_id,
                    "review_order": int(row.morphology_review_order),
                    "field_300_uri": uris[0], "field_600_uri": uris[1],
                    "field_1200_uri": uris[2],
                })
        print(f"embedded {len(group)} morphology fields from one H&E slide", flush=True)
    return sorted(cases, key=lambda item: item["review_order"])


HTML_TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PRECISE PNI 형태 재판독</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f6f7;color:#18252d;font-family:Arial,"Noto Sans KR",sans-serif}header{position:sticky;top:0;z-index:4;display:flex;gap:14px;align-items:center;background:#17364d;color:#fff;padding:12px 18px}header h1{font-size:18px;margin:0 auto 0 0}main{max-width:1500px;margin:16px auto;padding:0 14px}.card,.tools,.notice{background:#fff;border:1px solid #c8d4dc;border-radius:8px;padding:12px;margin-bottom:12px}.notice{background:#fff5d9}.tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}button,.button,input[type=text]{border:1px solid #8299a8;border-radius:5px;background:#fff;padding:8px 11px}.button,button{cursor:pointer}.images{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.image{background:#152129;padding:7px;text-align:center;border-radius:5px}.image h3{color:#fff;font-size:13px}.image img{max-width:100%;max-height:60vh;cursor:zoom-in}.grid{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:9px;margin-top:12px}fieldset{border:1px solid #ccd7de;border-radius:5px}legend{font-weight:bold}label.option{display:inline-flex;gap:4px;margin:5px 10px 5px 0}textarea{width:100%;min-height:70px}.nav{display:flex;justify-content:space-between;margin-top:12px}.ok{color:#087553}.bad{color:#934d00}.modal{display:none;position:fixed;inset:0;z-index:10;background:#000e;padding:15px}.modal.show{display:flex;align-items:center;justify-content:center}.modal img{max-width:98vw;max-height:96vh}@media(max-width:900px){.images,.grid{grid-template-columns:1fr}}</style></head><body>
<header><h1>PRECISE PNI 형태 재판독</h1><b id="progress"></b></header><main>
<div class="notice">14개의 선택된 신경 후보를 H&amp;E 형태만으로 독립 판정합니다. 빈 값을 음성으로 해석하지 마십시오. 기존 판정·모델 정보·면역염색은 표시되지 않습니다.</div>
<div class="tools"><label>Reviewer ID <input type="text" id="reviewer"></label><button onclick="jump()">다음 미완료</button><button onclick="downloadCSV()">CSV 다운로드</button><button onclick="downloadJSON()">JSON 백업</button><label class="button">JSON 불러오기<input hidden type="file" id="importer" accept="application/json"></label></div>
<section class="card"><h2><span id="case"></span> <small id="position"></small> <span id="status"></span></h2><div class="images">
<div class="image"><h3>300 µm 평가 영역</h3><img id="im300"></div><div class="image"><h3>600 µm 문맥</h3><img id="im600"></div><div class="image"><h3>1200 µm 문맥</h3><img id="im1200"></div></div>
<div class="grid" id="form"></div><fieldset><legend>관찰 메모 (선택)</legend><textarea id="notes"></textarea></fieldset><div class="nav"><button onclick="move(-1)">← 이전</button><button onclick="move(1)">다음 →</button></div></section></main><div id="modal" class="modal"><img id="zoom"></div>
<script>const cases=__CASES__;const choices={nerve_present:["yes","no","uncertain","not_evaluable"],pni_status:["definite","probable","absent","uncertain","not_evaluable"],overall_relation:["none","adjacent","touching","surrounding_encasement","intraneural","mixed","uncertain","not_evaluable"],touching_component:["yes","no","uncertain","not_evaluable"],surrounding_component:["yes","no","uncertain","not_evaluable"],intraneural_component:["yes","no","uncertain","not_evaluable"],section_orientation:["transverse","oblique","longitudinal","mixed","uncertain","not_evaluable"],longitudinal_tracking:["yes","no","uncertain","not_evaluable"],branch_point_involvement:["yes","no","uncertain","not_evaluable"],nerve_multiplicity:["single","multiple","uncertain","not_evaluable"],field_adequacy:["adequate","wider_context_needed","not_evaluable"],overall_confidence:["high","medium","low"]};const labels={nerve_present:"신경 존재",pni_status:"PNI 상태",overall_relation:"대표 암–신경 관계",touching_component:"접촉 요소",surrounding_component:"포위 요소",intraneural_component:"신경내 요소",section_orientation:"신경 절단 방향",longitudinal_tracking:"종축 추적",branch_point_involvement:"분지점 침범",nerve_multiplicity:"신경 수",field_adequacy:"시야 적절성",overall_confidence:"종합 확신도"};const headers=["temporary_id","reviewer_id",...Object.keys(choices),"reviewer_notes"];let state={reviewer_id:"",responses:{}},idx=0;try{state=JSON.parse(localStorage.getItem("precise-morphology-v1"))||state}catch(e){}function current(){let id=cases[idx].temporary_id;return state.responses[id]||(state.responses[id]={})}function complete(x){return Object.keys(choices).every(k=>x[k])}function save(){state.reviewer_id=document.getElementById("reviewer").value;localStorage.setItem("precise-morphology-v1",JSON.stringify(state));progress()}function makeForm(){let root=document.getElementById("form");for(let field of Object.keys(choices)){let box=document.createElement("fieldset"),legend=document.createElement("legend");legend.textContent=labels[field];box.appendChild(legend);for(let value of choices[field]){let label=document.createElement("label");label.className="option";label.innerHTML=`<input type="radio" name="${field}" value="${value}">${value}`;label.firstChild.onchange=e=>{current()[field]=e.target.value;save();renderStatus()};box.appendChild(label)}root.appendChild(box)}}function render(){let c=cases[idx],x=current();document.getElementById("case").textContent=c.temporary_id;document.getElementById("position").textContent=`${idx+1}/${cases.length}`;document.getElementById("im300").src=c.field_300_uri;document.getElementById("im600").src=c.field_600_uri;document.getElementById("im1200").src=c.field_1200_uri;for(let field of Object.keys(choices))document.querySelectorAll(`input[name=${field}]`).forEach(e=>e.checked===false&&(e.checked=x[field]===e.value));document.getElementById("notes").value=x.reviewer_notes||"";renderStatus();progress()}function renderStatus(){let e=document.getElementById("status");e.textContent=complete(current())?"완료":"미완료";e.className=complete(current())?"ok":"bad"}function progress(){let n=cases.filter(c=>complete(state.responses[c.temporary_id]||{})).length;document.getElementById("progress").textContent=`완료 ${n}/${cases.length}`}function move(d){idx=Math.max(0,Math.min(cases.length-1,idx+d));render();scrollTo(0,0)}function jump(){for(let k=1;k<=cases.length;k++){let j=(idx+k)%cases.length;if(!complete(state.responses[cases[j].temporary_id]||{})){idx=j;render();return}}alert("모든 항목이 완료되었습니다.")}function rows(){return cases.map(c=>{let x=state.responses[c.temporary_id]||{},r={temporary_id:c.temporary_id,reviewer_id:state.reviewer_id};for(let k of Object.keys(choices))r[k]=x[k]||"";r.reviewer_notes=x.reviewer_notes||"";return r})}function esc(x){x=String(x??"");return /[",\n]/.test(x)?`"${x.replaceAll('"','""')}"`:x}function dl(name,type,text){let a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click()}function downloadCSV(){dl("precise_pni_morphology_completed.csv","text/csv;charset=utf-8","\ufeff"+[headers.join(","),...rows().map(r=>headers.map(h=>esc(r[h])).join(","))].join("\n"))}function downloadJSON(){dl("precise_pni_morphology_backup.json","application/json",JSON.stringify(state,null,2))}document.getElementById("notes").oninput=e=>{current().reviewer_notes=e.target.value;save()};document.getElementById("reviewer").value=state.reviewer_id||"";document.getElementById("reviewer").oninput=save;document.getElementById("importer").onchange=e=>{let reader=new FileReader();reader.onload=()=>{state=JSON.parse(reader.result);localStorage.setItem("precise-morphology-v1",JSON.stringify(state));document.getElementById("reviewer").value=state.reviewer_id||"";render()};reader.readAsText(e.target.files[0])};for(let id of ["im300","im600","im1200"]){document.getElementById(id).onclick=e=>{document.getElementById("zoom").src=e.target.src;document.getElementById("modal").classList.add("show")}}document.getElementById("modal").onclick=e=>e.currentTarget.classList.remove("show");makeForm();render();</script></body></html>'''


def build_html(cases: list[dict]) -> str:
    template = HTML_TEMPLATE.replace(
        "e.checked===false&&(e.checked=x[field]===e.value)",
        "e.checked=(x[field]===e.value)",
    )
    return template.replace("__CASES__", json.dumps(cases, separators=(",", ":")))


def blank_template(blinded: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame({"temporary_id": blinded.temporary_id})
    for column in RESPONSE_COLUMNS[1:]:
        frame[column] = ""
    return frame[RESPONSE_COLUMNS]


def validate_completed_review(frame: pd.DataFrame, expected_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing_columns = set(RESPONSE_COLUMNS) - set(frame.columns)
    if missing_columns:
        raise ValueError(f"missing response columns: {sorted(missing_columns)}")
    normalized = frame[RESPONSE_COLUMNS].copy()
    for column in RESPONSE_COLUMNS:
        normalized[column] = normalized[column].astype("string").str.strip().replace("", pd.NA)
    if normalized.temporary_id.duplicated().any():
        raise ValueError("duplicate temporary ID")
    if set(normalized.temporary_id.dropna()) != set(expected_ids):
        raise ValueError("completed review ID set does not match private mapping")
    for column, allowed in ALLOWED.items():
        invalid = normalized[column].dropna()[~normalized[column].dropna().isin(allowed)]
        if not invalid.empty:
            raise ValueError(f"invalid {column} value(s): {sorted(invalid.unique())}")
    issues: list[dict] = []
    for _, row in normalized.iterrows():
        for column in ["reviewer_id", *ALLOWED.keys()]:
            if pd.isna(row[column]):
                issues.append({"temporary_id": row.temporary_id, "severity": "missing",
                               "issue_code": "missing_value",
                               "detail": f"Missing {column}; not interpreted as no"})
    def flag(mask, code, detail):
        for temporary_id in normalized.loc[mask.fillna(False), "temporary_id"]:
            issues.append({"temporary_id": temporary_id, "severity": "conflict",
                           "issue_code": code, "detail": detail})
    positive = normalized.pni_status.isin(["definite", "probable"])
    flag(normalized.nerve_present.eq("no") & positive, "nerve_no_with_positive_pni",
         "PNI definite/probable requires an evaluable nerve")
    flag(positive & normalized.overall_relation.isin(["none", "uncertain", "not_evaluable"]),
         "positive_pni_without_evaluable_relation",
         "PNI definite/probable requires an evaluable cancer–nerve relationship")
    invasion_yes = normalized[["touching_component", "surrounding_component",
                               "intraneural_component"]].eq("yes").any(axis=1)
    flag(normalized.pni_status.eq("absent") & invasion_yes, "pni_absent_with_positive_component",
         "PNI absent conflicts with a positive invasion component")
    flag(normalized.field_adequacy.eq("not_evaluable") & normalized.overall_confidence.eq("high"),
         "not_evaluable_with_high_confidence", "Not-evaluable field conflicts with high confidence")
    issue_frame = pd.DataFrame(issues, columns=["temporary_id", "severity", "issue_code", "detail"])
    return normalized, issue_frame


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, lineterminator="\n")


def build_package(review_path: Path, audit_path: Path, output_dir: Path,
                  seed: int = DEFAULT_SEED) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    before = sha256_file(review_path)
    review = pd.read_csv(review_path, dtype={"candidate_id": "string"}, encoding="utf-8-sig")
    audit = pd.read_csv(audit_path, dtype={"candidate_id": "string"})
    fixed = derive_fixed_set(review, audit)
    blinded = assign_blinded_ids(fixed, seed)
    missing_wsi = [str(wsi_path(x)) for x in blinded.image_id.unique() if not wsi_path(x).exists()]
    if missing_wsi:
        raise FileNotFoundError("missing WSI inputs: " + ", ".join(missing_wsi))
    cases = embed_case_images(blinded)
    html_path = output_dir / "precise_pni_morphology_review.html"
    html_path.write_text(build_html(cases), encoding="utf-8")
    private_columns = ["temporary_id", "morphology_review_order", "candidate_id", "review_order",
                       "subject_id", "image_id", "x0", "y0", "window_px", "window_um",
                       "previous_pni_status", "previous_relation"]
    mapping_path = output_dir / "private_case_mapping.csv"
    write_csv(blinded[private_columns], mapping_path)
    template_path = output_dir / "morphology_review_template.csv"
    write_csv(blank_template(blinded), template_path)
    checks = [
        ("fixed_case_count", len(blinded) == 14, len(blinded), 14),
        ("unique_temporary_ids", blinded.temporary_id.is_unique, blinded.temporary_id.nunique(), 14),
        ("unique_candidate_ids", blinded.candidate_id.is_unique, blinded.candidate_id.nunique(), 14),
        ("slide_count", blinded.image_id.nunique() == 10, blinded.image_id.nunique(), 10),
        ("subject_count", blinded.subject_id.nunique() == 10, blinded.subject_id.nunique(), 10),
        ("all_wsi_present", not missing_wsi, len(missing_wsi), 0),
        ("source_review_unchanged", sha256_file(review_path) == before, sha256_file(review_path), before),
    ]
    integrity = pd.DataFrame(checks, columns=["check", "passed", "observed", "expected"])
    integrity_path = output_dir / "build_integrity_report.csv"
    write_csv(integrity, integrity_path)
    readme_path = output_dir / "README.md"
    readme_path.write_text(
        "# PRECISE PNI morphology rereview package\n\n"
        "Open `precise_pni_morphology_review.html` locally in a modern browser. "
        "Complete all structured fields and enter the reviewer ID, then download the CSV. "
        "Do not distribute `private_case_mapping.csv` to the blinded reviewer. "
        "After review lock, run this script with the `finalize` subcommand.\n",
        encoding="utf-8",
    )
    output_paths = [html_path, mapping_path, template_path, integrity_path, readme_path]
    config = {
        "study": "PRECISE PNI blinded morphology rereview",
        "stage": "build",
        "seed": seed,
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(blinded), "slide_count": int(blinded.image_id.nunique()),
        "subject_count": int(blinded.subject_id.nunique()),
        "image_fields_um": [300, 600, 1200],
        "inputs": {str(review_path.resolve()): before, str(audit_path.resolve()): sha256_file(audit_path)},
        "software": {"python": platform.python_version(), "platform": platform.platform(),
                     "pandas": pd.__version__, "numpy": np.__version__,
                     "pillow": Image.__version__, "tifffile": tifffile.__version__,
                     "zarr": zarr.__version__},
        "outputs": {path.name: sha256_file(path) for path in output_paths},
    }
    (output_dir / "run_config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n",
                                                 encoding="utf-8")
    if not integrity.passed.all():
        raise RuntimeError("build integrity checks failed")
    return config


def finalize_package(completed_path: Path, mapping_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    completed = pd.read_csv(completed_path, dtype="string", encoding="utf-8-sig", keep_default_na=False)
    mapping = pd.read_csv(mapping_path, dtype={"temporary_id": "string"})
    normalized, issues = validate_completed_review(completed, mapping.temporary_id.tolist())
    joined = mapping.merge(normalized, on="temporary_id", validate="one_to_one")
    normalized_path = output_dir / "normalized_morphology_review.csv"
    integrity_path = output_dir / "morphology_data_integrity_report.csv"
    write_csv(joined, normalized_path)
    write_csv(issues, integrity_path)
    transition = pd.crosstab(joined.previous_pni_status, joined.pni_status, dropna=False).reset_index()
    transition_path = output_dir / "morphology_transition_table.csv"
    write_csv(transition, transition_path)
    issue_ids = set(issues.temporary_id)
    eligible = joined[["temporary_id", "candidate_id", "pni_status", "field_adequacy"]].copy()
    eligible["has_logical_conflict"] = eligible.temporary_id.isin(issue_ids)
    eligible["contour_disposition"] = np.where(
        eligible.has_logical_conflict, "adjudication_required",
        np.where(eligible.field_adequacy.eq("wider_context_needed"), "wider_context_required",
                 np.where(eligible.field_adequacy.eq("adequate") &
                          eligible.pni_status.isin(["definite", "probable", "absent"]),
                          "eligible_for_contouring", "not_evaluable")))
    eligibility_path = output_dir / "contour_eligibility_table.csv"
    write_csv(eligible, eligibility_path)
    evaluable = joined.pni_status.isin(["definite", "probable", "absent"])
    missing_count = int(issues.severity.eq("missing").sum())
    conflict_count = int(issues.severity.eq("conflict").sum())
    report_path = output_dir / "MORPHOLOGY_RESULTS_REPORT.md"
    report = (
        "# PRECISE PNI Morphology Rereview Results\n\n"
        "This report describes 14 selected, previously nerve-positive candidate foci only. "
        "It does not estimate PRECISE prevalence, whole-slide sensitivity, prognosis, or external validity.\n\n"
        f"- Structured reviews received: {len(joined)}\n"
        f"- Evaluable PNI status: {int(evaluable.sum())}/14\n"
        f"- Missing required values: {missing_count}\n"
        f"- Logical conflicts requiring resolution: {conflict_count}\n"
        f"- Definite PNI: {int(joined.pni_status.eq('definite').sum())}\n"
        f"- Probable PNI: {int(joined.pni_status.eq('probable').sum())}\n"
        f"- Absent PNI: {int(joined.pni_status.eq('absent').sum())}\n"
    )
    report_path.write_text(report, encoding="utf-8")
    output_paths = [normalized_path, integrity_path, transition_path, eligibility_path, report_path]
    config = {
        "study": "PRECISE PNI blinded morphology rereview",
        "stage": "finalize",
        "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(joined),
        "missing_value_count": missing_count,
        "logical_conflict_count": conflict_count,
        "inputs": {str(completed_path.resolve()): sha256_file(completed_path),
                   str(mapping_path.resolve()): sha256_file(mapping_path)},
        "software": {"python": platform.python_version(), "platform": platform.platform(),
                     "pandas": pd.__version__, "numpy": np.__version__},
        "outputs": {path.name: sha256_file(path) for path in output_paths},
    }
    (output_dir / "run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    build.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    final = sub.add_parser("finalize")
    final.add_argument("--completed-review", type=Path, required=True)
    final.add_argument("--mapping", type=Path, default=DEFAULT_OUTPUT / "private_case_mapping.csv")
    final.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "build":
        config = build_package(args.review, args.audit, args.output_dir, args.seed)
        print(json.dumps({key: config[key] for key in ["case_count", "slide_count", "subject_count"]}))
    else:
        finalize_package(args.completed_review, args.mapping, args.output_dir)


if __name__ == "__main__":
    main()
