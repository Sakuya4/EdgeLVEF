"""Check publication links, aggregate metrics, figure sources and private tokens."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAGES = [
    ROOT / "README.md", ROOT / "README.zh-TW.md", ROOT / "MODEL_CARD.md",
    *list((ROOT / "docs").rglob("*.md")),
    *list((ROOT / "research" / "plax_lvef").rglob("*.md")),
]

def main():
    count = 0
    for page in PAGES:
        content = page.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:M|H)\d+(?:[-–]\w+)?\b", content), page
        assert not re.search(r"\b[ps]\d{8}\b", content), page
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content):
            if target.startswith(("http:", "https:", "#")):
                continue
            target = unquote(target.split("#")[0])
            assert (page.parent / target).exists(), (page, target)
            count += 1
    results = ROOT / "research" / "plax_lvef" / "results"
    student = json.loads((results / "student_mobilenet_v3_large.json").read_text())
    table = pd.read_csv(results / "backbone_ablation.csv")
    selected = table.loc[table.backbone.eq("mobilenet_v3_large")].iloc[0]
    assert abs(selected.mae_pp - student["test"]["mae"]) < 1e-10
    assert student["parameter_count"] == 3_212_755
    assert student["test"]["studies"] == 82 and student["test"]["low_ef_n"] == 33
    manifest = json.loads((ROOT / "docs/assets/project/source_manifest.json").read_text())
    assert len(manifest["figures"]) == 7
    for record in manifest["figures"]:
        image = ROOT / "docs/assets/project" / record["file"]
        assert hashlib.sha256(image.read_bytes()).hexdigest() == record["sha256"]
    print(f"PASS: {len(PAGES)} Markdown pages, {count} local links, selected metrics and seven original figure hashes")

if __name__ == "__main__":
    main()
