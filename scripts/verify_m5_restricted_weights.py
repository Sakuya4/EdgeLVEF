"""Verify authorized local M5 checkpoints without copying them into the repo."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from edgelvef.research import EdgeLvefStudent, GaoR2Plus1DTeacher


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_model(path: Path, role: str) -> int:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if role.startswith("teacher"):
        model = GaoR2Plus1DTeacher(pretrained=False)
    else:
        model = EdgeLvefStudent(pretrained=False)
    model.load_state_dict(checkpoint["model"], strict=True)
    return sum(parameter.numel() for parameter in model.parameters())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher-batch16", type=Path, required=True)
    parser.add_argument("--teacher-batch32", type=Path, required=True)
    parser.add_argument("--student", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "m5_teacher_student"
        / "artifact_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    supplied = {
        "teacher_seed_batch16": args.teacher_batch16,
        "teacher_seed_batch32": args.teacher_batch32,
        "edge_student_m5e": args.student,
    }
    result = []
    for artifact in manifest["artifacts"]:
        role = artifact["role"]
        path = supplied[role]
        actual_hash = sha256(path)
        if actual_hash != artifact["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {role}")
        result.append(
            {
                "role": role,
                "sha256_verified": True,
                "parameter_count": load_model(path, role),
            }
        )
    print(json.dumps({"status": "verified", "artifacts": result}, indent=2))


if __name__ == "__main__":
    main()
