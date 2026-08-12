"""Extend pilot_clip_patch_outlier.py from 1034538 only to all 4 GNUH slides.

For each slide independently: embed ALL detected candidates with CLIP (image-only, no
text), compute each candidate's outlier score relative to THAT SLIDE's own mean embedding
(never pooled across slides -- axis C says there is no cross-slide absolute reference).
Then check whether suspect (lowest dab_ring) vs benign_ref (highest dab_ring) vs middle
differ in outlier score, per slide and pooled.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_patch_outlier_all4.py
"""
import json
import os
import numpy as np
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

SLIDES = ["1034532", "1034536", "1034538", "1034554"]
MODEL_ID = "openai/clip-vit-large-patch14-336"
N_EXTREME = 3  # matches the original v2 pipeline's TOP_N convention


def embed_slide(model, processor, device, slide):
    crops_dir = f"/tmp/clip_patch_all_{slide}"
    with open(f"{crops_dir}/meta.json") as f:
        meta = json.load(f)
    embeddings = []
    for m in meta:
        path = f"{crops_dir}/cand_{m['idx']:03d}.png"
        image = Image.open(path).convert("RGB")
        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt").to(device)
            feat = model.get_image_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        embeddings.append(feat.squeeze(0).cpu().numpy())
    embeddings = np.stack(embeddings)
    mean_emb = embeddings.mean(axis=0)
    mean_emb = mean_emb / np.linalg.norm(mean_emb)
    outlier_scores = 1.0 - embeddings @ mean_emb
    for m, score in zip(meta, outlier_scores):
        m["outlier_score"] = float(score)
        m["slide"] = slide
    return meta


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)

    all_meta = []
    for slide in SLIDES:
        print(f"=== embedding {slide} ===")
        meta = embed_slide(model, processor, device, slide)
        print(f"  {len(meta)} candidates embedded")
        all_meta.extend(meta)

    print(f"\n{'='*80}\nPER-SLIDE RESULTS (N_EXTREME={N_EXTREME})\n{'='*80}")
    per_slide_rho = {}
    for slide in SLIDES:
        rows = [m for m in all_meta if m["slide"] == slide]
        rows_sorted = sorted(rows, key=lambda m: m["dab"])
        suspect = rows_sorted[:N_EXTREME]
        benign_ref = rows_sorted[-N_EXTREME:]
        middle = rows_sorted[N_EXTREME:-N_EXTREME]
        rho, rp = stats.spearmanr([m["dab"] for m in rows], [m["outlier_score"] for m in rows])
        per_slide_rho[slide] = (rho, rp, len(rows))
        s_mean = np.mean([m["outlier_score"] for m in suspect])
        b_mean = np.mean([m["outlier_score"] for m in benign_ref])
        m_mean = np.mean([m["outlier_score"] for m in middle]) if middle else float("nan")
        print(f"{slide} (n={len(rows)}): suspect_outlier={s_mean:.4f}  "
              f"benign_ref_outlier={b_mean:.4f}  middle_outlier={m_mean:.4f}  "
              f"Spearman(dab,outlier)={rho:+.3f} p={rp:.4g}")

    print(f"\n{'='*80}\nPOOLED ACROSS ALL 4 SLIDES (n={len(all_meta)})\n{'='*80}")
    all_suspect, all_benign, all_middle = [], [], []
    for slide in SLIDES:
        rows = sorted([m for m in all_meta if m["slide"] == slide], key=lambda m: m["dab"])
        all_suspect += rows[:N_EXTREME]
        all_benign += rows[-N_EXTREME:]
        all_middle += rows[N_EXTREME:-N_EXTREME]

    s_scores = [m["outlier_score"] for m in all_suspect]
    b_scores = [m["outlier_score"] for m in all_benign]
    m_scores = [m["outlier_score"] for m in all_middle]
    print(f"suspect    (n={len(s_scores)}): mean={np.mean(s_scores):.4f}")
    print(f"benign_ref (n={len(b_scores)}): mean={np.mean(b_scores):.4f}")
    print(f"middle     (n={len(m_scores)}): mean={np.mean(m_scores):.4f}")

    u1, p1 = stats.mannwhitneyu(s_scores, b_scores, alternative="two-sided")
    u2, p2 = stats.mannwhitneyu(s_scores, m_scores, alternative="two-sided")
    print(f"\nsuspect vs benign_ref (pooled, n={len(s_scores)} vs {len(b_scores)}): p={p1:.4g}")
    print(f"suspect vs middle     (pooled, n={len(s_scores)} vs {len(m_scores)}): p={p2:.4g}")

    print("\n--- per-slide Spearman consistency check ---")
    for slide, (rho, rp, n) in per_slide_rho.items():
        print(f"  {slide}: rho={rho:+.3f} p={rp:.4g} (n={n})")

    with open("/tmp/clip_patch_outlier_all4_results.json", "w") as f:
        json.dump(all_meta, f, indent=2)
    print("\nsaved to /tmp/clip_patch_outlier_all4_results.json")


if __name__ == "__main__":
    main()
