"""Train one locked M5 PLAX video experiment variant."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "scripts"))

from plax_lvef.study_video import GaoCineRegressor, StudyTemporalTeacher  # noqa: E402
from plax_lvef.dicom import decode_dicom  # noqa: E402

KINETICS_MEAN = torch.tensor([0.43216, 0.394666, 0.37645])[:, None, None, None]
KINETICS_STD = torch.tensor([0.22803, 0.22145, 0.216989])[:, None, None, None]
ORDINAL_THRESHOLDS = torch.tensor([30.0, 40.0, 50.0, 60.0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--secure-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument(
        "--variant", choices=("gao", "mil_regression", "mil_multitask", "mil_physiology"), required=True
    )
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--frames", type=int, default=64)
    parser.add_argument("--stride", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=112)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--accumulate", type=int, default=4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--cines-per-study", type=int, default=2)
    parser.add_argument("--train-fraction", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--max-studies", type=int)
    parser.add_argument("--shuffle-evaluation-frames", action="store_true")
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def prepare_cache(args: argparse.Namespace) -> pd.DataFrame:
    args.cache_root.mkdir(parents=True, exist_ok=True)
    index_path = args.cache_root / "restricted_index.csv"
    if index_path.exists():
        cached = pd.read_csv(index_path, dtype={"subject_id": str, "study_id": str, "file_id": str})
        if len(cached) > 0 and cached.path.map(lambda value: Path(value).exists()).all():
            print(f"M5 cache ready cines={len(cached)}", flush=True)
            return cached
    source = pd.read_csv(args.manifest, dtype={"subject_id": str, "study_id": str, "file_id": str})
    records = []
    for number, row in enumerate(source.itertuples(index=False), 1):
        target = args.cache_root / f"{row.file_id}.npz"
        try:
            if not target.exists():
                cine, _ = decode_dicom(Path(row.dicom_path))
                resized = np.stack(
                    [cv2.resize(frame, (args.image_size, args.image_size), interpolation=cv2.INTER_AREA) for frame in cine]
                ).astype(np.uint8)
                np.savez_compressed(target, frames=resized)
            records.append(
                {
                    "subject_id": str(row.subject_id),
                    "study_id": str(row.study_id),
                    "file_id": str(row.file_id),
                    "lvef": float(row.EF_value),
                    "split": str(row.split),
                    "path": str(target),
                }
            )
        except Exception as error:
            print(f"M5 CACHE WARN {number}: {type(error).__name__}: {error}", flush=True)
        if number % 50 == 0 or number == len(source):
            print(f"M5 cache {number}/{len(source)} usable={len(records)}", flush=True)
    cached = pd.DataFrame(records)
    cached.to_csv(index_path, index=False)
    return cached


def sample_clip(
    path: str, frames: int, stride: int, training: bool, shuffle_frames: bool = False
) -> torch.Tensor:
    with np.load(path) as archive:
        cine = archive["frames"]
    span = (frames - 1) * stride + 1
    maximum_start = max(len(cine) - span, 0)
    start = np.random.randint(maximum_start + 1) if training and maximum_start else maximum_start // 2
    indices = np.minimum(start + np.arange(frames) * stride, len(cine) - 1)
    if shuffle_frames:
        indices = np.random.default_rng(1701).permutation(indices)
    clip = torch.from_numpy(cine[indices].copy()).float().div_(255.0)
    if training:
        gain = float(np.random.uniform(0.85, 1.15))
        offset = float(np.random.uniform(-0.05, 0.05))
        noise = torch.randn_like(clip).mul_(float(np.random.uniform(0.0, 0.015)))
        clip = (clip.mul(gain).add(offset).add(noise)).clamp_(0.0, 1.0)
    clip = clip.unsqueeze(0).repeat(3, 1, 1, 1)
    return (clip - KINETICS_MEAN) / KINETICS_STD


class CineDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, args: argparse.Namespace, training: bool):
        self.frame = frame.reset_index(drop=True)
        self.args = args
        self.training = training

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str]:
        row = self.frame.iloc[index]
        return {
            "clip": sample_clip(row.path, self.args.frames, self.args.stride, self.training),
            "lvef": torch.tensor(float(row.lvef), dtype=torch.float32),
            "study_id": str(row.study_id),
        }


class StudyDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, args: argparse.Namespace, training: bool):
        self.groups = [(study, part.reset_index(drop=True)) for study, part in frame.groupby("study_id", sort=True)]
        self.args = args
        self.training = training

    def __len__(self) -> int:
        return len(self.groups)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str]:
        study_id, part = self.groups[index]
        if self.training:
            chosen = np.random.choice(len(part), self.args.cines_per_study, replace=len(part) < self.args.cines_per_study)
            part = part.iloc[chosen]
        clips = torch.stack(
            [sample_clip(row.path, self.args.frames, self.args.stride, self.training) for row in part.itertuples()]
        )
        ratio = float(part.manual_ratio.iloc[0]) if "manual_ratio" in part and pd.notna(part.manual_ratio.iloc[0]) else np.nan
        return {
            "clips": clips,
            "lvef": torch.tensor(float(part.lvef.iloc[0]), dtype=torch.float32),
            "manual_ratio": torch.tensor(ratio, dtype=torch.float32),
            "study_id": str(study_id),
        }


def add_manual_ratio(frame: pd.DataFrame, manifest: Path) -> pd.DataFrame:
    measurement_path = manifest.parents[1] / "restricted_structured_measurements.csv"
    if not measurement_path.exists():
        frame["manual_ratio"] = np.nan
        return frame
    measured = pd.read_csv(measurement_path, dtype={"study_id": str})
    measured["manual_ratio"] = pd.to_numeric(measured.lvesd, errors="coerce") / pd.to_numeric(
        measured.lvedd, errors="coerce"
    )
    measured = measured.loc[measured.plausible_lvid_pair.astype(str).str.lower().eq("true"), ["study_id", "manual_ratio"]]
    return frame.merge(measured.drop_duplicates("study_id"), on="study_id", how="left")


def subset_training(frame: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    train = frame.loc[frame.split.eq("train")].copy()
    studies = train[["subject_id", "study_id", "lvef"]].drop_duplicates("study_id")
    if args.max_studies:
        studies = studies.sample(min(args.max_studies, len(studies)), random_state=args.seed)
    elif args.train_fraction < 1.0:
        bins = pd.cut(studies.lvef, [-np.inf, 30, 40, 50, 60, np.inf], labels=False)
        studies = studies.groupby(bins, group_keys=False).sample(frac=args.train_fraction, random_state=args.seed)
    return train.loc[train.study_id.isin(studies.study_id)]


def choose_threshold(reference: np.ndarray, probability: np.ndarray) -> float:
    target = reference <= 40.0
    candidates = np.unique(np.r_[0.0, probability, 1.0])
    scores = [f1_score(target, probability >= value, zero_division=0) for value in candidates]
    return float(candidates[int(np.argmax(scores))])


def concordance(reference: np.ndarray, prediction: np.ndarray) -> float:
    covariance = np.mean((reference - reference.mean()) * (prediction - prediction.mean()))
    denominator = reference.var() + prediction.var() + (reference.mean() - prediction.mean()) ** 2
    return float(2.0 * covariance / max(denominator, 1e-8))


def metrics(frame: pd.DataFrame, threshold: float) -> dict[str, float | int]:
    reference = frame.reference_lvef.to_numpy(float)
    prediction = frame.predicted_lvef.to_numpy(float)
    probability = frame.low_probability.to_numpy(float)
    target = reference <= 40.0
    label = probability >= threshold
    error = prediction - reference
    tp, tn = int((target & label).sum()), int((~target & ~label).sum())
    fp, fn = int((~target & label).sum()), int((target & ~label).sum())
    precision = tp / max(tp + fp, 1)
    sensitivity = tp / max(tp + fn, 1)
    return {
        "studies": int(len(frame)),
        "low_ef_n": int(target.sum()),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(np.mean(error)),
        "pearson": float(np.corrcoef(reference, prediction)[0, 1]),
        "ccc": concordance(reference, prediction),
        "low_ef_mae": float(np.mean(np.abs(error[target]))),
        "auroc": float(roc_auc_score(target, probability)),
        "auprc": float(average_precision_score(target, probability)),
        "sensitivity": sensitivity,
        "specificity": tn / max(tn + fp, 1),
        "precision": precision,
        "npv": tn / max(tn + fn, 1),
        "f1": 2 * precision * sensitivity / max(precision + sensitivity, 1e-8),
        "threshold": threshold,
    }


@torch.inference_mode()
def predict_gao(model, loader, device) -> pd.DataFrame:
    model.eval()
    rows = []
    for batch in loader:
        prediction = model(batch["clip"].to(device, non_blocking=True)).cpu().numpy()
        for study, reference, value in zip(batch["study_id"], batch["lvef"].numpy(), prediction):
            rows.append((study, float(reference), float(value)))
    cine = pd.DataFrame(rows, columns=("study_id", "reference_lvef", "predicted_lvef"))
    study = cine.groupby("study_id", as_index=False).agg(
        reference_lvef=("reference_lvef", "first"), predicted_lvef=("predicted_lvef", "mean")
    )
    study["low_probability"] = torch.sigmoid(torch.tensor((40.0 - study.predicted_lvef.to_numpy()) / 5.0)).numpy()
    return study


@torch.inference_mode()
def predict_study(model, dataset: StudyDataset, device, shuffle_frames: bool = False) -> pd.DataFrame:
    model.eval()
    rows = []
    for number in range(len(dataset)):
        study_id, part = dataset.groups[number]
        clips = torch.stack(
            [
                sample_clip(row.path, dataset.args.frames, dataset.args.stride, False, shuffle_frames)
                for row in part.itertuples()
            ]
        ).to(device)
        output = model.predict_chunked(clips, chunk_size=dataset.args.cines_per_study)
        rows.append(
            {
                "study_id": study_id,
                "reference_lvef": float(part.lvef.iloc[0]),
                "predicted_lvef": float(output["lvef"].cpu()),
                "low_probability": float(output["low_ef_logit"].sigmoid().cpu()),
                "cine_n": len(part),
                "cine_attention_max": float(output["cine_attention"].max().cpu()),
            }
        )
    return pd.DataFrame(rows)


def train_gao(args, frame, device):
    train = subset_training(frame, args)
    parts = {split: frame.loc[frame.split.eq(split)] for split in ("validation", "test")}
    studies = train.drop_duplicates("study_id")
    counts = train.groupby("study_id").size().to_dict()
    weights = [(3.0 if row.lvef <= 40 else 1.0) / counts[row.study_id] for row in train.itertuples()]
    sampler = WeightedRandomSampler(weights, len(train), replacement=True)
    loaders = {
        "train": DataLoader(CineDataset(train, args, True), batch_size=args.batch_size, sampler=sampler, num_workers=args.workers, pin_memory=True),
        **{
            split: DataLoader(CineDataset(part, args, False), batch_size=args.batch_size, shuffle=False, num_workers=args.workers, pin_memory=True)
            for split, part in parts.items()
        },
    }
    model = GaoCineRegressor(pretrained=True).to(device)
    optimizer = torch.optim.RAdam(model.parameters(), lr=1e-3)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.1)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best, stale, history = None, 0, []
    for epoch in range(1, args.epochs + 1):
        model.train(); optimizer.zero_grad(set_to_none=True); losses = []
        for step, batch in enumerate(loaders["train"], 1):
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                prediction = model(batch["clip"].to(device, non_blocking=True))
                loss = F.mse_loss(prediction, batch["lvef"].to(device)) / args.accumulate
            scaler.scale(loss).backward()
            if step % args.accumulate == 0 or step == len(loaders["train"]):
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
            losses.append(float(loss.detach()) * args.accumulate)
        validation = predict_gao(model, loaders["validation"], device)
        threshold = choose_threshold(validation.reference_lvef.to_numpy(), validation.low_probability.to_numpy())
        result = metrics(validation, threshold)
        scheduler.step(result["mae"])
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), "validation": result})
        print(f"M5-A epoch={epoch:02d} loss={np.mean(losses):.3f} val_mae={result['mae']:.3f} low_mae={result['low_ef_mae']:.3f} auroc={result['auroc']:.3f}", flush=True)
        if best is None or result["mae"] < best[0]:
            best = (result["mae"], epoch, threshold); stale = 0
            torch.save({"model": model.state_dict(), "epoch": epoch}, args.secure_output / "best.pt")
        else:
            stale += 1
        if stale >= args.patience:
            break
    checkpoint = torch.load(args.secure_output / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model"])
    validation = predict_gao(model, loaders["validation"], device)
    threshold = choose_threshold(validation.reference_lvef.to_numpy(), validation.low_probability.to_numpy())
    test = predict_gao(model, loaders["test"], device)
    return model, history, metrics(validation, threshold), metrics(test, threshold), validation, test


def train_study(args, frame, device):
    train = subset_training(frame, args)
    datasets = {
        "train": StudyDataset(train, args, True),
        "validation": StudyDataset(frame.loc[frame.split.eq("validation")], args, False),
        "test": StudyDataset(frame.loc[frame.split.eq("test")], args, False),
    }
    train_studies = train.drop_duplicates("study_id")
    target = train_studies.lvef.to_numpy(float)
    bins = np.digitize(target, [30, 40, 50, 60])
    counts = np.bincount(bins, minlength=5)
    bin_weights = np.clip(len(target) / (5 * np.maximum(counts, 1)), 0.5, 3.0)
    low_pos_weight = min(float(np.sum(target > 40) / max(np.sum(target <= 40), 1)), 3.0)
    loader = DataLoader(datasets["train"], batch_size=1, shuffle=True, num_workers=0, pin_memory=True)
    physiology = args.variant == "mil_physiology"
    model = StudyTemporalTeacher(pretrained=True, physiology_head=physiology).to(device)
    optimizer = torch.optim.AdamW(
        [
            {"params": model.encoder.parameters(), "lr": 1e-4},
            {"params": [p for name, p in model.named_parameters() if not name.startswith("encoder.")], "lr": 5e-4},
        ], weight_decay=1e-4
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    best, stale, history = None, 0, []
    for epoch in range(1, args.epochs + 1):
        model.train(); optimizer.zero_grad(set_to_none=True); losses = []
        for step, batch in enumerate(loader, 1):
            clips = batch["clips"].to(device, non_blocking=True)
            reference = batch["lvef"].to(device)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                output = model(clips)
                sample_bins = torch.bucketize(reference, ORDINAL_THRESHOLDS.to(device))
                sample_weight = torch.as_tensor(bin_weights, device=device)[sample_bins]
                regression = F.smooth_l1_loss(output["lvef"], reference, beta=5.0, reduction="none")
                loss = (regression * sample_weight).mean()
                if args.variant != "mil_regression":
                    low_target = reference.le(40).float()
                    low = F.binary_cross_entropy_with_logits(
                        output["low_ef_logit"], low_target,
                        pos_weight=torch.tensor(low_pos_weight, device=device),
                    )
                    ordinal_target = reference[:, None].le(ORDINAL_THRESHOLDS.to(device)).float()
                    ordinal = F.binary_cross_entropy_with_logits(output["ordinal_logits"], ordinal_target)
                    loss = loss + 0.25 * low + 0.15 * ordinal
                if physiology:
                    ratio = batch["manual_ratio"].to(device)
                    available = torch.isfinite(ratio)
                    if available.any():
                        loss = loss + 0.20 * F.smooth_l1_loss(output["lvid_ratio"][available], ratio[available], beta=0.05)
                loss = loss / args.accumulate
            scaler.scale(loss).backward()
            if step % args.accumulate == 0 or step == len(loader):
                scaler.unscale_(optimizer); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
            losses.append(float(loss.detach()) * args.accumulate)
        scheduler.step()
        validation = predict_study(model, datasets["validation"], device)
        if args.variant == "mil_regression":
            validation["low_probability"] = torch.sigmoid(torch.tensor((40.0 - validation.predicted_lvef.to_numpy()) / 5.0)).numpy()
        threshold = choose_threshold(validation.reference_lvef.to_numpy(), validation.low_probability.to_numpy())
        result = metrics(validation, threshold)
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), "validation": result})
        print(f"M5-B/{args.variant} epoch={epoch:02d} loss={np.mean(losses):.3f} val_mae={result['mae']:.3f} low_mae={result['low_ef_mae']:.3f} auroc={result['auroc']:.3f} sensitivity={result['sensitivity']:.3f}", flush=True)
        score = result["mae"]
        if best is None or score < best[0]:
            best = (score, epoch, threshold); stale = 0
            torch.save({"model": model.state_dict(), "epoch": epoch}, args.secure_output / "best.pt")
        else:
            stale += 1
        if stale >= args.patience:
            break
    checkpoint = torch.load(args.secure_output / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model"])
    validation = predict_study(model, datasets["validation"], device)
    test = predict_study(model, datasets["test"], device)
    if args.variant == "mil_regression":
        for predictions in (validation, test):
            predictions["low_probability"] = torch.sigmoid(torch.tensor((40.0 - predictions.predicted_lvef.to_numpy()) / 5.0)).numpy()
    threshold = choose_threshold(validation.reference_lvef.to_numpy(), validation.low_probability.to_numpy())
    shuffled = predict_study(model, datasets["test"], device, shuffle_frames=True)
    if args.variant == "mil_regression":
        shuffled["low_probability"] = torch.sigmoid(torch.tensor((40.0 - shuffled.predicted_lvef.to_numpy()) / 5.0)).numpy()
    return model, history, metrics(validation, threshold), metrics(test, threshold), validation, test, metrics(shuffled, threshold)


def main() -> None:
    args = parse_args(); seed_everything(args.seed)
    args.secure_output.mkdir(parents=True, exist_ok=True)
    args.summary_output.mkdir(parents=True, exist_ok=True)
    frame = prepare_cache(args)
    frame = add_manual_ratio(frame, args.manifest)
    overlaps = []
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        overlaps.append(set(frame.loc[frame.split.eq(left), "subject_id"]) & set(frame.loc[frame.split.eq(right), "subject_id"]))
    if any(overlaps):
        raise ValueError("Patient leakage in M5 manifest")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"M5 variant={args.variant} device={device} cines={len(frame)} studies={frame.study_id.nunique()}", flush=True)
    if args.variant == "gao":
        model, history, validation, test, validation_predictions, predictions = train_gao(args, frame, device)
        shuffled = None
    else:
        model, history, validation, test, validation_predictions, predictions, shuffled = train_study(args, frame, device)
    validation_predictions.to_csv(args.secure_output / "restricted_validation_predictions.csv", index=False)
    predictions.to_csv(args.secure_output / "restricted_test_predictions.csv", index=False)
    summary = {
        "status": "complete",
        "variant": args.variant,
        "evidence": "patient-disjoint MIMIC development split with report-linked weak LVEF",
        "seed": args.seed,
        "train_fraction": args.train_fraction,
        "epochs_completed": len(history),
        "best_epoch": int(np.argmin([row["validation"]["mae"] for row in history]) + 1),
        "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
        "validation": validation,
        "test": test,
        "temporal_shuffle_test": shuffled,
    }
    (args.secure_output / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (args.summary_output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"M5 {args.variant} COMPLETE", flush=True)


if __name__ == "__main__":
    main()
