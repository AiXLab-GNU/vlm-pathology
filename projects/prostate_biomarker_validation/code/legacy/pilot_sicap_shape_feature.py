"""Sanity-check pilot (not a full validation): does the GNUH shape-filter logic
(solidity, circularity, thickness = area/perimeter from common.py's find_gland_candidates)
even produce sensible lumen candidates on SICAPv2's 512x512 H&E patches, before committing to
a larger cribriform-label correlation study?

This intentionally strips out the IHC-specific parts of find_gland_candidates (ring dilation,
DAB/hematoxylin channel checks) -- SICAPv2 has no DAB channel -- and keeps only the
white-lumen detection + area filter + regionprops shape stats, which are stain-agnostic.

Run with any venv that has numpy/PIL/scikit-image/scipy (resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch already does):
    resources/projects/prostate_biomarker_validation/model_workspace/.venv-conch/bin/python resources/projects/prostate_biomarker_validation/model_workspace/pilot_sicap_shape_feature.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.measure import regionprops

SICAP_ROOT = "/home/jinhyun/prj_ws/prj_jin/vlm-pathology/resources/data/shared/opendataset/SICAPv2/SICAPv2/images"

EXAMPLES = [
    ("cribriform_positive (G4C=1)", "16B0008067_Block_Region_0_14_8_xini_17003_yini_111305.jpg"),
    ("cribriform_negative (G4C=0)", "16B0003388_Block_Region_13_10_1_xini_8636_yini_63869.jpg"),
]


def find_lumen_shapes(arr, white_thresh=205, black_thresh=20, min_lumen_area=2500, max_lumen_area=250000):
    gray = arr.mean(axis=2)
    white = gray > white_thresh
    black_bg = gray < black_thresh
    tissue_free = white & (~black_bg)

    lbl, n = ndi.label(tissue_free)
    border_ids = set(np.unique(np.concatenate([lbl[0, :], lbl[-1, :], lbl[:, 0], lbl[:, -1]])))
    border_ids.discard(0)
    areas = np.bincount(lbl.ravel())

    results = []
    for lid in range(1, n + 1):
        if lid in border_ids:
            continue
        area = areas[lid]
        if area < min_lumen_area or area > max_lumen_area:
            continue
        region = (lbl == lid).astype(np.uint8)
        rp = regionprops(region)[0]
        perim = rp.perimeter
        circularity = 4 * np.pi * rp.area / (perim ** 2) if perim > 0 else 0
        thickness = rp.area / perim if perim > 0 else 0
        results.append(dict(area=int(area), solidity=rp.solidity, circularity=circularity,
                             thickness=thickness))
    return results, tissue_free


def main():
    for label, fname in EXAMPLES:
        path = os.path.join(SICAP_ROOT, fname)
        arr = np.array(Image.open(path).convert("RGB"))
        print(f"\n=== {label}: {fname} ===")
        print(f"  patch shape: {arr.shape}, white-pixel fraction: {(arr.mean(axis=2) > 205).mean():.3f}")
        candidates, _ = find_lumen_shapes(arr)
        print(f"  {len(candidates)} lumen candidates found (area filter only, no DAB/ring check)")
        for i, c in enumerate(sorted(candidates, key=lambda c: -c["area"])):
            print(f"    #{i+1}: area={c['area']:6d}px  solidity={c['solidity']:.3f}  "
                  f"circularity={c['circularity']:.3f}  thickness={c['thickness']:.2f}px")


if __name__ == "__main__":
    main()
