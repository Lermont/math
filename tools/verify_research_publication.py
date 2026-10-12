"""Verify the public research package bytes and navigation; never run benchmarks.

Python 3.10+, standard library only. Run from a checkout with original Git line
endings. This checks publication integrity, not scientific truth or peer review.
"""
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


class PublicationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise PublicationError(message)


def local_target(path, relative_to=None):
    base = ROOT if relative_to is None else relative_to
    target = (base / path).resolve()
    require(target.is_relative_to(ROOT), f"Path escapes repository: {path}")
    return target


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_anchors(text):
    anchors, counts = set(), {}
    # Headings outside fenced code, using GitHub's ordinary identifier rules.
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith((chr(96) * 3, "~~~")):
            fence = not fence
        if fence:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = re.sub(r"<[^>]+>", "", match.group(1))
        title = re.sub(r"\[([^\]\n]+)\]\([^)]+\)", r"\1", title)
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        n = counts.get(slug, 0)
        counts[slug] = n + 1
        anchors.add(slug + (f"-{n}" if n else ""))
    return anchors


def check_links(path):
    text = path.read_text(encoding="utf-8")
    if path == ROOT / "README.md":
        text = text.split("## Upstream collection\n", 1)[0]
    text = re.sub(r"(?ms)^\x60{3}.*?^\x60{3}[^\n]*$", "", text)
    checked = 0
    for raw in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", text):
        url = urlsplit(raw)
        if url.scheme or url.netloc:
            continue
        target = local_target(unquote(url.path), path.parent) if url.path else path
        require(target.exists(), f"Broken link in {path.relative_to(ROOT)}: {raw}")
        if url.fragment and target.is_file() and target.suffix.lower() == ".md":
            require(
                unquote(url.fragment) in markdown_anchors(target.read_text(encoding="utf-8")),
                f"Missing heading in {path.relative_to(ROOT)}: {raw}",
            )
        checked += 1
    return checked


