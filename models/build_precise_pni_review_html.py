"""Build a blinded, standalone HTML review set from PRECISE PNI candidate scores.

Selection is patient/slide-balanced and spatially de-duplicated:
  * 60 high-ranked candidates
  * 30 middle-ranked candidates
  * 30 low-ranked/random candidates

The stratum and model scores are written to a separate manifest but never displayed in the
HTML. The HTML embeds its images, works from file:// without a server, saves progress in
localStorage, and exports reviewer labels as CSV or JSON.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import zarr
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PRECISE_DATA = ROOT / "opendataset/PRECISE/extracted/data"
DEFAULT_SCORES = ROOT / "opendataset/PRECISE/pni_candidate_full/all_candidate_scores.csv"
DEFAULT_HTML = ROOT / "opendataset/PRECISE/pni_review_120.html"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    p.add_argument("--output-html", type=Path, default=DEFAULT_HTML)
    p.add_argument("--n-high", type=int, default=60)
    p.add_argument("--n-mid", type=int, default=30)
    p.add_argument("--n-low", type=int, default=30)
    p.add_argument("--seed", type=int, default=20260803)
    p.add_argument("--crop-px", type=int, default=896)
    p.add_argument("--context-px", type=int, default=768)
    return p.parse_args()


def main_tiff_path(image_id: str) -> Path:
    sub, ses = image_id.rsplit("_", 1)
    return PRECISE_DATA / sub / ses / "wsi_h-e" / f"{image_id}_h-e.ome.tif"


def spatial_nms(scores: pd.DataFrame, distance_fraction: float = 0.75) -> pd.DataFrame:
    """Retain the highest model-scored window in each overlapping spatial neighborhood."""
    kept_parts = []
    for _, group in scores.groupby("image_id", sort=True):
        centers: list[tuple[float, float]] = []
        indices = []
        for idx, row in group.sort_values("combined_score", ascending=False).iterrows():
            cx = float(row.x0 + row.window_px / 2)
            cy = float(row.y0 + row.window_px / 2)
            minimum = distance_fraction * float(row.window_px)
            if any((cx - kx) ** 2 + (cy - ky) ** 2 < minimum ** 2
                   for kx, ky in centers):
                continue
            centers.append((cx, cy))
            indices.append(idx)
        kept_parts.append(scores.loc[indices])
    out = pd.concat(kept_parts, ignore_index=True)
    out["within_slide_pct"] = out.groupby("image_id")["combined_score"].rank(pct=True)
    return out


def balanced_pick(pool: pd.DataFrame, count: int, rng: np.random.Generator,
                  mode: str) -> pd.DataFrame:
    """Round-robin slides so a large biopsy does not dominate a review stratum."""
    queues: dict[str, list[int]] = {}
    for image_id, group in pool.groupby("image_id", sort=True):
        if mode == "high":
            group = group.sort_values("combined_score", ascending=False)
        else:
            group = group.iloc[rng.permutation(len(group))]
        queues[image_id] = group.index.tolist()
    slide_ids = sorted(queues)
    picked = []
    while len(picked) < count:
        progress = False
        for image_id in rng.permutation(slide_ids):
            if queues[image_id]:
                picked.append(queues[image_id].pop(0))
                progress = True
                if len(picked) == count:
                    break
        if not progress:
            raise RuntimeError(f"Only {len(picked)} candidates available for {mode}, need {count}")
    return pool.loc[picked].copy()


def select_review_set(scores: pd.DataFrame, n_high: int, n_mid: int, n_low: int,
                      seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    unique = spatial_nms(scores)
    high_pool = unique[unique["within_slide_pct"] >= 0.70]
    mid_pool = unique[(unique["within_slide_pct"] >= 0.35)
                      & (unique["within_slide_pct"] <= 0.65)]
    low_pool = unique[unique["within_slide_pct"] <= 0.30]
    high = balanced_pick(high_pool, n_high, rng, "high").assign(selection_stratum="high")
    mid = balanced_pick(mid_pool, n_mid, rng, "mid").assign(selection_stratum="mid")
    low = balanced_pick(low_pool, n_low, rng, "low").assign(selection_stratum="low_random")
    selected = pd.concat([high, mid, low], ignore_index=True)
    selected = selected.iloc[rng.permutation(len(selected))].reset_index(drop=True)
    selected["review_order"] = np.arange(1, len(selected) + 1)
    selected["candidate_id"] = [f"PRECISE-PNI-{i:03d}" for i in selected.review_order]
    return selected


def crop_with_padding(z, x0: int, y0: int, size: int) -> Image.Image:
    h, w = z.shape[:2]
    x1, y1 = x0 + size, y0 + size
    sx0, sy0, sx1, sy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    arr = np.asarray(z[sy0:sy1, sx0:sx1])
    image = Image.new("RGB", (size, size), "white")
    image.paste(Image.fromarray(arr), (sx0 - x0, sy0 - y0))
    return image


def jpeg_data_uri(image: Image.Image, max_size: int, quality: int = 90) -> str:
    image = image.copy()
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def embed_images(selected: pd.DataFrame, crop_px: int, context_px: int) -> list[dict]:
    records = []
    for image_id, group in selected.groupby("image_id", sort=True):
        path = main_tiff_path(image_id)
        if not path.exists():
            raise FileNotFoundError(path)
        with tifffile.TiffFile(path) as tiff:
            z = zarr.open(tiff.pages[0].aszarr(), mode="r")
            for _, row in group.iterrows():
                x0, y0, size = int(row.x0), int(row.y0), int(row.window_px)
                crop = crop_with_padding(z, x0, y0, size)
                context_size = size * 2
                context_x0 = x0 - size // 2
                context_y0 = y0 - size // 2
                context = crop_with_padding(z, context_x0, context_y0, context_size)
                draw = ImageDraw.Draw(context)
                half = size // 2
                draw.rectangle((half, half, half + size, half + size),
                               outline=(220, 35, 35), width=max(4, size // 160))
                records.append({
                    "candidate_id": row.candidate_id,
                    "review_order": int(row.review_order),
                    "image_id": image_id,
                    "x0": x0,
                    "y0": y0,
                    "window_px": size,
                    "window_um": round(float(row.window_um), 2),
                    "crop_uri": jpeg_data_uri(crop, crop_px),
                    "context_uri": jpeg_data_uri(context, context_px, quality=87),
                })
        print(f"embedded {len(group):3d} candidates from {image_id}", flush=True)
    return sorted(records, key=lambda x: x["review_order"])


HTML_TEMPLATE = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRECISE PNI blinded pathology review</title>
<style>
:root{--navy:#15324b;--blue:#2d6a9f;--pale:#eef4f8;--line:#c8d5de;--warn:#8a4b08}
*{box-sizing:border-box} body{margin:0;font-family:Arial,"Noto Sans KR",sans-serif;color:#17242d;background:#f5f7f8}
header{position:sticky;top:0;z-index:5;background:var(--navy);color:white;padding:12px 18px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0;margin-right:auto}.progress{font-weight:bold}.bar{width:180px;height:10px;background:#547084;border-radius:6px;overflow:hidden}.bar>div{height:100%;background:#64c5a5;width:0}
main{max-width:1500px;margin:18px auto;padding:0 16px}.notice{background:#fff5dc;border:1px solid #edcf86;padding:10px 14px;border-radius:7px;color:#543b09;margin-bottom:12px}
.toolbar,.review{background:white;border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:12px}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button,.button{border:1px solid #7892a3;background:white;padding:8px 12px;border-radius:6px;cursor:pointer}button.primary{background:var(--blue);color:white;border-color:var(--blue)}button:hover{filter:brightness(.96)}
input[type=text]{padding:8px;border:1px solid #9db0bc;border-radius:5px}.meta{font-size:14px;color:#425966;margin-bottom:8px;display:flex;gap:18px;flex-wrap:wrap}
.images{display:grid;grid-template-columns:1fr 1fr;gap:12px}.imagebox{background:#152027;padding:8px;border-radius:6px;text-align:center}.imagebox h3{color:white;font-size:14px;margin:2px 0 7px}.imagebox img{display:block;max-width:100%;max-height:68vh;margin:auto;cursor:zoom-in}
.formgrid{display:grid;grid-template-columns:repeat(2,minmax(280px,1fr));gap:12px;margin-top:14px}fieldset{border:1px solid var(--line);border-radius:6px;padding:10px}legend{font-weight:bold;color:var(--navy)}label.option{display:inline-flex;align-items:center;gap:4px;margin:5px 12px 5px 0}textarea{width:100%;min-height:70px;border:1px solid #9db0bc;border-radius:5px;padding:8px}
.footer-nav{display:flex;justify-content:space-between;margin-top:14px}.status{font-size:13px;color:#526873}.complete{color:#087553;font-weight:bold}.incomplete{color:var(--warn);font-weight:bold}
details{margin:8px 0}kbd{background:#edf1f4;border:1px solid #bbc6cd;border-radius:3px;padding:1px 4px}
.modal{display:none;position:fixed;z-index:20;inset:0;background:rgba(0,0,0,.92);padding:20px}.modal img{display:block;max-width:98vw;max-height:96vh;margin:auto}.modal.show{display:flex;align-items:center;justify-content:center}
@media(max-width:850px){.images,.formgrid{grid-template-columns:1fr}.imagebox img{max-height:none}}
</style>
</head>
<body>
<header><h1>PRECISE PNI blinded pathology review</h1><span class="progress" id="progressText"></span><div class="bar"><div id="progressBar"></div></div></header>
<main>
<div class="notice"><b>주의:</b> 이 120개는 모델이 선별한 후보이며 PNI 정답이 아닙니다. 모델 점수와 high/mid/low 추출 층은 블라인드되어 있습니다. 가능하면 이미지만으로 독립 판정해 주세요.</div>
<details class="toolbar"><summary><b>간단 판정 가이드</b></summary><p>먼저 신경 구조의 존재를 판정하고, 종양과 신경의 관계를 별도로 기록합니다. 단순 인접은 PNI 확정과 구분합니다. 좁은 crop으로 판단할 수 없으면 <b>불확실</b>을 선택하십시오. 붉은 사각형은 넓은 문맥 영상에서 평가 crop의 위치만 나타냅니다.</p></details>
<div class="toolbar">
  <label>Reviewer ID <input id="reviewerId" type="text" placeholder="예: pathologist-01"></label>
  <button onclick="jumpUnreviewed()">다음 미완료</button>
  <button onclick="downloadCSV()">결과 CSV 다운로드</button>
  <button onclick="downloadJSON()">백업 JSON 다운로드</button>
  <label class="button">JSON 불러오기<input id="importFile" type="file" accept="application/json" hidden></label>
  <span class="status">입력은 이 브라우저의 localStorage에 자동 저장됩니다.</span>
</div>
<section class="review">
  <div class="meta"><b id="candidateId"></b><span id="position"></span><span id="slideId"></span><span id="coords"></span><span id="completionState"></span></div>
  <div class="images"><div class="imagebox"><h3>평가 crop (300 µm)</h3><img id="cropImage" alt="candidate crop"></div><div class="imagebox"><h3>넓은 문맥 (붉은 상자 = 평가 crop)</h3><img id="contextImage" alt="context crop"></div></div>
  <div class="formgrid">
    <fieldset><legend>1. 신경이 보입니까?</legend><div id="nerve_present"></div></fieldset>
    <fieldset><legend>2. PNI가 있습니까?</legend><div id="pni_present"></div></fieldset>
    <fieldset><legend>3. 종양–신경 관계</legend><div id="tumor_nerve_relation"></div></fieldset>
    <fieldset><legend>4. 판정 확신도</legend><div id="confidence"></div></fieldset>
  </div>
  <fieldset><legend>메모 (선택)</legend><textarea id="notes" placeholder="감별진단, 더 넓은 영역 필요 여부 등"></textarea></fieldset>
  <div class="footer-nav"><button onclick="move(-1)">← 이전</button><span class="status">단축키: <kbd>←</kbd>/<kbd>→</kbd> 후보 이동</span><button class="primary" onclick="move(1)">다음 →</button></div>
</section>
</main>
<div class="modal" id="modal"><img id="modalImage"></div>
<script>
const candidates=__CANDIDATES_JSON__;
const options={
 nerve_present:[["yes","있음"],["no","없음"],["uncertain","불확실"]],
 pni_present:[["yes","있음"],["no","없음"],["uncertain","불확실"]],
 tumor_nerve_relation:[["none","관계 없음"],["adjacent","인접"],["touching","접촉"],["surrounding","둘러쌈"],["intraneural","신경초/신경 내"],["uncertain","불확실"]],
 confidence:[["high","높음"],["medium","중간"],["low","낮음"]]
};
const storageKey="precise-pni-review-120-v1";let state={labels:{},reviewer_id:""},index=0;
try{const saved=JSON.parse(localStorage.getItem(storageKey));if(saved)state=saved}catch(e){}
function entry(){const id=candidates[index].candidate_id;if(!state.labels[id])state.labels[id]={};return state.labels[id]}
function isComplete(x){return !!(x.nerve_present&&x.pni_present&&x.tumor_nerve_relation&&x.confidence)}
function save(){state.reviewer_id=document.getElementById("reviewerId").value;state.updated_at=new Date().toISOString();localStorage.setItem(storageKey,JSON.stringify(state));updateProgress()}
function makeOptions(field){const div=document.getElementById(field);div.innerHTML="";for(const [value,text] of options[field]){const label=document.createElement("label");label.className="option";label.innerHTML=`<input type="radio" name="${field}" value="${value}"> ${text}`;label.querySelector("input").onchange=e=>{entry()[field]=e.target.value;save();renderStatus()};div.appendChild(label)}}
for(const field of Object.keys(options))makeOptions(field);
function render(){const c=candidates[index],x=entry();document.getElementById("candidateId").textContent=c.candidate_id;document.getElementById("position").textContent=`${index+1} / ${candidates.length}`;document.getElementById("slideId").textContent=`Slide: ${c.image_id}`;document.getElementById("coords").textContent=`x=${c.x0}, y=${c.y0}, ${c.window_um} µm`;document.getElementById("cropImage").src=c.crop_uri;document.getElementById("contextImage").src=c.context_uri;for(const field of Object.keys(options)){document.querySelectorAll(`input[name=${field}]`).forEach(el=>el.checked=(x[field]===el.value))}document.getElementById("notes").value=x.notes||"";renderStatus();updateProgress()}
function renderStatus(){const el=document.getElementById("completionState");if(isComplete(entry())){el.textContent="완료";el.className="complete"}else{el.textContent="미완료";el.className="incomplete"}}
function updateProgress(){const n=candidates.filter(c=>isComplete(state.labels[c.candidate_id]||{})).length;document.getElementById("progressText").textContent=`완료 ${n}/${candidates.length}`;document.getElementById("progressBar").style.width=`${100*n/candidates.length}%`}
function move(delta){index=Math.max(0,Math.min(candidates.length-1,index+delta));render();window.scrollTo({top:0,behavior:"smooth"})}
function jumpUnreviewed(){const start=index;for(let k=1;k<=candidates.length;k++){const j=(start+k)%candidates.length;if(!isComplete(state.labels[candidates[j].candidate_id]||{})){index=j;render();return}}alert("모든 후보가 완료되었습니다.")}
document.getElementById("notes").oninput=e=>{entry().notes=e.target.value;save()};document.getElementById("reviewerId").value=state.reviewer_id||"";document.getElementById("reviewerId").oninput=save;
document.onkeydown=e=>{if(e.target.tagName==="TEXTAREA"||e.target.tagName==="INPUT")return;if(e.key==="ArrowLeft")move(-1);if(e.key==="ArrowRight")move(1)};
function exportRows(){return candidates.map(c=>({candidate_id:c.candidate_id,review_order:c.review_order,image_id:c.image_id,x0:c.x0,y0:c.y0,window_px:c.window_px,window_um:c.window_um,reviewer_id:state.reviewer_id||"",...(state.labels[c.candidate_id]||{})}))}
function download(name,type,text){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function csvEscape(x){x=x==null?"":String(x);return /[",\n]/.test(x)?`"${x.replaceAll('"','""')}"`:x}
function downloadCSV(){const rows=exportRows(),headers=["candidate_id","review_order","image_id","x0","y0","window_px","window_um","reviewer_id","nerve_present","pni_present","tumor_nerve_relation","confidence","notes"];download("precise_pni_review.csv","text/csv;charset=utf-8","\ufeff"+[headers.join(","),...rows.map(r=>headers.map(h=>csvEscape(r[h])).join(","))].join("\n"))}
function downloadJSON(){download("precise_pni_review_backup.json","application/json",JSON.stringify({...state,exported_at:new Date().toISOString()},null,2))}
document.getElementById("importFile").onchange=e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{try{const incoming=JSON.parse(r.result);if(!incoming.labels)throw Error("labels 없음");state=incoming;localStorage.setItem(storageKey,JSON.stringify(state));document.getElementById("reviewerId").value=state.reviewer_id||"";render();alert("불러왔습니다.")}catch(err){alert("올바른 백업 JSON이 아닙니다: "+err.message)}};r.readAsText(f)};
for(const id of ["cropImage","contextImage"]){document.getElementById(id).onclick=e=>{document.getElementById("modalImage").src=e.target.src;document.getElementById("modal").classList.add("show")}}
document.getElementById("modal").onclick=()=>document.getElementById("modal").classList.remove("show");render();
</script>
</body></html>'''


def main() -> None:
    args = parse_args()
    scores = pd.read_csv(args.scores)
    required = {"image_id", "x0", "y0", "window_px", "window_um", "combined_score"}
    missing = required - set(scores.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    selected = select_review_set(scores, args.n_high, args.n_mid, args.n_low, args.seed)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_html.with_name(args.output_html.stem + "_selection_manifest.csv")
    selected.to_csv(manifest_path, index=False)
    embedded = embed_images(selected, args.crop_px, args.context_px)
    html = HTML_TEMPLATE.replace(
        "__CANDIDATES_JSON__", json.dumps(embedded, ensure_ascii=False, separators=(",", ":"))
    )
    args.output_html.write_text(html, encoding="utf-8")
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_scores": str(args.scores),
        "html": str(args.output_html),
        "selection_manifest": str(manifest_path),
        "seed": args.seed,
        "n_total": len(selected),
        "strata": selected.selection_stratum.value_counts().to_dict(),
        "slides": selected.image_id.nunique(),
        "per_slide": selected.image_id.value_counts().sort_index().to_dict(),
        "blinding": "model scores and selection stratum are absent from reviewer HTML",
    }
    summary_path = args.output_html.with_name(args.output_html.stem + "_build_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
