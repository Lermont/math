"""Download only the three small, public Elliptic2 v1 subgraph CSVs."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/elliptic2/raw"
REF = ROOT / "references/graph131"
COMMIT = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
PAPER = "preprints/Polynomial-Mixing-of-the-Switch-Chain-for-Every-Graphical-Degree-Sequence-September-25-2026"


def get(url: str, limit: int = 30_000_000) -> bytes:
    with requests.get(url, timeout=(15, 60), stream=True) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(1 << 18):
            content.extend(chunk)
            if len(content) > limit:
                raise ValueError(f"Download exceeds {limit} bytes: {url}")
    return bytes(content)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    REF.mkdir(parents=True, exist_ok=True)
    base = "https://www.kaggle.com/api/v1/datasets/"
    metadata = json.loads(get(base + "view/ellipticco/elliptic2-data-set"))
    files = json.loads(get(base + "list/ellipticco/elliptic2-data-set"))
    if metadata["currentVersionNumber"] != 1:
        raise RuntimeError("Dataset has changed: review version before downloading")
    manifest = {
        "accessed_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "ellipticco/elliptic2-data-set", "version": 1,
        "license": metadata["licenseName"], "paper_commit": COMMIT,
        "data_scope": "Labeled subgraphs only; excludes both background CSVs",
        "files": [], "references": [],
    }
    (REF / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (REF / "dataset-files.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    sizes = {item["name"]: item["totalBytes"] for item in files["datasetFiles"]}
    for name in ("connected_components.csv", "nodes.csv", "edges.csv"):
        url = base + "download/ellipticco/elliptic2-data-set/" + name + "?datasetVersionNumber=1"
        target = DATA / name
        if not target.exists():
            payload = get(url)
            with ZipFile(io.BytesIO(payload)) as archive:
                if archive.namelist() != [name] or archive.getinfo(name).file_size != sizes[name]:
                    raise ValueError("Unexpected dataset archive")
                target.write_bytes(archive.read(name))
        payload = target.read_bytes()
        if len(payload) != sizes[name]:
            raise ValueError("Dataset size mismatch")
        manifest["files"].append({"name": name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "url": url})
        print(f"{name}: {len(payload):,} bytes, header={payload.splitlines()[0]!r}", flush=True)
    paths = ["lean/docs/131.md"] + [f"{PAPER}/build/sections/{s}.tex" for s in ("introduction", "setup", "mixing", "exact-sampling")]
    for path in paths:
        url = f"https://raw.githubusercontent.com/openai/math/{COMMIT}/{path}"
        target = REF / Path(path).name
        if not target.exists():
            target.write_bytes(get(url))
        payload = target.read_bytes()
        manifest["references"].append({"path": target.name, "url": url, "sha256": hashlib.sha256(payload).hexdigest()})
    (REF / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Saved source manifest", flush=True)


if __name__ == "__main__":
    main()
