"""Download immutable source snapshots and record SHA-256; explicit network step."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "references" / "p2p178"
PIN = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
PAPER = "preprints/Deterministic-nonbipartite-Ramanujan-graphs-in-every-fixed-degree-September-23-2026"


def fetch(url: str, local: str) -> bytes:
    DEST.mkdir(parents=True, exist_ok=True)
    path = DEST / local
    manifest_path = DEST / "sources.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {"sources": []}
    existing = next((x for x in manifest["sources"] if x["path"] == local), None)
    if existing is not None:
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == existing["sha256"], local
        assert existing["url"] == url, local
        return data
    request = Request(url, headers={"User-Agent": "local-p2p178-research", "Accept": "*/*"})
    with urlopen(request, timeout=60) as response:
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"Refuse to change an existing source: {path}")
    path.write_bytes(data)
    manifest["sources"].append({"path": local, "url": url, "sha256": hashlib.sha256(data).hexdigest(),
                                "bytes": len(data), "retrieved_utc": datetime.now(timezone.utc).isoformat()})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(local, len(data), flush=True)
    return data


def math_dir(remote: str, local: str) -> None:
    entries = json.loads(fetch(f"https://api.github.com/repos/openai/math/contents/{remote}?ref={PIN}",
                              f"api/{remote.replace('/', '__')}.json"))
    for entry in entries:
        target = f"{local}/{entry['name']}"
        if entry["type"] == "dir":
            math_dir(entry["path"], target)
        elif entry["type"] == "file":
            fetch(entry["download_url"], target)


def main() -> None:
    fetch("https://api.github.com/repos/openai/math/commits/main", "api/math-main-20261011.json")
    for name in ["README.md", "LICENSE", "history.md", "CONTENTS.md", "overview.tex",
                 "lean/README.md", "lean/formalization.yaml"]:
        fetch(f"https://raw.githubusercontent.com/openai/math/{PIN}/{name}", f"math/{name}")
    math_dir(PAPER, "math/paper178")


if __name__ == "__main__":
    main()
