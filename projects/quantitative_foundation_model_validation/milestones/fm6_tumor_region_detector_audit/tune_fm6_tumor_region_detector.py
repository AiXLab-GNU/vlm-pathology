#!/usr/bin/env python3
"""Train-only CV remediation of the FM6 tumor detector with a new locked holdout."""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
from PIL import Image
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from skimage.color import hed2rgb, rgb2hed
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_fm6_tumor_region_detector_audit as base  # noqa: E402


FOLDS = 3
TUNE_EPOCHS = 5
HOLDOUT_SEED = base.SEED + 1
CANDIDATES = {
    "baseline": {"negative_weight": 1.0, "color": "baseline", "scale": False},
    "strong_color": {"negative_weight": 1.25, "color": "strong", "scale": False},
    "hed_color": {"negative_weight": 1.25, "color": "hed", "scale": False},
    "hed_scale": {"negative_weight": 1.25, "color": "hed", "scale": True},
}


class HedJitter:
    def __init__(self, strength: float = 0.12) -> None:
        self.strength = strength

    def __call__(self, image: Image.Image) -> Image.Image:
        array = np.asarray(image, dtype=np.float32) / 255.0
        hed = rgb2hed(array)
        factors = np.random.uniform(1 - self.strength, 1 + self.strength, size=3)
        shifts = np.random.uniform(-0.015, 0.015, size=3)
        rgb = np.clip(hed2rgb(hed * factors + shifts), 0, 1)
        return Image.fromarray(np.round(rgb * 255).astype(np.uint8), mode="RGB")


class TuneDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, candidate: str, augment: bool) -> None:
        self.frame = frame.reset_index(drop=True)
        config = CANDIDATES[candidate]
        ops: list[object] = []
        if augment:
            ops.extend([transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip()])
            if config["color"] == "baseline":
                ops.append(transforms.RandomApply([transforms.ColorJitter(0.12, 0.12, 0.08, 0.02)], p=0.5))
            elif config["color"] == "strong":
                ops.append(transforms.RandomApply([transforms.ColorJitter(0.35, 0.35, 0.25, 0.06)], p=0.8))
            else:
                ops.append(transforms.RandomApply([HedJitter()], p=0.8))
        if augment and config["scale"]:
            ops.append(transforms.RandomResizedCrop(base.INPUT_SIZE, scale=(0.85, 1.0), ratio=(0.95, 1.05),
                                                     interpolation=transforms.InterpolationMode.BICUBIC))
        else:
            ops.append(transforms.Resize((base.INPUT_SIZE, base.INPUT_SIZE),
                                         interpolation=transforms.InterpolationMode.BICUBIC))
        ops.extend([transforms.ToTensor(),
                    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.transform = transforms.Compose(ops)

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        row = self.frame.iloc[index]
        image = Image.open(base.SICAP / "images" / row.image_name).convert("RGB")
        start = (image.height - base.SICAP_CROP) // 2
        image = image.crop((start, start, start + base.SICAP_CROP, start + base.SICAP_CROP))
        return self.transform(image), torch.tensor(float(row.tumor_present)), \
            torch.tensor(float(row.tumor_fraction)), index


def lock_holdout() -> None:
    frame = pd.read_csv(base.PANDA_CSV)
    with zipfile.ZipFile(base.PANDA_ZIP) as archive:
        available = {Path(name).stem.replace("_mask", "") for name in archive.namelist()
                     if name.startswith("train_label_masks/")}
    opened_path = base.LOCAL / "fm6_panda_selected_source_members.csv"
    opened = set(pd.read_csv(opened_path).image_id) if opened_path.exists() else set()
    frame = frame[frame.image_id.isin(available) & ~frame.image_id.isin(opened)].copy()
    frame["cancer"] = frame.isup_grade.gt(0).astype(int)
    rng = np.random.default_rng(HOLDOUT_SEED)
    parts = []
    for _, group in frame.groupby(["data_provider", "cancer"], sort=True):
        group = group.sort_values("image_id").reset_index(drop=True)
        parts.append(group.iloc[np.sort(rng.choice(len(group), 25, replace=False))])
    holdout = pd.concat(parts, ignore_index=True).sort_values(["data_provider", "cancer", "image_id"])
    path = base.OUTPUTS / "fm6_panda_remediation_holdout_manifest.csv"
    holdout[["image_id", "data_provider", "isup_grade", "cancer"]].to_csv(path, index=False, lineterminator="\n")
    base.stable_json(base.OUTPUTS / "fm6_panda_remediation_holdout_lock.json", {
        "seed": HOLDOUT_SEED, "slides": len(holdout), "opened_slides_excluded": len(opened),
        "manifest_sha256": base.sha256_file(path), "pixels_or_detector_scores_read": False,
    })
    print(holdout.groupby(["data_provider", "cancer"]).size())


def weighted_binary_loss(logit: torch.Tensor, target: torch.Tensor, negative_weight: float) -> torch.Tensor:
    raw = nn.functional.binary_cross_entropy_with_logits(logit, target, reduction="none")
    weight = torch.where(target > 0.5, torch.ones_like(target), torch.full_like(target, negative_weight))
    return (raw * weight).mean()


def train_candidate(candidate: str) -> None:
    if candidate not in CANDIDATES:
        raise ValueError(candidate)
    base.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = base.read_sicap_partition("Train")
    splitter = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=base.SEED)
    candidate_dir = base.LOCAL / "remediation_cv" / candidate
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for fold, (train_idx, val_idx) in enumerate(splitter.split(frame, frame.tumor_present, frame.slide_id)):
        model = base.make_model().to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
        train_frame = frame.iloc[train_idx].reset_index(drop=True)
        val_frame = frame.iloc[val_idx].reset_index(drop=True)
        train_loader = DataLoader(TuneDataset(train_frame, candidate, True), batch_size=base.BATCH_SIZE,
                                  shuffle=True, num_workers=8, pin_memory=True, persistent_workers=True)
        val_loader = DataLoader(TuneDataset(val_frame, candidate, False), batch_size=base.BATCH_SIZE,
                                shuffle=False, num_workers=8, pin_memory=True, persistent_workers=True)
        best = None
        for epoch in range(1, TUNE_EPOCHS + 1):
            model.train()
            for images, binary, fraction, _ in train_loader:
                images, binary, fraction = images.to(device), binary.to(device), fraction.to(device)
                optimizer.zero_grad(set_to_none=True)
                logits = model(images)
                loss = weighted_binary_loss(logits[:, 0], binary, CANDIDATES[candidate]["negative_weight"])
                loss = loss + 0.5 * nn.functional.mse_loss(torch.sigmoid(logits[:, 1]), fraction)
                loss.backward()
                optimizer.step()
            score, fraction_hat, y, index = base.predict_loader(model, val_loader, device)
            auc = roc_auc_score(y, score)
            if best is None or auc > best["auc"]:
                best = {"auc": float(auc), "epoch": epoch, "score": score, "fraction_hat": fraction_hat,
                        "y": y, "index": index}
            print(json.dumps({"candidate": candidate, "fold": fold, "epoch": epoch, "val_auroc": auc}), flush=True)
        assert best is not None
        np.savez_compressed(candidate_dir / f"fold_{fold}.npz", score=best["score"], y=best["y"],
                            fraction_hat=best["fraction_hat"], index=best["index"],
                            slide_id=val_frame.iloc[best["index"]].slide_id.to_numpy(str),
                            tumor_fraction=val_frame.iloc[best["index"]].tumor_fraction.to_numpy(float),
                            epoch=np.array([best["epoch"]]), auc=np.array([best["auc"]]))


def balanced_threshold(y: np.ndarray, score: np.ndarray) -> tuple[float, float, float]:
    best = None
    for threshold in np.unique(np.r_[0.0, score, 1.0]):
        pred = score >= threshold
        sensitivity = float(pred[y == 1].mean())
        specificity = float((~pred[y == 0]).mean())
        if sensitivity < 0.82 or specificity < 0.82:
            continue
        candidate = (min(sensitivity, specificity), sensitivity + specificity, -float(threshold),
                     float(threshold), sensitivity, specificity)
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    if best is None:
        return float("nan"), float("nan"), float("nan")
    return best[3], best[4], best[5]


def select_candidate() -> None:
    rows = []
    for order, candidate in enumerate(CANDIDATES):
        paths = sorted((base.LOCAL / "remediation_cv" / candidate).glob("fold_*.npz"))
        if len(paths) != FOLDS:
            raise RuntimeError(f"missing CV folds for {candidate}")
        arrays = [np.load(path, allow_pickle=False) for path in paths]
        score = np.concatenate([item["score"] for item in arrays])
        y = np.concatenate([item["y"] for item in arrays])
        threshold, sensitivity, specificity = balanced_threshold(y, score)
        rows.append({"candidate": candidate, "candidate_order": order, "n": len(y),
                     "oof_auroc": roc_auc_score(y, score), "threshold": threshold,
                     "sensitivity": sensitivity, "specificity": specificity,
                     "min_sensitivity_specificity": min(sensitivity, specificity),
                     "fold_auc_min": min(float(item["auc"][0]) for item in arrays),
                     "median_best_epoch": int(np.median([int(item["epoch"][0]) for item in arrays]))})
    summary = pd.DataFrame(rows)
    eligible = summary.dropna().sort_values(["min_sensitivity_specificity", "oof_auroc", "candidate_order"],
                                            ascending=[False, False, True])
    if eligible.empty:
        raise RuntimeError("no remediation candidate met OOF balance floor")
    selected = eligible.iloc[0]
    summary["selected"] = summary.candidate.eq(selected.candidate)
    summary.to_csv(base.OUTPUTS / "fm6_detector_remediation_cv_summary.csv", index=False, lineterminator="\n")
    base.stable_json(base.OUTPUTS / "fm6_detector_remediation_selection.json", {
        "candidate": selected.candidate, "threshold": selected.threshold,
        "oof_auroc": selected.oof_auroc, "sensitivity": selected.sensitivity,
        "specificity": selected.specificity, "epochs": TUNE_EPOCHS,
        "holdout_manifest_sha256": base.sha256_file(base.OUTPUTS / "fm6_panda_remediation_holdout_manifest.csv"),
        "opened_sicap_or_panda_used_for_selection": False,
    })
    print(summary.to_string(index=False))


def train_final() -> None:
    selection = json.loads((base.OUTPUTS / "fm6_detector_remediation_selection.json").read_text())
    candidate = selection["candidate"]
    base.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = base.read_sicap_partition("Train")
    model = base.make_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    loader = DataLoader(TuneDataset(frame, candidate, True), batch_size=base.BATCH_SIZE, shuffle=True,
                        num_workers=8, pin_memory=True, persistent_workers=True)
    started = time.time()
    for epoch in range(1, TUNE_EPOCHS + 1):
        model.train()
        for images, binary, fraction, _ in loader:
            images, binary, fraction = images.to(device), binary.to(device), fraction.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = weighted_binary_loss(logits[:, 0], binary, CANDIDATES[candidate]["negative_weight"])
            loss = loss + 0.5 * nn.functional.mse_loss(torch.sigmoid(logits[:, 1]), fraction)
            loss.backward(); optimizer.step()
        print(f"final {candidate} epoch {epoch}/{TUNE_EPOCHS}", flush=True)
    path = base.LOCAL / "fm6_sicap_resnet18_tumor_detector_remediated.pt"
    torch.save({"state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                "threshold": selection["threshold"], "candidate": candidate, "epochs": TUNE_EPOCHS}, path)
    base.stable_json(base.OUTPUTS / "fm6_detector_remediation_training_run_config.json", {
        "candidate": candidate, "threshold": selection["threshold"], "epochs": TUNE_EPOCHS,
        "checkpoint_sha256": base.sha256_file(path), "elapsed_seconds": time.time() - started,
        "holdout_opened": False,
    })


def load_remediated(device: torch.device):
    path = base.LOCAL / "fm6_sicap_resnet18_tumor_detector_remediated.pt"
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = base.make_model()
    model.load_state_dict(payload["state_dict"])
    return model.to(device).eval(), payload


def audit_holdout() -> None:
    base.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, payload = load_remediated(device)
    transform = base.deterministic_inference_transform()
    selected = pd.read_csv(base.OUTPUTS / "fm6_panda_remediation_holdout_manifest.csv")
    locked_hash = json.loads((base.OUTPUTS / "fm6_panda_remediation_holdout_lock.json").read_text())["manifest_sha256"]
    if base.sha256_file(base.OUTPUTS / "fm6_panda_remediation_holdout_manifest.csv") != locked_hash:
        raise RuntimeError("holdout manifest changed after lock")
    rng = np.random.default_rng(HOLDOUT_SEED)
    predictions = []
    sources = []
    with zipfile.ZipFile(base.PANDA_ZIP) as archive:
        for position, row in selected.iterrows():
            image_path = base.PANDA_IMAGES / f"{row.image_id}.tiff"
            member = f"train_label_masks/{row.image_id}_mask.tiff"
            info = archive.getinfo(member)
            mask_bytes = archive.read(member)
            with tifffile.TiffFile(image_path) as image_tiff, tifffile.TiffFile(io.BytesIO(mask_bytes)) as mask_tiff:
                level = 1 if len(image_tiff.pages) > 1 else 0
                image = image_tiff.pages[level].asarray()[..., :3]
                raw_mask = mask_tiff.pages[level].asarray()
                if raw_mask.ndim == 3:
                    raw_mask = raw_mask[..., 0]
                mpp = base.page_mpp(image_tiff.pages[level])
            if row.data_provider == "karolinska":
                tumor, tissue = raw_mask == 2, raw_mask > 0
            else:
                tumor, tissue = raw_mask >= 3, raw_mask > 0
            window = max(16, int(round(base.BOUNDARY_UM / mpp)))
            if window % 2:
                window += 1
            radius = window // 2
            coordinates = np.argwhere(tissue)
            valid = ((coordinates[:, 0] >= radius) & (coordinates[:, 0] < image.shape[0] - radius) &
                     (coordinates[:, 1] >= radius) & (coordinates[:, 1] < image.shape[1] - radius))
            coordinates = coordinates[valid]
            if len(coordinates) > 5000:
                coordinates = coordinates[rng.choice(len(coordinates), 5000, replace=False)]
            fractions = base.integral_fraction(tumor, coordinates, radius)
            positive = np.flatnonzero(fractions >= base.TUMOR_FRACTION_CUTOFF)
            negative = np.flatnonzero(fractions < base.TUMOR_FRACTION_CUTOFF)
            if int(row.cancer):
                pos_take = min(base.PANDA_PATCHES_PER_SLIDE // 2, len(positive))
                neg_take = min(base.PANDA_PATCHES_PER_SLIDE - pos_take, len(negative))
            else:
                pos_take = 0
                neg_take = min(base.PANDA_PATCHES_PER_SLIDE, len(negative))
            chosen = np.r_[rng.choice(positive, pos_take, replace=False) if pos_take else np.array([], int),
                           rng.choice(negative, neg_take, replace=False) if neg_take else np.array([], int)]
            tensors, meta = [], []
            for candidate_index in chosen:
                y, x = coordinates[candidate_index]
                crop = image[y-radius:y+radius, x-radius:x+radius]
                canonical = Image.fromarray(crop).resize((448, 448), Image.Resampling.BICUBIC)
                tensors.append(transform(canonical))
                meta.append((int(y), int(x), float(fractions[candidate_index])))
            if tensors:
                with torch.inference_mode():
                    score = torch.sigmoid(model(torch.stack(tensors).to(device))[:, 0]).cpu().numpy()
                for patch_index, ((y, x, fraction), value) in enumerate(zip(meta, score)):
                    predictions.append({"image_id": row.image_id, "slide_id": row.image_id,
                                        "provider": row.data_provider, "patch_index": patch_index,
                                        "center_y": y, "center_x": x, "mpp": mpp,
                                        "tumor_fraction": fraction,
                                        "tumor_present": int(fraction >= base.TUMOR_FRACTION_CUTOFF),
                                        "score": float(value)})
            sources.append({"image_id": row.image_id, "provider": row.data_provider,
                            "image_size": image_path.stat().st_size, "mask_member_size": info.file_size,
                            "mask_member_crc32": f"{info.CRC:08x}", "patches": len(tensors)})
            print(f"remediation holdout {position + 1}/{len(selected)} {row.data_provider} patches={len(tensors)}", flush=True)
    pred = pd.DataFrame(predictions)
    pred_path = base.LOCAL / "fm6_panda_remediation_holdout_predictions.csv"
    pred.to_csv(pred_path, index=False, lineterminator="\n")
    pd.DataFrame(sources).to_csv(base.LOCAL / "fm6_panda_remediation_holdout_sources.csv", index=False, lineterminator="\n")
    rows = []
    threshold = float(payload["threshold"])
    for provider, group in pred.groupby("provider"):
        metrics = base.binary_metrics(group.tumor_present.to_numpy(), group.score.to_numpy(), threshold)
        passed = (metrics["n_positive"] >= 100 and metrics["n_negative"] >= 100 and
                  metrics["auroc"] >= 0.80 and metrics["sensitivity"] >= 0.75 and
                  metrics["specificity"] >= 0.70)
        rows.append({"provider": provider, **metrics, "threshold": threshold,
                     "gate": "PASS_REMEDIATION_EXTERNAL_HOLDOUT" if passed else "FAIL_REMEDIATION_EXTERNAL_HOLDOUT"})
    summary = pd.DataFrame(rows)
    summary.to_csv(base.OUTPUTS / "fm6_panda_remediation_holdout_summary.csv", index=False, lineterminator="\n")
    base.stable_json(base.OUTPUTS / "fm6_panda_remediation_holdout_run_config.json", {
        "checkpoint_sha256": base.sha256_file(base.LOCAL / "fm6_sicap_resnet18_tumor_detector_remediated.pt"),
        "holdout_manifest_sha256": locked_hash, "predictions_sha256": base.sha256_file(pred_path),
        "threshold": threshold, "threshold_changed_after_holdout": False,
    })
    print(summary.to_string(index=False))


def evaluate_opened_sicap() -> None:
    """Secondary re-evaluation only; this opened test cannot select the remediated model."""
    base.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, payload = load_remediated(device)
    frame = base.read_sicap_partition("Test")
    loader = DataLoader(TuneDataset(frame, payload["candidate"], False), batch_size=base.BATCH_SIZE,
                        shuffle=False, num_workers=8, pin_memory=True)
    score, fraction_hat, y, index = base.predict_loader(model, loader, device)
    order = np.argsort(index)
    metrics = base.binary_metrics(y[order], score[order], float(payload["threshold"]))
    metrics.update({
        "cohort": "SICAPv2_opened_secondary_re_evaluation",
        "threshold": float(payload["threshold"]),
        "fraction_spearman": float(pd.Series(frame.iloc[index[order]].tumor_fraction.to_numpy()).corr(
            pd.Series(fraction_hat[order]), method="spearman")),
        "selection_role": "NOT_USED_OPENED_SECONDARY_ONLY",
    })
    pd.DataFrame([metrics]).to_csv(base.OUTPUTS / "fm6_sicap_remediation_opened_test_summary.csv",
                                    index=False, lineterminator="\n")
    print(json.dumps(metrics, indent=2))


def report_remediation() -> None:
    cv = pd.read_csv(base.OUTPUTS / "fm6_detector_remediation_cv_summary.csv")
    selected = cv[cv.selected].iloc[0]
    sicap = pd.read_csv(base.OUTPUTS / "fm6_sicap_remediation_opened_test_summary.csv").iloc[0]
    holdout = pd.read_csv(base.OUTPUTS / "fm6_panda_remediation_holdout_summary.csv")
    passed = holdout.gate.eq("PASS_REMEDIATION_EXTERNAL_HOLDOUT").all()
    lines = [
        "---",
        "document_id: fm6-tumor-region-detector-remediation-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: generated",
        "created: 2026-08-16",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_tumor_region_detector_audit/outputs/fm6-tumor-region-detector-remediation-report.md",
        "---", "", "# FM6 tumor-region detector remediation", "",
        "## Train-only selection", "",
        f"- Selected candidate: {selected.candidate}; 3-fold OOF AUROC={selected.oof_auroc:.3f}; sensitivity={selected.sensitivity:.3f}; specificity={selected.specificity:.3f}.",
        f"- Locked OOF threshold: {selected.threshold:.6f}.",
        "- Opened SICAP test and prior PANDA 40 slides were not used for selection.", "",
        "## Opened SICAP secondary re-evaluation", "",
        f"- AUROC={sicap.auroc:.3f}; sensitivity={sicap.sensitivity:.3f}; specificity={sicap.specificity:.3f}; balanced accuracy={sicap.balanced_accuracy:.3f}.",
        "- This clears the original numeric SICAP gate only as a secondary re-evaluation; it is not a new independent test.", "",
        "## Newly locked PANDA 100-slide holdout", "",
    ]
    for row in holdout.itertuples(index=False):
        lines.append(f"- {row.provider}: n={row.n}; AUROC={row.auroc:.3f}; sensitivity={row.sensitivity:.3f}; specificity={row.specificity:.3f}; gate={row.gate}.")
    lines.extend(["", "## Decision", "",
                  f"- Remediation external holdout gate: {'PASS' if passed else 'FAIL'}.",
                  "- TCGA scoring and detector-restricted H2 remain NOT RUN.",
                  "- The remaining problem is cross-domain calibration/sensitivity, not merely SICAP discrimination.",
                  "- Strong H2 and external T remain PROHIBITED.", ""])
    (base.OUTPUTS / "fm6-tumor-region-detector-remediation-report.md").write_text("\n".join(lines))
    pd.DataFrame([{
        "sicap_secondary_numeric_gate": "PASS" if sicap.sensitivity >= .85 and sicap.specificity >= .80 else "FAIL",
        "new_panda_holdout_gate": "PASS" if passed else "FAIL",
        "tcga_application": "NOT_RUN",
        "strong_H2": "PROHIBITED",
    }]).to_csv(base.OUTPUTS / "fm6_tumor_region_detector_remediation_evidence_gate.csv",
              index=False, lineterminator="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["lock-holdout", "train-candidate", "select-candidate", "train-final", "audit-holdout", "evaluate-opened-sicap", "report-remediation"])
    parser.add_argument("--candidate", choices=list(CANDIDATES))
    args = parser.parse_args()
    if args.stage == "lock-holdout": lock_holdout()
    elif args.stage == "train-candidate":
        if args.candidate is None: parser.error("--candidate required")
        train_candidate(args.candidate)
    elif args.stage == "select-candidate": select_candidate()
    elif args.stage == "train-final": train_final()
    elif args.stage == "audit-holdout": audit_holdout()
    elif args.stage == "evaluate-opened-sicap": evaluate_opened_sicap()
    else: report_remediation()


if __name__ == "__main__":
    main()
