#!/usr/bin/env python3
"""Train, audit, and apply the FM6 outcome-independent tumor-tile detector."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import torch
from PIL import Image
from scipy import stats
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import resnet18


ROOT = Path(__file__).resolve().parents[4]
MILESTONE = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_tumor_region_detector_audit"
OUTPUTS = MILESTONE / "outputs"
LOCAL = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_tumor_region_detector_audit"
SICAP = ROOT / "resources/data/shared/opendataset/SICAPv2/SICAPv2"
PANDA_ROOT = ROOT / "resources/data/shared/opendataset"
PANDA_CSV = PANDA_ROOT / "PANDA_extracted/train.csv"
PANDA_IMAGES = PANDA_ROOT / "PANDA_extracted/train_images"
PANDA_ZIP = PANDA_ROOT / "PANDA/prostate-cancer-grade-assessment.zip"
TCGA_OUTPUTS = ROOT / "projects/quantitative_foundation_model_validation/milestones/fm6_internal_development_pilot/outputs"
TCGA_CROPS = ROOT / "resources/artifacts/quantitative_foundation_model_validation/fm6_internal_development_pilot/shared_canonical_crops"
WEIGHTS = Path("/home/jinhyun/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth")

SEED = 20260816
BOUNDARY_UM = 394.24
SICAP_CROP = 394
INPUT_SIZE = 224
TUMOR_FRACTION_CUTOFF = 0.10
EPOCHS = 8
BATCH_SIZE = 128
BOOTSTRAPS = 1000
PANDA_SLIDES_PER_STRATUM = 10
PANDA_PATCHES_PER_SLIDE = 32


def sha256_file(path: Path, block: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def set_seed() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)


def slide_id(name: str) -> str:
    return Path(name).stem.split("_Block_")[0]


def sicap_fraction(mask_path: Path) -> float:
    mask = np.asarray(Image.open(mask_path))
    start = (mask.shape[0] - SICAP_CROP) // 2
    crop = mask[start:start + SICAP_CROP, start:start + SICAP_CROP]
    return float((crop > 0).mean())


def read_sicap_partition(split: str) -> pd.DataFrame:
    frame = pd.read_excel(SICAP / f"partition/Test/{split}.xlsx")
    frame["image_name"] = frame.image_name.astype(str)
    frame["slide_id"] = frame.image_name.map(slide_id)
    frame["mask_name"] = frame.image_name.map(lambda value: Path(value).with_suffix(".png").name)
    frame["tumor_fraction"] = [sicap_fraction(SICAP / "masks" / value) for value in frame.mask_name]
    frame["tumor_present"] = frame.tumor_fraction.ge(TUMOR_FRACTION_CUTOFF).astype(int)
    return frame


class SicapDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, augment: bool) -> None:
        self.frame = frame.reset_index(drop=True)
        ops: list[object] = []
        if augment:
            ops.extend([
                transforms.RandomHorizontalFlip(),
                transforms.RandomVerticalFlip(),
                transforms.RandomApply([transforms.ColorJitter(0.12, 0.12, 0.08, 0.02)], p=0.5),
            ])
        ops.extend([
            transforms.Resize((INPUT_SIZE, INPUT_SIZE), interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.transform = transforms.Compose(ops)

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int]:
        row = self.frame.iloc[index]
        image = Image.open(SICAP / "images" / row.image_name).convert("RGB")
        start = (image.height - SICAP_CROP) // 2
        image = image.crop((start, start, start + SICAP_CROP, start + SICAP_CROP))
        return (
            self.transform(image),
            torch.tensor(float(row.tumor_present), dtype=torch.float32),
            torch.tensor(float(row.tumor_fraction), dtype=torch.float32),
            index,
        )


def make_model() -> nn.Module:
    model = resnet18(weights=None)
    state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.fc = nn.Linear(model.fc.in_features, 2)
    return model


@torch.inference_mode()
def predict_loader(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    scores: list[np.ndarray] = []
    fractions: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    model.eval()
    for images, binary, _, index in loader:
        logits = model(images.to(device, non_blocking=True))
        scores.append(torch.sigmoid(logits[:, 0]).cpu().numpy())
        fractions.append(torch.sigmoid(logits[:, 1]).cpu().numpy())
        labels.append(binary.numpy())
        indices.append(index.numpy())
    return tuple(np.concatenate(values) for values in (scores, fractions, labels, indices))  # type: ignore[return-value]


def choose_threshold(y: np.ndarray, score: np.ndarray) -> tuple[float, float, float, float]:
    candidates = np.unique(np.r_[0.0, score, 1.0])
    best: tuple[float, float, float, float] | None = None
    for threshold in candidates:
        pred = score >= threshold
        sensitivity = float(pred[y == 1].mean())
        specificity = float((~pred[y == 0]).mean())
        balanced = (sensitivity + specificity) / 2
        candidate = (balanced, sensitivity, specificity, float(threshold))
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    assert best is not None
    return best[3], best[0], best[1], best[2]


def binary_metrics(y: np.ndarray, score: np.ndarray, threshold: float) -> dict[str, float]:
    pred = score >= threshold
    sensitivity = float(pred[y == 1].mean()) if np.any(y == 1) else float("nan")
    specificity = float((~pred[y == 0]).mean()) if np.any(y == 0) else float("nan")
    return {
        "n": int(len(y)),
        "n_positive": int(y.sum()),
        "n_negative": int((1 - y).sum()),
        "auroc": float(roc_auc_score(y, score)),
        "auprc": float(average_precision_score(y, score)),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
    }


def bootstrap_metrics(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    groups = frame.slide_id.unique()
    rows = []
    for replicate in range(BOOTSTRAPS):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        parts = [frame[frame.slide_id.eq(group)] for group in sampled]
        boot = pd.concat(parts, ignore_index=True)
        if boot.tumor_present.nunique() < 2:
            continue
        metrics = binary_metrics(boot.tumor_present.to_numpy(), boot.score.to_numpy(), threshold)
        rows.append({"replicate": replicate, **metrics})
    return pd.DataFrame(rows)


def prepare() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    train = read_sicap_partition("Train")
    test = read_sicap_partition("Test")
    overlap = sorted(set(train.slide_id) & set(test.slide_id))
    images = {path.stem for path in (SICAP / "images").glob("*.jpg")}
    masks = {path.stem for path in (SICAP / "masks").glob("*.png")}
    audit = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_sha256": "e08c5c17d03096baf10805daf54ec05b91ef6e7835a8cff66e5df862d29ad8f1",
        "images": len(images),
        "masks": len(masks),
        "paired": len(images & masks),
        "official_train_tiles": len(train),
        "official_test_tiles": len(test),
        "official_train_slides": int(train.slide_id.nunique()),
        "official_test_slides": int(test.slide_id.nunique()),
        "train_test_slide_overlap": overlap,
        "boundary_um": BOUNDARY_UM,
        "tumor_fraction_cutoff": TUMOR_FRACTION_CUTOFF,
        "status": "PASS" if not overlap and len(images & masks) == 18783 else "FAIL",
    }
    stable_json(OUTPUTS / "fm6_sicap_source_integrity_audit.json", audit)
    summary = pd.DataFrame([
        {"split": name.lower(), "tiles": len(frame), "slides": frame.slide_id.nunique(),
         "positive": int(frame.tumor_present.sum()), "negative": int((1-frame.tumor_present).sum()),
         "tumor_fraction_median": frame.tumor_fraction.median()}
        for name, frame in [("Train", train), ("Test", test)]
    ])
    summary.to_csv(OUTPUTS / "fm6_sicap_partition_summary.csv", index=False, lineterminator="\n")
    if audit["status"] != "PASS":
        raise RuntimeError(audit)
    print(json.dumps(audit, indent=2))


def train() -> None:
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = read_sicap_partition("Train")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    dev_idx, val_idx = next(splitter.split(frame, frame.tumor_present, frame.slide_id))
    dev = frame.iloc[dev_idx].reset_index(drop=True)
    val = frame.iloc[val_idx].reset_index(drop=True)
    model = make_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()
    train_loader = DataLoader(SicapDataset(dev, True), batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=8, pin_memory=True, persistent_workers=True)
    val_loader = DataLoader(SicapDataset(val, False), batch_size=BATCH_SIZE, shuffle=False,
                            num_workers=8, pin_memory=True, persistent_workers=True)
    best_auc = -np.inf
    best_payload: dict | None = None
    history = []
    started = time.time()
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        seen = 0
        for images, binary, fraction, _ in train_loader:
            images = images.to(device, non_blocking=True)
            binary = binary.to(device, non_blocking=True)
            fraction = fraction.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = bce(logits[:, 0], binary) + 0.5 * mse(torch.sigmoid(logits[:, 1]), fraction)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(images)
            seen += len(images)
        score, fraction_hat, y, _ = predict_loader(model, val_loader, device)
        auc = float(roc_auc_score(y, score))
        threshold, balanced, sensitivity, specificity = choose_threshold(y, score)
        row = {
            "epoch": epoch,
            "train_loss": total_loss / seen,
            "val_auroc": auc,
            "val_fraction_spearman": float(stats.spearmanr(val.tumor_fraction, fraction_hat).statistic),
            "threshold": threshold,
            "balanced_accuracy": balanced,
            "sensitivity": sensitivity,
            "specificity": specificity,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if auc > best_auc:
            best_auc = auc
            best_payload = {
                "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
                "threshold": threshold,
                "epoch": epoch,
                "val_metrics": row,
                "dev_slides": sorted(dev.slide_id.unique().tolist()),
                "val_slides": sorted(val.slide_id.unique().tolist()),
            }
    assert best_payload is not None
    checkpoint = LOCAL / "fm6_sicap_resnet18_tumor_detector.pt"
    torch.save(best_payload, checkpoint)
    pd.DataFrame(history).to_csv(OUTPUTS / "fm6_detector_training_history.csv", index=False, lineterminator="\n")
    config = {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "seed": SEED,
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "optimizer": "AdamW(lr=1e-4, weight_decay=1e-4)",
        "loss": "BCE(binary tumor_fraction>=0.10)+0.5*MSE(sigmoid fraction,tumor_fraction)",
        "pretrained_weights_sha256": sha256_file(WEIGHTS),
        "checkpoint_sha256": sha256_file(checkpoint),
        "best_epoch": best_payload["epoch"],
        "threshold": best_payload["threshold"],
        "elapsed_seconds": time.time() - started,
        "claim_ceiling": "outcome-independent detector development",
    }
    stable_json(OUTPUTS / "fm6_detector_training_run_config.json", config)
    print(json.dumps(config, indent=2), flush=True)


def load_detector(device: torch.device) -> tuple[nn.Module, dict]:
    payload = torch.load(LOCAL / "fm6_sicap_resnet18_tumor_detector.pt", map_location="cpu", weights_only=False)
    model = make_model()
    model.load_state_dict(payload["state_dict"])
    return model.to(device).eval(), payload


def evaluate_sicap() -> None:
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = read_sicap_partition("Test")
    loader = DataLoader(SicapDataset(frame, False), batch_size=BATCH_SIZE, shuffle=False,
                        num_workers=8, pin_memory=True)
    model, payload = load_detector(device)
    score, fraction_hat, y, indices = predict_loader(model, loader, device)
    order = np.argsort(indices)
    frame = frame.iloc[indices[order]].reset_index(drop=True)
    frame["score"] = score[order]
    frame["fraction_hat"] = fraction_hat[order]
    threshold = float(payload["threshold"])
    metrics = binary_metrics(frame.tumor_present.to_numpy(), frame.score.to_numpy(), threshold)
    metrics.update({
        "cohort": "SICAPv2_official_test",
        "threshold": threshold,
        "fraction_spearman": float(stats.spearmanr(frame.tumor_fraction, frame.fraction_hat).statistic),
        "fraction_mae": float(np.abs(frame.tumor_fraction - frame.fraction_hat).mean()),
        "failure_rate": 0.0,
    })
    boot = bootstrap_metrics(frame, threshold)
    intervals = []
    for metric in ["auroc", "sensitivity", "specificity", "balanced_accuracy"]:
        intervals.append({"metric": metric, "estimate": metrics[metric],
                          "ci_low": boot[metric].quantile(0.025), "ci_high": boot[metric].quantile(0.975),
                          "bootstrap_replicates": len(boot)})
    passed = (metrics["auroc"] >= 0.90 and metrics["sensitivity"] >= 0.85 and
              metrics["specificity"] >= 0.80 and metrics["failure_rate"] <= 0.01)
    metrics["gate"] = "PASS_INTERNAL" if passed else "FAIL_INTERNAL"
    pd.DataFrame([metrics]).to_csv(OUTPUTS / "fm6_sicap_detector_test_summary.csv", index=False, lineterminator="\n")
    pd.DataFrame(intervals).to_csv(OUTPUTS / "fm6_sicap_detector_test_intervals.csv", index=False, lineterminator="\n")
    frame.to_csv(LOCAL / "fm6_sicap_detector_test_predictions.csv", index=False, lineterminator="\n")
    stable_json(OUTPUTS / "fm6_sicap_detector_evaluation_run_config.json", {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": sha256_file(LOCAL / "fm6_sicap_resnet18_tumor_detector.pt"),
        "predictions_sha256": sha256_file(LOCAL / "fm6_sicap_detector_test_predictions.csv"),
        "threshold_source": "locked internal validation",
        "gate": metrics["gate"],
    })
    print(json.dumps(metrics, indent=2), flush=True)


def page_mpp(page: tifffile.TiffPage) -> float:
    resolution = page.tags["XResolution"].value
    pixels_per_cm = float(resolution[0]) / float(resolution[1])
    return 10000.0 / pixels_per_cm


def integral_fraction(mask: np.ndarray, centers: np.ndarray, radius: int) -> np.ndarray:
    integral = np.pad(mask.astype(np.int64).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    y, x = centers[:, 0], centers[:, 1]
    y0, y1, x0, x1 = y - radius, y + radius, x - radius, x + radius
    sums = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
    return sums / float((2 * radius) ** 2)


def select_panda_rows() -> pd.DataFrame:
    frame = pd.read_csv(PANDA_CSV)
    with zipfile.ZipFile(PANDA_ZIP) as archive:
        available = {Path(name).stem.replace("_mask", "") for name in archive.namelist()
                     if name.startswith("train_label_masks/")}
    frame = frame[frame.image_id.isin(available)].copy()
    frame["cancer"] = frame.isup_grade.gt(0).astype(int)
    rng = np.random.default_rng(SEED)
    parts = []
    for _, group in frame.groupby(["data_provider", "cancer"], sort=True):
        take = min(PANDA_SLIDES_PER_STRATUM, len(group))
        parts.append(group.iloc[np.sort(rng.choice(len(group), size=take, replace=False))])
    return pd.concat(parts, ignore_index=True).sort_values(["data_provider", "cancer", "image_id"])


def deterministic_inference_transform() -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize((INPUT_SIZE, INPUT_SIZE), interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])


def audit_panda() -> None:
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, payload = load_detector(device)
    transform = deterministic_inference_transform()
    selected = select_panda_rows()
    rng = np.random.default_rng(SEED)
    predictions = []
    sources = []
    with zipfile.ZipFile(PANDA_ZIP) as archive:
        for position, row in selected.iterrows():
            image_path = PANDA_IMAGES / f"{row.image_id}.tiff"
            member = f"train_label_masks/{row.image_id}_mask.tiff"
            info = archive.getinfo(member)
            mask_bytes = archive.read(member)
            with tifffile.TiffFile(image_path) as image_tiff, tifffile.TiffFile(io.BytesIO(mask_bytes)) as mask_tiff:
                level = 1 if len(image_tiff.pages) > 1 else 0
                image = image_tiff.pages[level].asarray()[..., :3]
                raw_mask = mask_tiff.pages[level].asarray()
                if raw_mask.ndim == 3:
                    raw_mask = raw_mask[..., 0]
                mpp = page_mpp(image_tiff.pages[level])
            if row.data_provider == "karolinska":
                tumor = raw_mask == 2
                tissue = raw_mask > 0
            else:
                tumor = raw_mask >= 3
                tissue = raw_mask > 0
            window = max(16, int(round(BOUNDARY_UM / mpp)))
            if window % 2:
                window += 1
            radius = window // 2
            coordinates = np.argwhere(tissue)
            keep = ((coordinates[:, 0] >= radius) & (coordinates[:, 0] < image.shape[0] - radius) &
                    (coordinates[:, 1] >= radius) & (coordinates[:, 1] < image.shape[1] - radius))
            coordinates = coordinates[keep]
            if len(coordinates) > 5000:
                coordinates = coordinates[rng.choice(len(coordinates), 5000, replace=False)]
            fractions = integral_fraction(tumor, coordinates, radius)
            positive = np.flatnonzero(fractions >= TUMOR_FRACTION_CUTOFF)
            negative = np.flatnonzero(fractions < TUMOR_FRACTION_CUTOFF)
            if int(row.cancer):
                pos_take = min(PANDA_PATCHES_PER_SLIDE // 2, len(positive))
                neg_take = min(PANDA_PATCHES_PER_SLIDE - pos_take, len(negative))
            else:
                pos_take = 0
                neg_take = min(PANDA_PATCHES_PER_SLIDE, len(negative))
            chosen = np.r_[rng.choice(positive, pos_take, replace=False) if pos_take else np.array([], int),
                           rng.choice(negative, neg_take, replace=False) if neg_take else np.array([], int)]
            tensors = []
            meta = []
            for candidate in chosen:
                y, x = coordinates[candidate]
                crop = image[y-radius:y+radius, x-radius:x+radius]
                canonical = Image.fromarray(crop).resize((448, 448), Image.Resampling.BICUBIC)
                tensors.append(transform(canonical))
                meta.append((int(y), int(x), float(fractions[candidate])))
            if tensors:
                with torch.inference_mode():
                    score = torch.sigmoid(model(torch.stack(tensors).to(device))[:, 0]).cpu().numpy()
                for patch_index, ((y, x, fraction), value) in enumerate(zip(meta, score)):
                    predictions.append({"image_id": row.image_id, "slide_id": row.image_id,
                                        "provider": row.data_provider, "isup_grade": row.isup_grade,
                                        "patch_index": patch_index, "center_y": y, "center_x": x,
                                        "mpp": mpp, "tumor_fraction": fraction,
                                        "tumor_present": int(fraction >= TUMOR_FRACTION_CUTOFF),
                                        "score": float(value)})
            sources.append({"image_id": row.image_id, "provider": row.data_provider,
                            "image_size": image_path.stat().st_size, "mask_member_size": info.file_size,
                            "mask_member_crc32": f"{info.CRC:08x}", "patches": len(tensors)})
            print(f"PANDA {position + 1}/{len(selected)} {row.data_provider} {row.image_id} patches={len(tensors)}", flush=True)
    pred = pd.DataFrame(predictions)
    pred.to_csv(LOCAL / "fm6_panda_detector_predictions.csv", index=False, lineterminator="\n")
    pd.DataFrame(sources).to_csv(LOCAL / "fm6_panda_selected_source_members.csv", index=False, lineterminator="\n")
    threshold = float(payload["threshold"])
    rows = []
    for provider, group in pred.groupby("provider"):
        metrics = binary_metrics(group.tumor_present.to_numpy(), group.score.to_numpy(), threshold)
        passed = (metrics["n_positive"] >= 50 and metrics["n_negative"] >= 50 and
                  metrics["auroc"] >= 0.80 and metrics["sensitivity"] >= 0.75 and
                  metrics["specificity"] >= 0.70)
        rows.append({"provider": provider, **metrics, "threshold": threshold,
                     "gate": "PASS_EXTERNAL_SCANNER_PROXY" if passed else "FAIL_EXTERNAL_SCANNER_PROXY"})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUTPUTS / "fm6_panda_detector_scanner_proxy_summary.csv", index=False, lineterminator="\n")
    stable_json(OUTPUTS / "fm6_panda_detector_audit_run_config.json", {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "selected_slides": len(selected),
        "predictions_sha256": sha256_file(LOCAL / "fm6_panda_detector_predictions.csv"),
        "selected_members_sha256": sha256_file(LOCAL / "fm6_panda_selected_source_members.csv"),
        "checkpoint_sha256": sha256_file(LOCAL / "fm6_sicap_resnet18_tumor_detector.pt"),
        "provider_is_scanner_proxy": True,
    })
    print(summary.to_string(index=False), flush=True)


def score_tcga() -> None:
    internal = pd.read_csv(OUTPUTS / "fm6_sicap_detector_test_summary.csv")
    external = pd.read_csv(OUTPUTS / "fm6_panda_detector_scanner_proxy_summary.csv")
    if internal.iloc[0].gate != "PASS_INTERNAL" or not external.gate.eq("PASS_EXTERNAL_SCANNER_PROXY").all():
        raise RuntimeError("detector gate not passed; TCGA scoring is prohibited")
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, payload = load_detector(device)
    transform = deterministic_inference_transform()
    manifest = pd.read_csv(TCGA_OUTPUTS / "fm6_tcga_whole_tissue_tile_manifest.csv")
    rows = []
    for slide_number, (file_id, group) in enumerate(manifest.groupby("file_id", sort=False), 1):
        with np.load(TCGA_CROPS / f"{file_id}.npz", allow_pickle=False) as cached:
            crops = cached["crops"]
            tile_ids = cached["tile_id"].astype(str)
        if not np.array_equal(tile_ids, group.tile_id.to_numpy(str)):
            raise RuntimeError(f"TCGA tile mismatch {file_id}")
        scores = []
        with torch.inference_mode():
            for start in range(0, len(crops), BATCH_SIZE):
                batch = torch.stack([transform(Image.fromarray(crop)) for crop in crops[start:start+BATCH_SIZE]])
                scores.extend(torch.sigmoid(model(batch.to(device))[:, 0]).cpu().numpy().tolist())
        for source, score in zip(group.to_dict("records"), scores):
            rows.append({**source, "tumor_score": score})
        if slide_number % 50 == 0:
            print(f"TCGA scored {slide_number}/{manifest.file_id.nunique()} slides", flush=True)
    scored = pd.DataFrame(rows)
    threshold = float(payload["threshold"])
    scored["above_threshold"] = scored.tumor_score.ge(threshold)
    scored["rank_within_slide"] = scored.groupby("file_id").tumor_score.rank(method="first", ascending=False)
    scored["selected"] = scored.above_threshold & scored.rank_within_slide.le(32)
    slide = scored.groupby(["case_id", "file_id"], as_index=False).agg(
        candidate_tiles=("tile_id", "size"), above_threshold=("above_threshold", "sum"),
        selected_tiles=("selected", "sum"), median_score=("tumor_score", "median"), max_score=("tumor_score", "max"))
    slide["evaluable"] = slide.selected_tiles.ge(8)
    patient = slide.groupby("case_id", as_index=False).agg(slides=("file_id", "size"),
        evaluable_slides=("evaluable", "sum"), selected_tiles=("selected_tiles", "sum"))
    patient["evaluable"] = patient.evaluable_slides.gt(0)
    scored.to_csv(LOCAL / "fm6_tcga_tumor_tile_scores.csv", index=False, lineterminator="\n")
    slide.to_csv(LOCAL / "fm6_tcga_detector_slide_audit.csv", index=False, lineterminator="\n")
    patient.to_csv(LOCAL / "fm6_tcga_detector_patient_audit.csv", index=False, lineterminator="\n")
    summary = pd.DataFrame([{
        "candidate_tiles": len(scored), "above_threshold_tiles": int(scored.above_threshold.sum()),
        "selected_tiles": int(scored.selected.sum()), "slides": len(slide),
        "evaluable_slides": int(slide.evaluable.sum()), "slide_failure_rate": float(1-slide.evaluable.mean()),
        "patients": len(patient), "evaluable_patients": int(patient.evaluable.sum()),
        "patient_failure_rate": float(1-patient.evaluable.mean()), "threshold": threshold,
        "gate": "PASS_TCGA_APPLICATION" if patient.evaluable.mean() >= 0.90 else "NARROW_TCGA_APPLICATION",
    }])
    summary.to_csv(OUTPUTS / "fm6_tcga_detector_application_summary.csv", index=False, lineterminator="\n")
    stable_json(OUTPUTS / "fm6_tcga_detector_application_run_config.json", {
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": sha256_file(LOCAL / "fm6_sicap_resnet18_tumor_detector.pt"),
        "tile_scores_sha256": sha256_file(LOCAL / "fm6_tcga_tumor_tile_scores.csv"),
        "selection_rule": "score>=locked validation threshold; top32/slide; >=8 selected/slide",
        "outcome_or_isup_used": False,
    })
    print(summary.to_string(index=False), flush=True)


def report() -> None:
    internal = pd.read_csv(OUTPUTS / "fm6_sicap_detector_test_summary.csv").iloc[0]
    external = pd.read_csv(OUTPUTS / "fm6_panda_detector_scanner_proxy_summary.csv")
    tcga_path = OUTPUTS / "fm6_tcga_detector_application_summary.csv"
    tcga = pd.read_csv(tcga_path).iloc[0] if tcga_path.exists() else None
    combined = (internal.gate == "PASS_INTERNAL" and external.gate.eq("PASS_EXTERNAL_SCANNER_PROXY").all())
    lines = [
        "---",
        "document_id: fm6-tumor-region-detector-audit-report",
        "owner_project: quantitative_foundation_model_validation",
        "document_type: report",
        "status: generated",
        "created: 2026-08-16",
        "canonical_path: projects/quantitative_foundation_model_validation/milestones/fm6_tumor_region_detector_audit/outputs/fm6-tumor-region-detector-audit-report.md",
        "---", "",
        "# FM6 independent tumor-region detector audit", "",
        "## Decision", "",
        f"- Combined detector gate: {'PASS' if combined else 'NARROW_OR_FAIL'}",
        "- Claim ceiling: outcome-independent detector audit and detector-restricted development only.", "",
        "## SICAPv2 official test", "",
        f"- n={int(internal['n'])}; positives={int(internal.n_positive)}; negatives={int(internal.n_negative)}",
        f"- AUROC={internal.auroc:.3f}; sensitivity={internal.sensitivity:.3f}; specificity={internal.specificity:.3f}; balanced accuracy={internal.balanced_accuracy:.3f}",
        f"- Fraction Spearman={internal.fraction_spearman:.3f}; MAE={internal.fraction_mae:.3f}; gate={internal.gate}", "",
        "## PANDA provider/scanner-proxy audit", "",
    ]
    for row in external.itertuples(index=False):
        lines.append(f"- {row.provider}: n={row.n}, AUROC={row.auroc:.3f}, sensitivity={row.sensitivity:.3f}, specificity={row.specificity:.3f}, gate={row.gate}")
    lines.extend(["", "## TCGA application", ""])
    if tcga is None:
        lines.append("- Not run because the detector gate did not authorize TCGA scoring.")
    else:
        lines.append(f"- {int(tcga.selected_tiles):,}/{int(tcga.candidate_tiles):,} candidate tiles selected; {int(tcga.evaluable_patients)}/{int(tcga.patients)} patients evaluable; patient failure rate={tcga.patient_failure_rate:.3f}; gate={tcga.gate}")
    lines.extend(["", "## Interpretation boundary", "",
                  "Passing this audit does not create TCGA pixel truth. Subsequent analyses must be named detector-restricted exploratory R/A/U; strong H2 and external T remain locked.", ""])
    (OUTPUTS / "fm6-tumor-region-detector-audit-report.md").write_text("\n".join(lines))
    pd.DataFrame([{
        "internal_gate": internal.gate,
        "external_gate": "PASS_EXTERNAL_SCANNER_PROXY" if external.gate.eq("PASS_EXTERNAL_SCANNER_PROXY").all() else "FAIL_EXTERNAL_SCANNER_PROXY",
        "combined_gate": "PASS" if combined else "NARROW_OR_FAIL",
        "tcga_application": tcga.gate if tcga is not None else "NOT_RUN",
        "strong_H2": "PROHIBITED",
    }]).to_csv(OUTPUTS / "fm6_tumor_region_detector_evidence_gate.csv", index=False, lineterminator="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "train", "evaluate-sicap", "audit-panda", "score-tcga", "report"])
    args = parser.parse_args()
    globals()[args.stage.replace("-", "_")]()


if __name__ == "__main__":
    main()
