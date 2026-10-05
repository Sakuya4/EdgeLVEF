"""Locked M10 frozen-appearance / anatomy-anchored motion-map pilot."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from plax_lvef.model import EdgeLvefModel
from plax_lvef.motion_maps import cycle_window, sample_motion_map, median_anchor, MotionFusion
from motion_locator import build_teacher, soft_coordinates
from train_student import seed_everything, literal_metrics, lvef_error_metrics
from train_teacher import metrics, choose_threshold

VARIANTS = ("control", "cycle_only", "fixed_motion", "anatomy_motion", "anatomy_cycle")


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


def check_splits(frame):
    if frame.groupby("subject_id").split.nunique().max() != 1:
        raise ValueError("Patient crosses split boundary")
    if frame.groupby("study_id").lvef.nunique().max() != 1:
        raise ValueError("Inconsistent study labels")


@torch.inference_mode()
def extract(args, frame, device):
    folder = args.secure_output / "cache"
    folder.mkdir(parents=True, exist_ok=True)
    signature = {"index": digest(args.cache_index), "base": digest(args.baseline_checkpoint),
                 "locator": digest(args.locator_checkpoint), "version": 1,
                 "rows": len(frame), "smoke": args.smoke}
    marker = folder / "signature.json"
    if marker.exists() and json.loads(marker.read_text()) != signature:
        raise ValueError("Cache signature changed; do not reuse this output directory")
    write_json(marker, signature)
    base = EdgeLvefModel(variant="mobilenet_v3_large", pretrained=False, temporal_model="tsm").to(device)
    base.load_state_dict(torch.load(args.baseline_checkpoint, map_location=device, weights_only=True)["model"])
    base.eval()
    locator = build_teacher(args.locator_checkpoint).to(device).eval()
    counts = {"appearance_parameters": sum(p.numel() for p in base.parameters()),
              "locator_parameters": sum(p.numel() for p in locator.parameters())}
    mean = torch.tensor([0.485, 0.456, 0.406], device=device)[None, :, None, None]
    std = torch.tensor([0.229, 0.224, 0.225], device=device)[None, :, None, None]
    diagnostics = []
    for i, row in enumerate(frame.itertuples()):
        target = folder / f"{i:06d}.npz"
        if not target.exists():
            with np.load(row.path) as archive:
                cine = archive["frames"]
            if cine.ndim != 3 or cine.shape[1:] != (112, 112):
                raise ValueError("Unexpected cine dimensions")
            indices = np.rint(np.linspace(0, len(cine) - 1, 64)).astype(int)
            points = []
            for start in range(0, 64, 8):
                windows = np.stack([np.stack([cv2.resize(cine[np.clip(t + offset, 0, len(cine)-1)],
                                                                       (256, 256))
                                                      for offset in (-1, 0, 1)])
                                    for t in indices[start:start+8]])
                images = torch.from_numpy(windows).to(device).float() / 255
                logits = locator((images - mean) / std)
                # Average the two trained phase-specific diameter endpoint heads.
                xy = soft_coordinates(logits)[:, [2, 3, 4, 5]].reshape(-1, 2, 2, 2).mean(dim=1)
                points.append(xy.cpu().numpy() * (112 / 256))
            points = np.concatenate(points)
            lengths = np.linalg.norm(points[:, 1] - points[:, 0], axis=1)
            valid = (lengths >= 8) & (lengths <= 70) & np.isfinite(points).all(axis=(1, 2))
            valid &= (points >= 8).all(axis=(1, 2)) & (points <= 104).all(axis=(1, 2))
            anchor, coverage = median_anchor(points, valid)
            cycle_a, cycle_b, cycle_ok = cycle_window(lengths) if coverage >= .70 else (0, 63, False)
            a, b = int(indices[cycle_a]), int(indices[cycle_b])
            predictions, low_logits, features = [], [], []
            for begin, end in ((0, len(cine)-1), (a, b)):
                selected = np.rint(np.linspace(begin, end, 32)).astype(int)
                clip = torch.from_numpy(cine[selected].copy()).float().to(device)[None, :, None] / 255
                ef, _, low, feature = base(clip, return_embedding=True)
                predictions.append(float(ef.item())); low_logits.append(float(low.item()))
                features.append(feature.cpu().numpy()[0])
            maps = np.stack([sample_motion_map(cine, np.array([[56, 28], [56, 80]])),
                             sample_motion_map(cine, anchor), sample_motion_map(cine, anchor, a, b)])
            np.savez_compressed(target, feature=np.stack(features), prediction=predictions,
                                low=low_logits, maps=maps, valid_coverage=coverage,
                                cycle_ok=cycle_ok, anchor=anchor, cycle_bounds=[a,b])
        with np.load(target) as cached:
            diagnostics.append({"split": row.split, "valid": float(cached["valid_coverage"]),
                                "cycle": bool(cached["cycle_ok"])})
        if (i + 1) % 20 == 0 or i + 1 == len(frame):
            print(f"M10 extraction cines={i+1}/{len(frame)}", flush=True)
    diagnostic_frame = pd.DataFrame(diagnostics)
    report = {split: {"cines": len(part), "anatomy_anchor_rate": float((part.valid >= .70).mean()),
                       "cycle_proposal_rate": float(part.cycle.mean())}
              for split, part in diagnostic_frame.groupby("split")}
    report.update(counts)
    # Only development train/validation input plausibility controls this technical gate.
    report["input_gate_passed"] = all(report[s]["anatomy_anchor_rate"] >= .70 for s in ("train", "validation"))
    write_json(args.summary_output / "input_diagnostics.json", report)
    del base, locator
    torch.cuda.empty_cache()
    return report


class CachedDataset(Dataset):
    def __init__(self, frame, targets, folder, variant, training=False):
        self.frame, self.targets, self.folder = frame, targets, folder
        self.variant, self.training = variant, training

    def __len__(self):
        return len(self.frame)

    def __getitem__(self, index):
        row = self.frame.iloc[index]
        mode = int(self.variant in ("cycle_only", "anatomy_cycle"))
        map_index = {"fixed_motion": 0, "anatomy_motion": 1, "anatomy_cycle": 2}.get(self.variant, 0)
        with np.load(self.folder / f"{int(row.cache_row):06d}.npz") as data:
            maps = torch.from_numpy(data["maps"][map_index].copy()).float() / 255
            feature = torch.from_numpy(data["feature"][mode].copy())
            ef, low = float(data["prediction"][mode]), float(data["low"][mode])
        if self.training:
            maps = (maps * np.random.uniform(.9, 1.1) + np.random.uniform(-.04, .04)).clamp(0, 1)
        return {"feature": feature, "base": torch.tensor(ef), "low": torch.tensor(low), "maps": maps,
                "target": torch.tensor(float(row.lvef)), "teacher": torch.tensor(float(self.targets["prediction"][row.source_row])),
                "embedding": torch.from_numpy(self.targets["embedding"][row.source_row].copy()),
                "study_id": str(row.study_id)}


@torch.inference_mode()
def predict(model, loader, device, baseline=False):
    model.eval(); rows = []
    for batch in loader:
        if baseline:
            ef, low = batch["base"], batch["low"]
        else:
            ef, low, _ = model(*[batch[k].to(device) for k in ("feature", "base", "low", "maps")])
            ef, low = ef.cpu(), low.cpu()
        rows.extend(zip(batch["study_id"], batch["target"].tolist(), ef.tolist(), low.sigmoid().tolist()))
    return pd.DataFrame(rows, columns=["study_id", "reference_lvef", "predicted_lvef", "low_probability"]).groupby(
        "study_id", as_index=False).agg(reference_lvef=("reference_lvef", "first"),
                                       predicted_lvef=("predicted_lvef", "mean"), low_probability=("low_probability", "mean"))


def train_variant(args, frame, targets, variant, device):
    seed_everything(args.seed)
    out = args.secure_output / variant; out.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary_output / variant / "summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text())
    parts = {s: frame.loc[frame.split.eq(s)].copy() for s in ("train", "validation", "test")}
    counts = parts["train"].groupby("study_id").size().to_dict()
    weights = [(3 if r.lvef <=40 else 1) / counts[r.study_id] for r in parts["train"].itertuples()]
    loaders = {s: DataLoader(CachedDataset(part, targets, args.secure_output / "cache", variant, s=="train"),
                             batch_size=32, sampler=WeightedRandomSampler(weights, len(weights), True) if s=="train" else None,
                             num_workers=0) for s, part in parts.items()}
    motion = variant not in ("control", "cycle_only")
    model = MotionFusion(motion).to(device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)
    best = float("inf"); stale=0; history=[]
    for epoch in range(1, args.epochs+1):
        model.train(); losses=[]
        for batch in loaders["train"]:
            ef, low, projected = model(*[batch[k].to(device) for k in ("feature", "base", "low", "maps")])
            teacher = batch["teacher"].to(device)
            teacher_probability = torch.sigmoid((40-teacher)/5)
            loss = F.huber_loss(ef, batch["target"].to(device), delta=5)
            loss += .5 * F.huber_loss(ef, teacher, delta=5)
            loss += .2 * F.binary_cross_entropy_with_logits(low, teacher_probability)
            loss += .1 * (1-(F.normalize(projected, dim=1)*F.normalize(batch["embedding"].to(device), dim=1)).sum(1)).mean()
            optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
            optimizer.step(); losses.append(float(loss.detach()))
        scheduler.step()
        validation = predict(model, loaders["validation"], device)
        val_mae = float((validation.predicted_lvef-validation.reference_lvef).abs().mean())
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), "validation_mae": val_mae})
        write_json(args.summary_output / variant / "history.json", history)
        print(f"M10 {variant} epoch={epoch:02d} loss={np.mean(losses):.4f} val_mae={val_mae:.4f}", flush=True)
        if val_mae < best:
            best=val_mae; stale=0
            torch.save({"model":model.state_dict(), "epoch":epoch, "variant":variant}, out / "best.pt")
        else:
            stale+=1
        if stale>=7:
            break
    checkpoint=torch.load(out / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model"])
    validation=predict(model, loaders["validation"], device)
    threshold=choose_threshold(validation.reference_lvef.to_numpy(), validation.low_probability.to_numpy())
    test=predict(model, loaders["test"], device)
    test.to_csv(out / "restricted_test_predictions.csv", index=False)
    result={"variant":variant, "status":"complete", "best_epoch":checkpoint["epoch"],
            "validation_mae":best, "test":metrics(test,threshold), "literal":literal_metrics(test),
            "errors":lvef_error_metrics(test), "threshold":threshold,
            "fusion_parameters":sum(p.numel() for p in model.parameters()) - (0 if motion else sum(p.numel() for p in model.motion_encoder.parameters())),
            "evidence":"repeatedly inspected patient-disjoint development split; report-linked weak EF"}
    write_json(summary_path, result)
    return result


def compare(args, frame, results):
    control=pd.read_csv(args.secure_output / "control" / "restricted_test_predictions.csv", dtype={"study_id":str})
    subjects=frame[["study_id", "subject_id"]].drop_duplicates()
    table=[]
    for result in results:
        variant=result["variant"]
        candidate=pd.read_csv(args.secure_output / variant / "restricted_test_predictions.csv", dtype={"study_id":str})
        paired=control.merge(candidate, on="study_id", suffixes=("_control", "_new"), validate="one_to_one").merge(subjects, on="study_id")
        delta=(paired.predicted_lvef_new-paired.reference_lvef_new).abs()-(paired.predicted_lvef_control-paired.reference_lvef_control).abs()
        groups=[delta[paired.subject_id.eq(subject)].to_numpy() for subject in paired.subject_id.unique()]
        rng=np.random.default_rng(args.seed)
        bootstrap=[np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))]).mean() for _ in range(2500)]
        lo,hi=np.quantile(bootstrap,[.025,.975])
        row={"variant":variant, **{k:result["test"][k] for k in ("mae","low_ef_mae","auroc","f1")},
             "literal_sensitivity":result["literal"]["sensitivity"], "delta_mae":float(delta.mean()), "delta_ci_lower":lo,"delta_ci_upper":hi}
        row["advances_development"]=bool(not args.smoke and variant!="control" and row["delta_mae"]<=-.30 and hi<0
                                           and row["low_ef_mae"]<=results[0]["test"]["low_ef_mae"]+.30
                                           and row["literal_sensitivity"]>=results[0]["literal"]["sensitivity"]-.05)
        table.append(row)
    comparison=pd.DataFrame(table)
    comparison.to_csv(args.summary_output / "comparison.csv",index=False)
    write_json(args.summary_output / "comparison.json",table)
    print(comparison.to_string(index=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("cache-index","teacher-cache","baseline-checkpoint","locator-checkpoint","secure-output","summary-output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--epochs",type=int,default=20); p.add_argument("--seed",type=int,default=20261005)
    p.add_argument("--smoke",action="store_true")
    p.add_argument("--credentialed-root",type=Path,required=True)
    args=p.parse_args()
    secure_root=args.credentialed_root.resolve()
    if not args.secure_output.resolve().is_relative_to(secure_root):
        raise ValueError("Restricted outputs must remain under credentialed derived root")
    # Resume only exactly the same locked implementation and configuration.
    configuration={"runner_sha256":digest(Path(__file__)),
                   "motion_sha256":digest(PROJECT / "src/plax_lvef/motion_maps.py"),
                   "epochs":1 if args.smoke else args.epochs, "seed":args.seed, "smoke":args.smoke}
    run_marker=args.secure_output / "run_configuration.json"
    if run_marker.exists() and json.loads(run_marker.read_text())!=configuration:
        raise ValueError("Run configuration changed; choose a new output directory")
    write_json(run_marker,configuration)
    frame=pd.read_csv(args.cache_index,dtype={"subject_id":str,"study_id":str,"file_id":str})
    check_splits(frame); frame["source_row"]=np.arange(len(frame))
    if args.smoke:
        selected=[]
        for split in ("train","validation","test"):
            part=frame.loc[frame.split.eq(split)]
            for low in (False,True):
                selected.extend(part.loc[part.lvef.le(40).eq(low)].head(2).index)
        frame=frame.loc[selected].reset_index(drop=True); args.epochs=1
    frame["cache_row"]=np.arange(len(frame))
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_everything(args.seed)
    print(f"M10 device={device} cines={len(frame)} smoke={args.smoke}",flush=True)
    diagnostics=extract(args,frame,device)
    if not diagnostics["input_gate_passed"] and not args.smoke:
        write_json(args.summary_output / "status.json",{"status":"input_feasibility_failed", "reason":"anatomy anchor coverage below locked gate; no model promotion"})
        print("M10 stopped: locator input feasibility failed; review diagnostics before training.",flush=True)
        return
    with np.load(args.teacher_cache) as archive:
        targets={k:archive[k] for k in ("prediction","embedding")}
    if len(targets["prediction"])!=len(pd.read_csv(args.cache_index)):
        raise ValueError("Teacher targets are not aligned to original index")
    # Recompute frozen M5 statistics on exactly this cohort before any adaptation.
    loaders={s:DataLoader(CachedDataset(frame.loc[frame.split.eq(s)], targets,args.secure_output / "cache","control"),batch_size=32)
             for s in ("validation","test")}
    frozen=predict(MotionFusion(False),loaders["test"],device,baseline=True)
    validation=predict(MotionFusion(False),loaders["validation"],device,baseline=True)
    threshold=choose_threshold(validation.reference_lvef.to_numpy(),validation.low_probability.to_numpy())
    frozen.to_csv(args.secure_output / "restricted_frozen_predictions.csv",index=False)
    write_json(args.summary_output / "frozen_m5.json",{"test":metrics(frozen,threshold),"literal":literal_metrics(frozen),"errors":lvef_error_metrics(frozen)})
    results=[train_variant(args,frame,targets,v,device) for v in VARIANTS]
    compare(args,frame,results)
    write_json(args.summary_output / "status.json",{"status":"complete", "smoke":args.smoke, "joint_fine_tuning_launched":False})
    print("M10 COMPLETE - keep this window open and tell Codex.",flush=True)


if __name__=="__main__":
    main()