def verify():
    catalog_path = ROOT / "experiments/index.json"
    catalog = load_json(catalog_path)
    require(catalog["schema_version"] == 1, "Unsupported catalogue schema")
    require(catalog["repository"] == "https://github.com/Lermont/math", "Wrong repository scope")
    require(catalog["benchmark_rerun_for_documentation_update"] is False, "Do not relabel documentation as a benchmark")
    base = catalog["evidence_snapshot"]["commit"]
    require(re.fullmatch(r"[a-f0-9]{40}", base) is not None, "Evidence snapshot must be a complete commit SHA")
    studies = catalog["experiments"]
    require(len(studies) == 7, "Expected exactly seven studies")
    require({r["number"] for r in studies} == set(range(1, 8)), "Missing/duplicate PR numbers")
    require(len({r["id"] for r in studies}) == 7, "Duplicate study IDs")
    require(len({r["citation_key"] for r in studies}) == 7, "Duplicate citation keys")
    require(
        {p.name for p in (ROOT / "experiments").glob("family*") if p.is_dir()}
        == {r["id"] for r in studies},
        "Unlisted or missing experiment directories",
    )
    checked_hashes, preserved_source_files, test_executions = 0, 0, 0
    docs = {
        ROOT / "README.md", ROOT / "CITATION.md", ROOT / "llms.txt",
        ROOT / "experiments/README.md", ROOT / "experiments/RESEARCH_INTEGRITY.md"
    }
    for study in studies:
        require(re.fullmatch(r"family[0-9]+-[a-z0-9-]+", study["id"]) is not None, "Invalid study ID")
        directory = ROOT / "experiments" / study["id"]
        expected_prefix = "experiments/" + study["id"] + "/"
        for key in ["report_path", "landing_path", "guide_path", "manifest_path", "tests_path"]:
            require(study[key].startswith(expected_prefix), f"Cross-study {key}: {study['id']}")
            require(local_target(study[key]).is_file(), f"Missing catalogue target: {study[key]}")
        report = local_target(study["report_path"])
        require(study["report_title"] == report.read_text(encoding="utf-8").splitlines()[0].removeprefix("# "), f"Citation title mismatch: {study['id']}")
        require(hashlib.sha256(report.read_bytes()).hexdigest() == study["report_sha256"], f"Report identity changed: {study['id']}")
        expected = catalog["repository"] + "/blob/" + base + "/" + study["report_path"]
        require(study["report_permalink"] == expected, f"Unpinned report: {study['id']}")
        require(study["report_raw_url"] == "https://raw.githubusercontent.com/Lermont/math/" + base + "/" + study["report_path"], f"Wrong raw URL: {study['id']}")
        require(study["pull_request"] == catalog["repository"] + "/pull/" + str(study["number"]), f"PR mismatch: {study['id']}")
        for token in study["reported_numeric_tokens"]:
            require(token in report.read_text(encoding="utf-8"), f"Numeric evidence token absent: {study['id']}: {token}")
        for evidence in study["evidence"]:
            require(evidence["path"].startswith(expected_prefix), f"Cross-study evidence: {study['id']}")
            url = urlsplit(evidence["path"])
            target = local_target(unquote(url.path))
            require(target.is_file(), f"Missing evidence: {evidence['path']}")
            if url.fragment and target.suffix == ".md":
                require(url.fragment in markdown_anchors(target.read_text(encoding="utf-8")), f"Missing evidence heading: {evidence['path']}")
        manifest = load_json(local_target(study["manifest_path"]))
        require(manifest["source_commit"] == catalog["upstream_source"]["commit"], f"Source pin mismatch: {study['id']}")
        seen = set()
        for entry in manifest["files"]:
            rel = PurePosixPath(entry["path"])
            require(not rel.is_absolute() and ".." not in rel.parts, f"Unsafe manifest path: {rel}")
            require(entry["path"] not in seen, f"Duplicate manifest entry: {rel}")
            seen.add(entry["path"])
            target = local_target(str(rel), directory)
            require(target.is_file(), f"Missing included file: {study['id']}/{rel}")
            data = target.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            require(len(data) == entry["bytes"], f"Size mismatch: {study['id']}/{rel}")
            require(digest == entry["sha256"], f"SHA-256 mismatch: {study['id']}/{rel}")
            if "original_sha256" in entry:
                require(digest == entry["original_sha256"], f"Original-source bytes changed: {study['id']}/{rel}")
                preserved_source_files += 1
            checked_hashes += 1
        actual = {
            str(p.relative_to(directory).as_posix()) for p in directory.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts
            and p.name != "PUBLICATION_MANIFEST.json"
        }
        require(actual == seen, f"Manifest coverage mismatch in {study['id']}: missing={sorted(actual-seen)}, stale={sorted(seen-actual)}")
        log = local_target(study["tests_path"]).read_text(encoding="utf-8")
        match = re.search(r"Ran (\d+) tests", log)
        require(match is not None and re.search(r"(?m)^OK\s*$", log) is not None, f"Missing recorded successful test log: {study['id']}")
        count = int(match.group(1))
        require(count == study["recorded_publication_test_executions"], f"Test count mismatch: {study['id']}")
        test_executions += count
        docs.update([report, local_target(study["landing_path"]), local_target(study["guide_path"])])
    checked_links = sum(check_links(path) for path in sorted(docs))
    bib = (ROOT / "experiments/CITATIONS.bib").read_text(encoding="utf-8")
    require(len(re.findall(r"(?m)^@misc\{", bib)) == 7, "Expected seven BibTeX report citations")
    for study in studies:
        require("@misc{" + study["citation_key"] + "," in bib, f"Missing citation: {study['id']}")
        require(study["report_permalink"] in bib, f"Missing fixed citation URL: {study['id']}")
    require(test_executions == 59, "Historical test execution count changed")
    print(json.dumps({
        "status": "passed",
        "experiments": len(studies),
        "manifest_file_hashes_checked": checked_hashes,
        "original_source_file_hashes_preserved": preserved_source_files,
        "documentation_files_checked": len(docs),
        "relative_links_checked": checked_links,
        "historical_test_executions": test_executions,
        "includes_repeated_sampler_tests": True,
        "new_benchmarks_run": False,
        "independent_peer_review_or_replication_certified": False,
    }, indent=2))


if __name__ == "__main__":
    try:
        verify()
    except (PublicationError, KeyError, ValueError, OSError) as exc:
        print("Publication integrity check failed: " + str(exc), file=sys.stderr)
        sys.exit(1)

