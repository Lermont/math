"""Audit source hashes, actual baseline wheels and the frozen benchmark code."""
from __future__ import annotations
import hashlib
import json
import sys
import zipfile
from pathlib import Path
import importlib.metadata
import onebatch.onebatchpam as ob
import scipy.optimize._highspy._core as highs
from kmedian125.data import ROOT, digest, write_json

def main():
    refs = ROOT/"references/kmedian125"
    manifest = json.loads((refs/"sources.json").read_text())
    source_checks = []
    for entry in manifest["files"]:
        actual = digest(ROOT/entry["path"])
        assert actual == entry["sha256"], entry["path"]
        source_checks.append(dict(path=entry["path"], sha256=actual))
    installed = Path(ob.__file__).resolve().parents[1]
    wheel_checks = []
    for wheel in sorted((refs/"wheels").glob("*.whl")):
        prefix = "onebatch/" if wheel.name.startswith("onebatch-") else "kmedoids/"
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if name.startswith(prefix) and name.endswith((".py", ".pyd", ".pyx")):
                    data = z.read(name)
                    local = installed/name
                    assert local.read_bytes() == data, name
                    wheel_checks.append(dict(wheel=wheel.name, path=name, sha256=hashlib.sha256(data).hexdigest()))
    run = ROOT/"results/kmedian125/pilot-20261011-v1"
    env = json.loads((run/"environment.json").read_text())
    assert env["sources_manifest_sha256"] == digest(refs/"sources.json")
    frozen = []
    for name, expected in env["source_sha256"].items():
        assert digest(run/"source-snapshot"/name) == expected
        assert digest(ROOT/"kmedian125"/name) == expected, "benchmark input modified: "+name
        frozen.append(name)
    metadata = dict(source_count=len(source_checks), source_checks=source_checks,
                    wheel_member_checks=wheel_checks, frozen_inputs_unchanged=frozen,
                    onebatch_github_vs_wheel_text_equal=(Path(ob.__file__).read_text() == (refs/"onebatch/onebatch/onebatchpam.py").read_text()),
                    onebatch_github_sha256=digest(refs/"onebatch/onebatch/onebatchpam.py"),
                    onebatch_installed_sha256=digest(ob.__file__),
                    onebatch_hash_difference="CRLF/LF only; normalized text identical",
                    highs_version=".".join(str(getattr(highs,"HIGHS_VERSION_"+part)) for part in ("MAJOR","MINOR","PATCH")),
                    package_license={name: importlib.metadata.metadata(name).get("License") for name in ("kmedoids","onebatch")},
                    current_code_sha256={p.name:digest(p) for p in sorted((ROOT/"kmedian125").glob("*.py"))})
    write_json(ROOT/"results/kmedian125/provenance-audit.json", metadata)
    print(json.dumps({k: metadata[k] for k in ("source_count","frozen_inputs_unchanged","onebatch_github_vs_wheel_text_equal","highs_version")}, indent=2))

if __name__ == "__main__":
    main()
