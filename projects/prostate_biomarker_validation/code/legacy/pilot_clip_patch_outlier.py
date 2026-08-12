"""Patch-to-patch embedding comparison (no text prompt) -- the within-slide relative
approach, matching axis C's lesson (no absolute reference works; only within-slide
relative comparison is defensible).

Embed ALL 152 detected gland candidates on 1034538.svs with CLIP's image encoder only
(no text prompt at all). Compute each patch's outlier score as its distance from the
mean embedding of the whole population of patches on this same slide. Then check whether
the extreme-low-dab_ring (suspect) and extreme-high-dab_ring (benign_ref) candidates --
already known from our own pipeline -- show different outlier-score distributions than
the bulk of "typical" mid-ranked candidates.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_patch_outlier.py
"""
import json
import numpy as np
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

CROPS_DIR = "/tmp/clip_patch_all_1034538"
MODEL_ID = "openai/clip-vit-large-patch14-336"
N_EXTREME = 15  # how many lowest/highest dab_ring candidates count as "suspect"/"benign_ref"


def main():
    with open(f"{CROPS_DIR}/meta.json") as f:
        meta = json.load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)

    embeddings = []
    for m in meta:
        path = f"{CROPS_DIR}/cand_{m['idx']:03d}.png"
        image = Image.open(path).convert("RGB")
        with torch.no_grad():
            inputs = processor(images=image, return_tensors="pt").to(device)
            feat = model.get_image_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        embeddings.append(feat.squeeze(0).cpu().numpy())
        if m["idx"] % 30 == 0:
            print(f"  embedded {m['idx']}/{len(meta)}")

    embeddings = np.stack(embeddings)  # (152, dim)
    mean_emb = embeddings.mean(axis=0)
    mean_emb = mean_emb / np.linalg.norm(mean_emb)

    # outlier score = 1 - cosine similarity to the whole-slide mean embedding
    outlier_scores = 1.0 - embeddings @ mean_emb

    for m, score in zip(meta, outlier_scores):
        m["outlier_score"] = float(score)

    meta_sorted_by_dab = sorted(meta, key=lambda m: m["dab"])
    suspect = meta_sorted_by_dab[:N_EXTREME]
    benign_ref = meta_sorted_by_dab[-N_EXTREME:]
    middle = meta_sorted_by_dab[N_EXTREME:-N_EXTREME]

    print(f"\n{'='*80}\nSUMMARY (n_total={len(meta)}, N_EXTREME={N_EXTREME} each side)\n{'='*80}")
    for name, group in [("suspect (lowest dab_ring)", suspect),
                         ("benign_ref (highest dab_ring)", benign_ref),
                         ("middle (typical)", middle)]:
        scores = [m["outlier_score"] for m in group]
        print(f"{name:32s} n={len(scores):3d}  mean_outlier={np.mean(scores):.4f}  "
              f"median={np.median(scores):.4f}")

    u1, p1 = stats.mannwhitneyu([m["outlier_score"] for m in suspect],
                                 [m["outlier_score"] for m in middle], alternative="two-sided")
    u2, p2 = stats.mannwhitneyu([m["outlier_score"] for m in benign_ref],
                                 [m["outlier_score"] for m in middle], alternative="two-sided")
    u3, p3 = stats.mannwhitneyu([m["outlier_score"] for m in suspect],
                                 [m["outlier_score"] for m in benign_ref], alternative="two-sided")
    print(f"\nsuspect vs middle:     Mann-Whitney p={p1:.4g}")
    print(f"benign_ref vs middle:  Mann-Whitney p={p2:.4g}")
    print(f"suspect vs benign_ref: Mann-Whitney p={p3:.4g}")

    rho, rp = stats.spearmanr([m["dab"] for m in meta], [m["outlier_score"] for m in meta])
    print(f"\nSpearman(dab_ring, outlier_score) across all {len(meta)} candidates = {rho:+.3f} p={rp:.4g}")

    with open("/tmp/clip_patch_outlier_results.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("\nsaved to /tmp/clip_patch_outlier_results.json")


if __name__ == "__main__":
    main()
