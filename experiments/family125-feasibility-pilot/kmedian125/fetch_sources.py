"""Fetch immutable public sources for the local family-125 feasibility pilot."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "references" / "kmedian125"
MATH_COMMIT = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
OB_COMMIT = "ee823101bd43dbb4095b103ef248221c682da88e"
ONE_COMMIT = "950cae188f171878c3ff574b81bce7d41736107e"
PAPERS = {
    "threshold": "The-Approximation-Threshold-for-Metric-k-Median-September-24-2026",
    "recovery": "Single-Exponential-Recovery-and-Bounded-Price-Strictness-for-Metric-k-Median-September-24-2026",
}

def get(url):
    with urlopen(Request(url, headers={"User-Agent": "kmedian125-local-research"}), timeout=60) as r:
        return r.read()

def api(path):
    return json.loads(get("https://api.github.com/" + path))

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = []
    def save(url, rel, commit=None):
        path = DEST / rel
        data = path.read_bytes() if path.exists() else get(url)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        manifest.append(dict(path=str(path.relative_to(ROOT)).replace("\\", "/"),
                             url=url, commit=commit, bytes=len(data),
                             sha256=hashlib.sha256(data).hexdigest()))
    latest = api("repos/openai/math/commits/main")
    metadata = {"checked_utc": datetime.now(timezone.utc).isoformat(),
                "math_commit": MATH_COMMIT, "latest_math": latest["sha"],
                "latest_message": latest["commit"]["message"]}
    for name, folder in PAPERS.items():
        path = "preprints/" + folder
        listing = api(f"repos/openai/math/contents/{path}?ref={MATH_COMMIT}")
        for item in listing:
            if item["type"] == "dir":
                tree = api(f"repos/openai/math/git/trees/{item['sha']}?recursive=1")
                assert not tree.get("truncated")
                for entry in tree["tree"]:
                    if entry["type"] == "blob" and entry["path"].endswith((".tex", ".bib", ".md")):
                        remote = path + "/" + item["name"] + "/" + entry["path"]
                        save(f"https://raw.githubusercontent.com/openai/math/{MATH_COMMIT}/{remote}",
                             f"{name}/{item['name']}/{entry['path']}", MATH_COMMIT)
            elif item["name"].endswith((".md", ".pdf")):
                save(item["download_url"], f"{name}/{item['name']}", MATH_COMMIT)
    for remote in ["lean/docs/125.md", "history.md", "README.md", "LICENSE",
                   "lean/ComparatorChallenges/MetricKMedian.lean",
                   "lean/ComparatorChallenges/KMedianThreshold.lean",
                   "lean/ComparatorChallenges/KMedianRefinedRecovery.lean"]:
        save(f"https://raw.githubusercontent.com/openai/math/{MATH_COMMIT}/{remote}", "math/" + remote, MATH_COMMIT)
    ob = api("repos/antoinedemathelin/obpam/commits/main")
    oc = OB_COMMIT
    metadata["obpam_commit"] = oc
    metadata["latest_obpam"] = ob["sha"]
    tree = api(f"repos/antoinedemathelin/obpam/git/trees/{oc}?recursive=1")
    assert not tree.get("truncated")
    for item in tree["tree"]:
        if item["type"] == "blob":
            save(f"https://raw.githubusercontent.com/antoinedemathelin/obpam/{oc}/{item['path']}",
                 "obpam/" + item["path"], oc)
    for paper in ["2008.05171v2", "2501.19285v1"]:
        save(f"https://arxiv.org/pdf/{paper}", f"baselines/{paper}.pdf")
    metadata["onebatch_github_commit"] = ONE_COMMIT
    for path in ["README.md", "LICENSE", "onebatch/onebatchpam.py", "onebatch/pam.pyx", "pyproject.toml", "setup.py"]:
        save(f"https://raw.githubusercontent.com/antoinedemathelin/onebatch/{ONE_COMMIT}/{path}",
             "onebatch/" + path, ONE_COMMIT)
    # Pin the actually executed binary distributions, not merely the current GitHub wrapper.
    for package, version in [("onebatch", "0.1.0"), ("kmedoids", "0.5.5")]:
        info_url = f"https://pypi.org/pypi/{package}/{version}/json"
        info = json.loads(get(info_url))
        for wheel in info["urls"]:
            if "cp311" in wheel["filename"] and "win_amd64.whl" in wheel["filename"]:
                save(wheel["url"], "wheels/" + wheel["filename"])
                assert manifest[-1]["sha256"] == wheel["digests"]["sha256"]
        save(info_url, f"wheels/{package}-{version}-pypi.json")
    save("https://archive.ics.uci.edu/static/public/236/seeds.zip", "datasets/seeds.zip")
    save("https://archive.ics.uci.edu/dataset/236/seeds", "datasets/seeds-source.html")
    (DEST / "sources.json").write_text(json.dumps({**metadata, "files": manifest}, indent=2), encoding="utf-8")
    print(json.dumps({**metadata, "file_count": len(manifest)}, indent=2))

if __name__ == "__main__":
    main()
