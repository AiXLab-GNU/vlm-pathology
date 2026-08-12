"""CLIP similarity test on NADT PIN-4 crops -- where our own rgb2hed-based dab_ring collapsed
(dual-chromogen problem). Tests whether CLIP's learned embedding (no explicit color
deconvolution) can still separate candidates, using two real slides with contrasting
ground truth: a BENIGN-phenotype slide (1014, no cancer) and a Gleason 5+5=10 slide (1039).

Run with the VLM-only venv:
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-quilt/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_clip_nadt_pin4.py
"""
import os
import glob
import torch
from transformers import CLIPModel, CLIPProcessor
from PIL import Image
from scipy import stats

CROPS_DIR = "/tmp/nadt_pin4_crops"
MODEL_ID = "openai/clip-vit-large-patch14-336"

TEXT_BENIGN = ("a histopathology image of a prostate gland with an intact, continuous brown "
               "basal cell layer ring, benign")
TEXT_MALIGNANT = ("a histopathology image of a prostate gland with loss of the basal cell "
                  "layer, no ring, suspicious for carcinoma")


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_ID)

    with torch.no_grad():
        text_inputs = processor(text=[TEXT_BENIGN, TEXT_MALIGNANT], return_tensors="pt",
                                 padding=True).to(device)
        text_features = model.get_text_features(**text_inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    paths = sorted(glob.glob(os.path.join(CROPS_DIR, "*_suspect_*.png")) +
                   glob.glob(os.path.join(CROPS_DIR, "*_benign_ref_*.png")))

    results = []
    for path in paths:
        fname = os.path.basename(path)
        slide = "benign_1014" if fname.startswith("benign_1014") else "high_1039"
        label = "suspect" if "_suspect_" in fname else "benign_ref"
        image = Image.open(path).convert("RGB")
        with torch.no_grad():
            img_inputs = processor(images=image, return_tensors="pt").to(device)
            img_features = model.get_image_features(**img_inputs)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)
            sims = (img_features @ text_features.T).squeeze(0).cpu().tolist()
        score = sims[1] - sims[0]
        results.append(dict(slide=slide, fname=fname, label=label, score=score))
        print(f"{fname:35s} slide={slide:12s} label={label:10s} score={score:+.4f}")

    print(f"\n{'='*80}\nSUMMARY\n{'='*80}")
    for slide in ["benign_1014", "high_1039"]:
        rows = [r for r in results if r["slide"] == slide]
        susp = [r["score"] for r in rows if r["label"] == "suspect"]
        ben = [r["score"] for r in rows if r["label"] == "benign_ref"]
        print(f"\n{slide}: n_suspect={len(susp)} n_benign_ref={len(ben)}")
        print(f"  suspect scores:    {[f'{s:+.4f}' for s in susp]}")
        print(f"  benign_ref scores: {[f'{s:+.4f}' for s in ben]}")
        if len(susp) >= 2 and len(ben) >= 2:
            u, p = stats.mannwhitneyu(susp, ben, alternative="two-sided")
            print(f"  Mann-Whitney p={p:.4g}")
        print(f"  ALL scores range: [{min(r['score'] for r in rows):+.4f}, "
              f"{max(r['score'] for r in rows):+.4f}] (spread={max(r['score'] for r in rows)-min(r['score'] for r in rows):.4f})")

    print("\n--- cross-slide comparison: does the truly-BENIGN slide score lower overall than the HIGH-GRADE slide? ---")
    all_benign_slide = [r["score"] for r in results if r["slide"] == "benign_1014"]
    all_high_slide = [r["score"] for r in results if r["slide"] == "high_1039"]
    print(f"benign_1014 (truly benign, all candidates) mean={sum(all_benign_slide)/len(all_benign_slide):+.4f}")
    print(f"high_1039   (Gleason 5+5=10, all candidates) mean={sum(all_high_slide)/len(all_high_slide):+.4f}")
    u2, p2 = stats.mannwhitneyu(all_benign_slide, all_high_slide, alternative="two-sided")
    print(f"Mann-Whitney (benign slide vs high-grade slide, all candidates pooled) p={p2:.4g}")


if __name__ == "__main__":
    main()
