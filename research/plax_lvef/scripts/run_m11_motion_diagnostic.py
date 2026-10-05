"""M11 motion-only diagnostic: do maps carry useful ordered EF signal?"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler

from run_m10_motion_fusion import CachedDataset, check_splits, digest, write_json
from train_student import seed_everything, literal_metrics, lvef_error_metrics
from train_teacher import metrics, choose_threshold

VARIANTS = ("fixed", "anatomy", "shuffled", "static")


def transform_map(maps, variant, cache_row, seed):
    if variant == "shuffled":
        # Stable per cine, independent of EF/split; same order for all lines.
        permutation = np.random.default_rng(seed + int(cache_row)).permutation(maps.shape[-1])
        return maps[..., torch.from_numpy(permutation)]
    if variant == "static":
        return maps.mean(dim=-1, keepdim=True).expand_as(maps).clone()
    return maps


class MotionDataset(CachedDataset):
    def __init__(self, *args, diagnostic_variant, seed, **kwargs):
        super().__init__(*args, variant="fixed_motion" if diagnostic_variant == "fixed" else "anatomy_motion", **kwargs)
        self.diagnostic_variant, self.seed = diagnostic_variant, seed

    def __getitem__(self, index):
        item = super().__getitem__(index)
        row = self.frame.iloc[index]
        item["maps"] = transform_map(item["maps"], self.diagnostic_variant, row.cache_row, self.seed)
        return item


class MotionOnly(nn.Module):
    def __init__(self, mean=50., std=15.):
        super().__init__()
        blocks = []
        for incoming, outgoing in ((5, 16), (16, 32), (32, 64)):
            blocks.extend([nn.Conv2d(incoming, outgoing, 3, stride=2, padding=1),
                           nn.GroupNorm(4, outgoing), nn.Hardswish()])
        self.encoder = nn.Sequential(*blocks, nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.hidden = nn.Sequential(nn.Linear(64, 128), nn.Hardswish(), nn.Dropout(.2))
        self.ef = nn.Linear(128, 1)
        self.low = nn.Linear(128, 1)
        self.projector = nn.Linear(64, 512)
        self.register_buffer("label_mean", torch.tensor(float(mean)))
        self.register_buffer("label_std", torch.tensor(float(std)))

    def forward(self, maps):
        feature = self.encoder(maps)
        hidden = self.hidden(feature)
        return (self.ef(hidden).squeeze(1) * self.label_std + self.label_mean,
                self.low(hidden).squeeze(1), self.projector(feature))


@torch.inference_mode()
def predict(model, loader, device):
    model.eval(); rows = []
    for batch in loader:
        ef, low, _ = model(batch["maps"].to(device))
        rows.extend(zip(batch["study_id"], batch["target"].tolist(), ef.cpu().tolist(), low.sigmoid().cpu().tolist()))
    return pd.DataFrame(rows, columns=["study_id", "reference_lvef", "predicted_lvef", "low_probability"]).groupby(
        "study_id", as_index=False).agg(reference_lvef=("reference_lvef", "first"),
                                       predicted_lvef=("predicted_lvef", "mean"), low_probability=("low_probability", "mean"))


def previews(args, frame):
    """Blinded deterministic TRAIN/validation previews, kept credentialed locally."""
    out = args.secure_output / "previews"; out.mkdir(parents=True, exist_ok=True)
    records = []
    for split in ("train", "validation"):
        part = frame.loc[frame.split.eq(split)]
        selected = np.unique(np.rint(np.linspace(0, len(part)-1, min(20, len(part)))).astype(int))
        for number, offset in enumerate(selected, 1):
            row = part.iloc[offset]
            with np.load(args.motion_cache / f"{int(row.cache_row):06d}.npz") as data:
                anchor, maps = data["anchor"].astype(np.float32), data["maps"]
                coverage, cycle = float(data["valid_coverage"]), bool(data["cycle_ok"])
            with np.load(row.path) as archive:
                cine = archive["frames"]
            axis = anchor[1] - anchor[0]; axis /= max(np.linalg.norm(axis), 1e-6)
            normal = np.array([-axis[1], axis[0]]); center = anchor.mean(0)
            panels = []
            for t in (0, len(cine)//2, len(cine)-1):
                image = cv2.cvtColor(cine[t], cv2.COLOR_GRAY2BGR)
                for shift in (-12, -6, 0, 6, 12):
                    a = tuple(np.rint(center - 40*axis + shift*normal).astype(int))
                    b = tuple(np.rint(center + 40*axis + shift*normal).astype(int))
                    cv2.line(image, a, b, (255,255,255), 1)
                panels.append(cv2.resize(image, (384,384), interpolation=cv2.INTER_NEAREST))
            canvas = np.zeros((684,1152,3), np.uint8)
            canvas[40:424] = np.concatenate(panels, axis=1)
            for position, (map_index, title) in enumerate(((0,"Fixed lines"),(1,"Anatomy lines"),(2,"Cycle proposal"))):
                stacked = maps[map_index].reshape(400,128)
                image = cv2.resize(stacked, (384,240), interpolation=cv2.INTER_NEAREST)
                canvas[444:684,position*384:(position+1)*384] = cv2.cvtColor(image,cv2.COLOR_GRAY2BGR)
                cv2.putText(canvas,title,(position*384+8,440),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            cv2.putText(canvas,f"{split} sample {number:02d} | anchor plausibility {coverage:.2f} | cycle {cycle}",
                        (8,28),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
            # Use imencode/tofile for Unicode Windows paths, no public raw images.
            cv2.imencode(".png",canvas)[1].tofile(out / f"{split}_{number:02d}.png")
            records.append({"split":split,"preview_number":number,"anchor_coverage":coverage,
                            "cycle_proposed":cycle,"map_mean_absolute_difference_fixed_anatomy":
                            float(np.abs(maps[0].astype(float)-maps[1]).mean())})
    write_json(args.summary_output / "preview_diagnostics.json",records)
    print(f"M11 secure blinded previews ready: {len(records)}",flush=True)


def loaders_for(args, frame, targets, variant):
    parts = {s:frame.loc[frame.split.eq(s)].copy() for s in ("train","validation","test")}
    count = parts["train"].groupby("study_id").size().to_dict()
    weights = [(3 if r.lvef<=40 else 1)/count[r.study_id] for r in parts["train"].itertuples()]
    return {s:DataLoader(MotionDataset(part,targets,args.motion_cache,diagnostic_variant=variant,
                                      seed=args.seed,training=s=="train"),batch_size=32,num_workers=0,
                         sampler=WeightedRandomSampler(weights,len(weights),True) if s=="train" else None)
            for s,part in parts.items()}


def train(args, frame, targets, variant, device):
    seed_everything(args.seed)
    out = args.secure_output / variant; out.mkdir(parents=True,exist_ok=True)
    history_path = args.summary_output / variant / "history.json"
    ready = out / "selection.json"
    if ready.exists():
        return
    loaders = loaders_for(args,frame,targets,variant)
    labels = frame.loc[frame.split.eq("train")].drop_duplicates("study_id").lvef.to_numpy(float)
    model = MotionOnly(labels.mean(),max(labels.std(),1)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,args.epochs)
    best = float("inf"); stale=0; history=[]
    for epoch in range(1,args.epochs+1):
        model.train(); losses=[]
        for batch in loaders["train"]:
            ef,low,projected = model(batch["maps"].to(device))
            teacher = batch["teacher"].to(device)
            loss = F.huber_loss(ef,batch["target"].to(device),delta=5)
            loss += .5*F.huber_loss(ef,teacher,delta=5)
            loss += .2*F.binary_cross_entropy_with_logits(low,torch.sigmoid((40-teacher)/5))
            loss += .1*(1-(F.normalize(projected,dim=1)*F.normalize(batch["embedding"].to(device),dim=1)).sum(1)).mean()
            optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1)
            optimizer.step(); losses.append(float(loss.detach()))
        scheduler.step()
        validation = predict(model,loaders["validation"],device)
        mae = float((validation.reference_lvef-validation.predicted_lvef).abs().mean())
        history.append({"epoch":epoch,"loss":float(np.mean(losses)),"validation_mae":mae})
        write_json(history_path,history)
        print(f"M11 {variant} epoch={epoch:02d} loss={np.mean(losses):.3f} val_mae={mae:.3f}",flush=True)
        if mae<best:
            best=mae; stale=0
            torch.save({"model":model.state_dict(),"epoch":epoch,"variant":variant},out / "best.pt")
        else:
            stale+=1
        if stale>=7:
            break
    checkpoint = torch.load(out / "best.pt",map_location=device,weights_only=True)
    model.load_state_dict(checkpoint["model"])
    validation = predict(model,loaders["validation"],device)
    threshold = choose_threshold(validation.reference_lvef.to_numpy(),validation.low_probability.to_numpy())
    validation.to_csv(out / "restricted_validation_predictions.csv",index=False)
    write_json(ready,{"best_epoch":checkpoint["epoch"],"threshold":threshold,"validation_mae":best,
                      "epochs_completed":len(history)})


def evaluate(args, frame, targets, variant, device):
    out = args.secure_output / variant
    selection = json.loads((out / "selection.json").read_text())
    model = MotionOnly().to(device)
    model.load_state_dict(torch.load(out / "best.pt",map_location=device,weights_only=True)["model"])
    test = predict(model,loaders_for(args,frame,targets,variant)["test"],device)
    test.to_csv(out / "restricted_test_predictions.csv",index=False)
    result = {"variant":variant,**selection,"test":metrics(test,selection["threshold"]),
              "literal":literal_metrics(test),"errors":lvef_error_metrics(test),
              "inference_parameters":sum(p.numel() for p in model.parameters())-sum(p.numel() for p in model.projector.parameters()),
              "evidence":"motion-only diagnostic on repeatedly inspected development split; no promotion"}
    write_json(args.summary_output / variant / "summary.json",result)
    return result


def paired_delta(candidate, reference, subjects, seed):
    paired = candidate.merge(reference,on="study_id",suffixes=("_new","_ref"),validate="one_to_one").merge(subjects,on="study_id")
    delta = (paired.predicted_lvef_new-paired.reference_lvef_new).abs()-(paired.predicted_lvef_ref-paired.reference_lvef_ref).abs()
    groups = [delta[paired.subject_id.eq(s)].to_numpy() for s in paired.subject_id.unique()]
    rng = np.random.default_rng(seed)
    boot = [np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))]).mean() for _ in range(2500)]
    lo,hi = np.quantile(boot,[.025,.975])
    return {"delta_mae":float(delta.mean()),"ci_lower":float(lo),"ci_upper":float(hi)}


def compare(args, frame, results):
    # Validation-only signal assessment; the inspected test cannot trigger new training.
    subjects = frame[["subject_id","study_id"]].drop_duplicates()
    validation = {v:pd.read_csv(args.secure_output / v / "restricted_validation_predictions.csv",dtype={"study_id":str}) for v in VARIANTS}
    labels = frame.loc[frame.split.eq("train")].drop_duplicates("study_id").lvef.to_numpy(float)
    train_median = float(np.median(labels))
    median_mae = float((validation["anatomy"].reference_lvef-train_median).abs().mean())
    anatomy = next(r for r in results if r["variant"]=="anatomy")
    differences = {v:paired_delta(validation["anatomy"],validation[v],subjects,args.seed) for v in ("fixed","shuffled","static")}
    signal = {"training_median_ef":train_median,"constant_baseline_validation_mae":median_mae,
              "anatomy_validation_mae":anatomy["validation_mae"],"paired_validation_deltas":differences,
              "predictive_signal":bool(not args.smoke and anatomy["validation_mae"]<=median_mae-1),
              "ordered_motion_signal":bool(not args.smoke and all(differences[v]["delta_mae"]<=-.5 and differences[v]["ci_upper"]<0 for v in ("shuffled","static"))),
              "anatomical_position_signal":bool(not args.smoke and differences["fixed"]["delta_mae"]<=-.3 and differences["fixed"]["ci_upper"]<0),
              "automatic_further_training":False}
    write_json(args.summary_output / "validation_signal.json",signal)
    table = [{"variant":r["variant"],"validation_mae":r["validation_mae"],
              **{k:r["test"][k] for k in ("mae","low_ef_mae","auroc","f1")},
              "literal_sensitivity":r["literal"]["sensitivity"],"parameters":r["inference_parameters"]} for r in results]
    pd.DataFrame(table).to_csv(args.summary_output / "comparison.csv",index=False)
    print(pd.DataFrame(table).to_string(index=False),flush=True)
    print("Validation signal assessment:",json.dumps(signal),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache-index","teacher-cache","motion-cache","secure-output","summary-output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--epochs",type=int,default=20)
    parser.add_argument("--seed",type=int,default=20261005)
    parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--credentialed-root",type=Path,required=True)
    args = parser.parse_args()
    secure_root=args.credentialed_root.resolve()
    if not args.secure_output.resolve().is_relative_to(secure_root):
        raise ValueError("Restricted outputs must remain credentialed")
    signature=json.loads((args.motion_cache / "signature.json").read_text())
    if signature["index"]!=digest(args.cache_index) or signature["smoke"]:
        raise ValueError("Motion cache does not match the full cohort")
    configuration={"runner_sha256":digest(Path(__file__)),"index":digest(args.cache_index),"teacher":digest(args.teacher_cache),
                   "cache_signature":signature,"seed":args.seed,"epochs":1 if args.smoke else args.epochs,"smoke":args.smoke}
    marker=args.secure_output / "run_configuration.json"
    if marker.exists() and json.loads(marker.read_text())!=configuration:
        raise ValueError("Run configuration differs; do not overwrite an experiment")
    write_json(marker,configuration)
    frame=pd.read_csv(args.cache_index,dtype={"subject_id":str,"study_id":str,"file_id":str})
    check_splits(frame); frame["source_row"]=np.arange(len(frame)); frame["cache_row"]=np.arange(len(frame))
    if args.smoke:
        selected=[]
        for split in ("train","validation","test"):
            for low in (False,True):
                selected.extend(frame.loc[frame.split.eq(split) & frame.lvef.le(40).eq(low)].head(2).index)
        frame=frame.loc[selected].reset_index(drop=True); args.epochs=1
    with np.load(args.teacher_cache) as archive:
        targets={k:archive[k] for k in ("prediction","embedding")}
    if len(targets["prediction"])!=signature["rows"]:
        raise ValueError("Teacher cache length mismatch")
    for i in frame.cache_row:
        if not (args.motion_cache / f"{int(i):06d}.npz").exists():
            raise ValueError("Incomplete motion cache")
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"M11 device={device} cines={len(frame)} smoke={args.smoke}",flush=True)
    previews(args,frame)
    # Freeze all selections before computing any test metrics.
    for variant in VARIANTS:
        train(args,frame,targets,variant,device)
    results=[evaluate(args,frame,targets,v,device) for v in VARIANTS]
    compare(args,frame,results)
    write_json(args.summary_output / "status.json",{"status":"complete","smoke":args.smoke,"promoted":False})
    print("M11 COMPLETE - keep this window open and tell Codex.",flush=True)


if __name__=="__main__":
    main()
