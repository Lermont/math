"""Re-read saved inputs, archives and hashes independently of timed pack calls."""
import argparse
import base64
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stringpack.benchmark import dataset_hash
from stringpack.storage import Reader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    result = json.loads(args.results.read_text(encoding="utf-8"))
    directory = args.results.parent
    checked = 0
    for dataset in result["datasets"]:
        base = directory/dataset["id"]
        obj = json.loads((base/"input.json").read_text(encoding="utf-8"))
        strings = [base64.b64decode(s, validate=True) for s in obj["strings"]]
        assert dataset_hash(strings) == dataset["sha256"]
        assert len(strings) == dataset["count"]
        assert sum(map(len,strings)) == dataset["raw_bytes"]
        trace = json.loads((base/"trace.json").read_text())
        trace_hash = hashlib.sha256(struct.pack(f"<{len(trace)}I",*trace)).hexdigest()
        assert trace_hash == dataset["trace_sha256"]
        for row in result["rows"]:
            if row["dataset"] != dataset["id"] or row["status"] != "ok":
                continue
            blob = (base/(row["method"]+".spk")).read_bytes()
            assert len(blob) == row["total_bytes"] == sum(row[k] for k in ("header_bytes","index_bytes","payload_bytes"))
            assert hashlib.sha256(blob).hexdigest() == row["archive_sha256"]
            reader = Reader(blob)
            assert reader.read_all() == strings
            for i in {0,len(strings)//2,len(strings)-1}:
                if strings:
                    assert reader.read(i) == strings[i]
            checked += 1
    manifest = json.loads(Path("references/sources.json").read_text())
    for f in manifest["files"]:
        assert hashlib.sha256(Path(f["path"]).read_bytes()).hexdigest() == f["sha256"]
    report = dict(status="passed", datasets=len(result["datasets"]), saved_archives=checked,
                  upstream_files=len(manifest["files"]), checks=["dataset hashes", "trace hashes",
                  "archive sizes and hashes", "all original strings in original order",
                  "sampled ID reads", "pinned reference hashes"])
    (directory/"verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
