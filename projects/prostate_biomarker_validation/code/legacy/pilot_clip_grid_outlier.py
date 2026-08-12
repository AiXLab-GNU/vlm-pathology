"""Fixed-size grid-patch version of the outlier-score test, to control for the gland-area
confound found in pilot_clip_patch_outlier_all4.py (on 1034554, gland area correlated with
dab_ring: rho=+0.336, p=0.009 -- larger glands filled more of the fixed 900x900 crop,
potentially confounding the embedding).

Reference distribution = 171 systematic, non-overlapping 512x512 grid patches covering the
whole slide (tissue_frac>=0.15), NOT our own gland candidates -- this also fixes the second
issue that the old reference was built only from our lumen-detector's own (possibly biased)
candidate set. Suspect/benign_ref crops are re-extracted at the SAME 512x512 size, centered
on the same centroids, so gland size no longer affects how much of the patch is "gland" vs
"surrounding tissue" in a systematically different way between groups.

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_grid_outlier.py
"""
import json
import numpy as np
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

CROPS_DIR = "/tmp/clip_grid_1034554"
MODEL_ID = "openai/clip-vit-large-patch14-336"


def embed(model, processor, device, path):
    image = Image.open(path).convert("RGB")
    with torch.no_grad():
        inputs = processor(images=image, return_tensors="pt").to(device)
        feat = model.get_image_features(**inputs)
        feat = feat / feat.norm(dim=-1, keepdim=True)
    return feat.squeeze(0).cpu().numpy()


def main():
    with open(f"{CROPS_DIR}/grid_meta.json") as f:
        grid_meta = json.load(f)
    with open(f"{CROPS_DIR}/cand_meta.json") as f:
        cand_meta = json.load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)

    grid_embeddings = []
    for m in grid_meta:
        emb = embed(model, processor, device, f"{CROPS_DIR}/grid_{m['idx']:04d}.png")
        grid_embeddings.append(emb)
    grid_embeddings = np.stack(grid_embeddings)
    mean_emb = grid_embeddings.mean(axis=0)
    mean_emb = mean_emb / np.linalg.norm(mean_emb)
    print(f"grid reference: {len(grid_meta)} patches, mean embedding computed")

    # sanity check: what's the outlier-score distribution of the grid patches themselves?
    grid_outlier = 1.0 - grid_embeddings @ mean_emb
    print(f"grid patch outlier scores: mean={grid_outlier.mean():.4f} std={grid_outlier.std():.4f} "
          f"min={grid_outlier.min():.4f} max={grid_outlier.max():.4f}")

    print(f"\n{'='*80}\nCANDIDATE OUTLIER SCORES (512x512, same reference)\n{'='*80}")
    results = []
    for m in cand_meta:
        emb = embed(model, processor, device, f"{CROPS_DIR}/{m['tag']}.png")
        score = float(1.0 - emb @ mean_emb)
        results.append(dict(tag=m['tag'], dab=m['dab'], area=m['area'], outlier_score=score))
        print(f"{m['tag']:14s} dab={m['dab']:.4f} area={m['area']:6d}  outlier_score={score:.4f}")

    susp = [r for r in results if 'suspect' in r['tag']]
    ben = [r for r in results if 'benign_ref' in r['tag']]
    print(f"\nsuspect mean outlier: {np.mean([r['outlier_score'] for r in susp]):.4f}")
    print(f"benign_ref mean outlier: {np.mean([r['outlier_score'] for r in ben]):.4f}")

    rho, p = stats.spearmanr([r['dab'] for r in results], [r['outlier_score'] for r in results])
    print(f"\nSpearman(dab_ring, outlier_score), n={len(results)}: rho={rho:+.3f} p={p:.4g}")
    print("(n=6 only -- read qualitatively; compare direction against the old 900x900 "
          "gland-crop version which gave rho=+0.470 p=0.0002, i.e. WRONG direction)")


if __name__ == "__main__":
    main()
