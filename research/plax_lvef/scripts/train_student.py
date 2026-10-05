"""Distil the frozen M5-A ensemble into the locked edge video Student."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "scripts"))

from plax_lvef.model import EdgeLvefModel  # noqa: E402
from plax_lvef.study_video import GaoCineRegressor  # noqa: E402
from train_teacher import (  # noqa: E402
    KINETICS_MEAN,
    KINETICS_STD,
    choose_threshold,
    metrics,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-index", type=Path, required=True)
    parser.add_argument("--teacher-checkpoint", type=Path, action="append", required=True)
    parser.add_argument("--teacher-cache", type=Path, required=True)
    parser.add_argument("--secure-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--frames", type=int, default=32)
    parser.add_argument("--teacher-frames", type=int, default=64)
    parser.add_argument("--teacher-stride", type=int, default=2)
    parser.add_argument("--image-size", type=int, default=112)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument(
        "--backbone",
        choices=(
            "mobilenet_v2",
            "mobilenet_v3_small",
            "mobilenet_v3_large",
            "shufflenet_v2_x1_0",
            "efficientnet_b0",
            "resnet18",
        ),
        default="mobilenet_v3_small",
    )
    parser.add_argument("--boundary-recovery", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def teacher_clip(path: str, frames: int, stride: int) -> torch.Tensor:
    with np.load(path) as archive:
        cine = archive["frames"]
    span = (frames - 1) * stride + 1
    start = max(len(cine) - span, 0) // 2
    indices = np.minimum(start + np.arange(frames) * stride, len(cine) - 1)
    clip = torch.from_numpy(cine[indices].copy()).float().div_(255.0)
    clip = clip.unsqueeze(0).repeat(3, 1, 1, 1)
    return (clip - KINETICS_MEAN) / KINETICS_STD


class TeacherExtractionDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, args: argparse.Namespace):
        self.frame = frame.reset_index(drop=True)
        self.args = args

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        return teacher_clip(
            self.frame.iloc[index].path,
            self.args.teacher_frames,
            self.args.teacher_stride,
        )


@torch.inference_mode()
def load_or_extract_teacher_targets(
    frame: pd.DataFrame, args: argparse.Namespace, device: torch.device
) -> tuple[np.ndarray, np.ndarray]:
    if args.teacher_cache.exists():
        with np.load(args.teacher_cache) as archive:
            prediction = archive["prediction"]
            embedding = archive["embedding"]
        if len(prediction) != len(frame):
            raise ValueError("Teacher cache length does not match the cache index")
        print(f"M5-E teacher cache ready cines={len(frame)}", flush=True)
        return prediction, embedding

    loader = DataLoader(
        TeacherExtractionDataset(frame, args),
        batch_size=max(args.batch_size // 2, 1),
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
    )
    seed_predictions, seed_embeddings = [], []
    for checkpoint_path in args.teacher_checkpoint:
        model = GaoCineRegressor(pretrained=False).to(device)
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
        model.load_state_dict(checkpoint["model"])
        model.eval()
        predictions, embeddings = [], []
        for number, clips in enumerate(loader, 1):
            clips = clips.to(device, non_blocking=True)
            feature = model.encoder(clips).mean(dim=(2, 3, 4))
            predictions.append(model.head(feature).squeeze(1).cpu().numpy())
            embeddings.append(feature.cpu().numpy())
            if number % 25 == 0 or number == len(loader):
                print(
                    f"M5-E teacher extraction checkpoint={checkpoint_path.parent.name} "
                    f"batch={number}/{len(loader)}",
                    flush=True,
                )
        seed_predictions.append(np.concatenate(predictions))
        seed_embeddings.append(np.concatenate(embeddings))
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    prediction = np.mean(seed_predictions, axis=0).astype(np.float32)
    embedding = np.mean(seed_embeddings, axis=0).astype(np.float32)
    args.teacher_cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.teacher_cache, prediction=prediction, embedding=embedding)
    print(f"M5-E teacher targets saved cines={len(frame)}", flush=True)
    return prediction, embedding


class StudentDataset(Dataset):
    def __init__(
        self,
        frame: pd.DataFrame,
        teacher_prediction: np.ndarray,
        teacher_embedding: np.ndarray,
        frames: int,
        training: bool,
    ):
        self.frame = frame.reset_index(drop=True)
        self.teacher_prediction = teacher_prediction
        self.teacher_embedding = teacher_embedding
        self.frames = frames
        self.training = training

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int):
        row = self.frame.iloc[index]
        with np.load(row.path) as archive:
            cine = archive["frames"]
        indices = np.rint(np.linspace(0, len(cine) - 1, self.frames)).astype(np.int64)
        images = torch.from_numpy(cine[indices].copy()).float().unsqueeze(1).div_(255.0)
        if self.training:
            gain = float(np.random.uniform(0.9, 1.1))
            offset = float(np.random.uniform(-0.04, 0.04))
            noise = torch.randn_like(images).mul_(float(np.random.uniform(0.0, 0.01)))
            images = images.mul(gain).add(offset).add(noise).clamp_(0.0, 1.0)
        teacher_lvef = float(self.teacher_prediction[index])
        return {
            "frames": images,
            "lvef": torch.tensor(float(row.lvef), dtype=torch.float32),
            "teacher_lvef": torch.tensor(teacher_lvef, dtype=torch.float32),
            "teacher_probability": torch.tensor(
                1.0 / (1.0 + np.exp(-(40.0 - teacher_lvef) / 5.0)),
                dtype=torch.float32,
            ),
            "teacher_embedding": torch.from_numpy(self.teacher_embedding[index]).float(),
            "study_id": str(row.study_id),
        }


def make_dataset(
    full_frame: pd.DataFrame,
    full_prediction: np.ndarray,
    full_embedding: np.ndarray,
    split: str,
    frames: int,
    training: bool,
) -> StudentDataset:
    selected = np.flatnonzero(full_frame.split.to_numpy() == split)
    return StudentDataset(
        full_frame.iloc[selected],
        full_prediction[selected],
        full_embedding[selected],
        frames,
        training,
    )


@torch.inference_mode()
def predict_student(model, loader, device) -> pd.DataFrame:
    model.eval()
    rows = []
    for batch in loader:
        predicted_lvef, _, low_logit = model(batch["frames"].to(device, non_blocking=True))
        rows.extend(
            (study, float(reference), float(value), float(probability))
            for study, reference, value, probability in zip(
                batch["study_id"],
                batch["lvef"],
                predicted_lvef.cpu(),
                low_logit.sigmoid().cpu(),
            )
        )
    cine = pd.DataFrame(
        rows,
        columns=("study_id", "reference_lvef", "predicted_lvef", "low_probability"),
    )
    return cine.groupby("study_id", as_index=False).agg(
        reference_lvef=("reference_lvef", "first"),
        predicted_lvef=("predicted_lvef", "mean"),
        low_probability=("low_probability", "mean"),
    )


def literal_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    target = frame.reference_lvef.to_numpy(float) <= 40.0
    label = frame.predicted_lvef.to_numpy(float) <= 40.0
    tp = int((target & label).sum())
    tn = int((~target & ~label).sum())
    fp = int((~target & label).sum())
    fn = int((target & ~label).sum())
    precision = tp / max(tp + fp, 1)
    sensitivity = tp / max(tp + fn, 1)
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": (tp + tn) / max(tp + tn + fp + fn, 1),
        "precision": precision,
        "sensitivity": sensitivity,
        "specificity": tn / max(tn + fp, 1),
        "f1": 2 * precision * sensitivity / max(precision + sensitivity, 1e-8),
    }


def lvef_error_metrics(frame: pd.DataFrame) -> dict[str, float]:
    """Report percentage-point error separately from relative percent error."""
    reference = frame.reference_lvef.to_numpy(float)
    prediction = frame.predicted_lvef.to_numpy(float)
    error = prediction - reference
    absolute = np.abs(error)
    return {
        "mae_percentage_points": float(absolute.mean()),
        "median_absolute_error_percentage_points": float(np.median(absolute)),
        "mape_percent": float(np.mean(absolute / np.maximum(np.abs(reference), 1e-6)) * 100.0),
        "within_5_percentage_points_rate": float(np.mean(absolute <= 5.0)),
        "within_10_percentage_points_rate": float(np.mean(absolute <= 10.0)),
        "bias_percentage_points": float(error.mean()),
        "bland_altman_lower_95": float(error.mean() - 1.96 * error.std(ddof=1)),
        "bland_altman_upper_95": float(error.mean() + 1.96 * error.std(ddof=1)),
    }


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    args.secure_output.mkdir(parents=True, exist_ok=True)
    args.summary_output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(args.cache_index, dtype={"subject_id": str, "study_id": str, "file_id": str})
    if args.smoke:
        kept = []
        for split in ("train", "validation", "test"):
            kept.extend(frame.index[frame.split.eq(split)][:16].tolist())
        frame = frame.loc[kept].reset_index(drop=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    teacher_prediction, teacher_embedding = load_or_extract_teacher_targets(frame, args, device)
    datasets = {
        split: make_dataset(
            frame,
            teacher_prediction,
            teacher_embedding,
            split,
            args.frames,
            split == "train",
        )
        for split in ("train", "validation", "test")
    }
    train_frame = datasets["train"].frame
    counts = train_frame.groupby("study_id").size().to_dict()
    if args.boundary_recovery:
        study_targets = train_frame.drop_duplicates("study_id").lvef.to_numpy(float)
        study_bins = np.digitize(study_targets, [30.0, 40.0, 50.0, 60.0])
        bin_counts = np.bincount(study_bins, minlength=5)
        bin_weights = np.clip(len(study_targets) / (5 * np.maximum(bin_counts, 1)), 0.5, 3.0)
        weights = [
            float(bin_weights[np.digitize(float(row.lvef), [30.0, 40.0, 50.0, 60.0])])
            / counts[str(row.study_id)]
            for row in train_frame.itertuples()
        ]
    else:
        weights = [
            (3.0 if row.lvef <= 40.0 else 1.0) / counts[str(row.study_id)]
            for row in train_frame.itertuples()
        ]
    sampler = WeightedRandomSampler(weights, len(train_frame), replacement=True)
    loaders = {
        "train": DataLoader(
            datasets["train"],
            batch_size=args.batch_size,
            sampler=sampler,
            num_workers=args.workers,
            pin_memory=True,
        ),
        **{
            split: DataLoader(
                datasets[split],
                batch_size=args.batch_size,
                shuffle=False,
                num_workers=args.workers,
                pin_memory=True,
            )
            for split in ("validation", "test")
        },
    }
    labels = train_frame.lvef.to_numpy(float)
    model = EdgeLvefModel(
        variant=args.backbone,
        pretrained=True,
        label_mean=float(labels.mean()),
        label_std=float(labels.std()),
        temporal_model="tsm",
    ).to(device)
    projector = nn.Linear(model.temporal_dim, teacher_embedding.shape[1]).to(device)
    ordinal_head = nn.Linear(model.temporal_dim, 4).to(device) if args.boundary_recovery else None
    optimized_parameters = list(model.parameters()) + list(projector.parameters())
    if ordinal_head is not None:
        optimized_parameters += list(ordinal_head.parameters())
    optimizer = torch.optim.AdamW(
        optimized_parameters,
        lr=3e-4,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    # A conservative initial scale avoids skipped first updates from the
    # ImageNet-initialised encoder and the untrained feature projector.
    scaler = torch.amp.GradScaler(
        "cuda", enabled=device.type == "cuda", init_scale=1024.0
    )
    best, stale, history = None, 0, []
    study_labels = train_frame.drop_duplicates("study_id").lvef.to_numpy(float)
    positive_weight = min(float(np.sum(study_labels > 40.0) / max(np.sum(study_labels <= 40.0), 1)), 3.0)
    ordinal_thresholds = torch.tensor([30.0, 40.0, 50.0, 60.0], device=device)
    for epoch in range(1, args.epochs + 1):
        model.train(); projector.train(); losses = []
        if ordinal_head is not None:
            ordinal_head.train()
        for batch in loaders["train"]:
            images = batch["frames"].to(device, non_blocking=True)
            report = batch["lvef"].to(device)
            teacher_lvef = batch["teacher_lvef"].to(device)
            teacher_probability = batch["teacher_probability"].to(device)
            teacher_feature = F.normalize(batch["teacher_embedding"].to(device), dim=1)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                predicted, _, low_logit, student_feature = model(images, return_embedding=True)
                loss = F.huber_loss(predicted, report, delta=5.0)
                loss = loss + 0.50 * F.huber_loss(predicted, teacher_lvef, delta=5.0)
                loss = loss + 0.20 * F.binary_cross_entropy_with_logits(
                    low_logit, teacher_probability
                )
                projected = F.normalize(projector(student_feature).float(), dim=1)
                loss = loss + 0.10 * (1.0 - (projected * teacher_feature).sum(dim=1)).mean()
                if args.boundary_recovery:
                    low_target = report.le(40.0).float()
                    loss = loss + 0.25 * F.binary_cross_entropy_with_logits(
                        low_logit,
                        low_target,
                        pos_weight=report.new_tensor(positive_weight),
                    )
                    ordinal_target = report[:, None].le(ordinal_thresholds).float()
                    loss = loss + 0.15 * F.binary_cross_entropy_with_logits(
                        ordinal_head(student_feature), ordinal_target
                    )
                    numerical_low_logit = (40.0 - predicted) / 5.0
                    loss = loss + 0.20 * F.binary_cross_entropy_with_logits(
                        numerical_low_logit, low_target
                    )
                    difference = report[:, None] - report[None, :]
                    predicted_difference = predicted[:, None] - predicted[None, :]
                    pairs = torch.triu(difference.abs() >= 5.0, diagonal=1)
                    if pairs.any():
                        direction = difference[pairs].sign()
                        loss = loss + 0.10 * F.softplus(
                            -direction * predicted_difference[pairs] / 5.0
                        ).mean()
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer); scaler.update()
            losses.append(float(loss.detach()))
        scheduler.step()
        validation = predict_student(model, loaders["validation"], device)
        threshold = choose_threshold(
            validation.reference_lvef.to_numpy(float),
            validation.low_probability.to_numpy(float),
        )
        result = metrics(validation, threshold)
        validation_literal = literal_metrics(validation)
        history.append({
            "epoch": epoch,
            "loss": float(np.mean(losses)),
            "validation": result,
            "validation_literal": validation_literal,
        })
        print(
            f"M5-E epoch={epoch:02d} loss={np.mean(losses):.3f} "
            f"val_mae={result['mae']:.3f} low_mae={result['low_ef_mae']:.3f} "
            f"auroc={result['auroc']:.3f} sensitivity={result['sensitivity']:.3f}",
            flush=True,
        )
        boundary_eligible = validation_literal["sensitivity"] >= 0.70
        score = (
            (0 if boundary_eligible else 1, result["mae"])
            if args.boundary_recovery
            else (0, result["mae"])
        )
        if best is None or score < best[0]:
            best = (score, epoch, threshold); stale = 0
            torch.save(
                {
                    "model": model.state_dict(),
                    "projector": projector.state_dict(),
                    "ordinal_head": ordinal_head.state_dict() if ordinal_head is not None else None,
                    "epoch": epoch,
                },
                args.secure_output / "best.pt",
            )
        else:
            stale += 1
        if stale >= args.patience:
            break

    checkpoint = torch.load(args.secure_output / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model"])
    validation = predict_student(model, loaders["validation"], device)
    threshold = choose_threshold(
        validation.reference_lvef.to_numpy(float), validation.low_probability.to_numpy(float)
    )
    test = predict_student(model, loaders["test"], device)
    test.to_csv(args.secure_output / "restricted_test_predictions.csv", index=False)
    test_metrics = metrics(test, threshold)
    literal = literal_metrics(test)
    error_metrics = lvef_error_metrics(test)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    if ordinal_head is not None:
        parameter_count += sum(parameter.numel() for parameter in ordinal_head.parameters())
    gates = {
        "mae_le_7_1346": test_metrics["mae"] <= 7.1346,
        "auroc_ge_0_9432": test_metrics["auroc"] >= 0.9432,
        "literal_sensitivity_ge_0_70": literal["sensitivity"] >= 0.70,
        "screening_f1_ge_0_80": test_metrics["f1"] >= 0.80,
        "parameters_lt_5m": parameter_count < 5_000_000,
    }
    summary = {
        "status": "complete",
        "evidence": "single patient-disjoint MIMIC development split with report-linked weak LVEF",
        "student": (
            f"{args.backbone}_tsm_boundary_recovery"
            if args.boundary_recovery
            else f"{args.backbone}_tsm"
        ),
        "epochs_completed": len(history),
        "best_epoch": int(checkpoint["epoch"]),
        "parameter_count": int(parameter_count),
        "validation_selected_threshold": threshold,
        "test": test_metrics,
        "literal_lvef_le40": literal,
        "lvef_error": error_metrics,
        "locked_gates": gates,
        "passes_float_promotion": all(gates.values()),
    }
    (args.secure_output / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (args.summary_output / "student_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    print("M5-E EDGE STUDENT COMPLETE", flush=True)


if __name__ == "__main__":
    main()
