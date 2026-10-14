"""Extract original embedded artwork from the supplied project description."""
import argparse
import hashlib
import json
from pathlib import Path

import pymupdf

FIGURES = {
    4: ["probe-board-connection"],
    5: ["power-supply", "external-circuit"],
    6: ["pcb-layout", "enclosure-design"],
    8: ["portable-system", "application-interface"],
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(args.pdf)
    records = []
    for page_number, names in FIGURES.items():
        images = document[page_number - 1].get_images(full=True)
        if len(images) != len(names):
            raise ValueError(f"Unexpected embedded artwork count on page {page_number}")
        for name, metadata in zip(names, images):
            extracted = document.extract_image(metadata[0])
            target = args.output / f"{name}.{extracted['ext']}"
            target.write_bytes(extracted["image"])
            records.append({
                "file": target.name, "source_page": page_number,
                "width": extracted["width"], "height": extracted["height"],
                "sha256": hashlib.sha256(extracted["image"]).hexdigest(),
            })
    (args.output / "source_manifest.json").write_text(
        json.dumps({"source": "EdgeLVEF project description 4.0", "figures": records}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(records, indent=2))

if __name__ == "__main__":
    main()
