"""Reproducible in-memory CPU/storage benchmark, with full saved archives."""
from __future__ import annotations

import argparse
import base64
import csv
import gc
import hashlib
import json
import math
import os
import platform
import random
import statistics
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from compression import zstd
from .datasets import corpora
from .paper128 import ResourceLimit
from .storage import METHODS, Reader, pack


def measure(fn, repeats, target_seconds=0.025):
    """Warm calibration, then a fixed batch size for each measured repeat."""
    t = perf_counter()
    fn()
    estimate = max(perf_counter()-t, 1e-7)
    loops = max(1, min(10000, math.ceil(target_seconds/estimate)))
    samples = []
    for _ in range(repeats):
        gc.collect()
        enabled = gc.isenabled()
        gc.disable()
        try:
            t = perf_counter()
            for _ in range(loops):
                fn()
            samples.append((perf_counter()-t)/loops)
        finally:
            if enabled:
                gc.enable()
    return dict(median=statistics.median(samples), minimum=min(samples),
                maximum=max(samples), samples=samples, batch_loops=loops)


def dataset_hash(strings):
    h = hashlib.sha256()
    for s in strings:
        h.update(struct.pack("<I", len(s)))
        h.update(s)
    return h.hexdigest()


def save_data(path, strings):
    path.write_text(json.dumps(dict(encoding="base64", strings=[base64.b64encode(s).decode("ascii")
                                                               for s in strings]), indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=None)
    parser.add_argument("--datasets", nargs="*", default=None)
    parser.add_argument("--methods", nargs="*", choices=list(METHODS), default=list(METHODS))
    parser.add_argument("--seed", type=int, default=1282026)
    parser.add_argument("--pack-repeats", type=int, default=3)
    parser.add_argument("--read-repeats", type=int, default=5)
    parser.add_argument("--queries", type=int, default=4096)
    parser.add_argument("--max-vertices", type=int, default=20000)
    parser.add_argument("--max-paper-seconds", type=float, default=20)
    parser.add_argument("--prefix-block", type=int, default=16)
    parser.add_argument("--zstd-block", type=int, default=32)
    parser.add_argument("--zstd-level", type=int, default=3)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = Path(args.output or ("results/"+now.strftime("%Y%m%dT%H%M%SZ")))
    output.mkdir(parents=True, exist_ok=True)
    env = dict(timestamp_utc=now.isoformat(), python=sys.version, executable=sys.executable,
               platform=platform.platform(), processor=platform.processor(),
               logical_cpus=os.cpu_count(), zstd_version=zstd.zstd_version)
    settings = vars(args).copy()
    settings.update(input_resident_in_ram=True, file_io_timed=False, decoded_cache=False,
                    random_trace="uniform with replacement, fixed shared trace",
                    full_read="materialize every string in original ID order",
                    timer="time.perf_counter, GC disabled only within timed batches")
    result = dict(environment=env, settings=settings, datasets=[], rows=[])
    selected = [d for d in corpora(args.seed) if not args.datasets or d["id"] in args.datasets]
    if args.datasets and set(args.datasets) != {d["id"] for d in selected}:
        parser.error("unknown dataset")
    for number, dataset in enumerate(selected):
        strings = dataset["strings"]
        info = {k:v for k,v in dataset.items() if k != "strings"}
        info.update(count=len(strings), unique_count=len(set(strings)), raw_bytes=sum(map(len,strings)),
                    min_length=min(map(len,strings),default=0), max_length=max(map(len,strings),default=0),
                    sha256=dataset_hash(strings))
        # Derive each trace from its name; selecting a subset does not change it.
        query_seed = int.from_bytes(hashlib.sha256((str(args.seed)+dataset["id"]).encode()).digest()[:8],"little")
        rng = random.Random(query_seed)
        trace = [rng.randrange(len(strings)) for _ in range(args.queries)] if strings else []
        info["trace_sha256"] = hashlib.sha256(struct.pack(f"<{len(trace)}I", *trace)).hexdigest()
        result["datasets"].append(info)
        directory = output/dataset["id"]
        directory.mkdir(exist_ok=True)
        save_data(directory/"input.json", strings)
        (directory/"trace.json").write_text(json.dumps(trace), encoding="utf-8")
        print(f"DATASET {dataset['id']} n={len(strings)} bytes={info['raw_bytes']}", flush=True)
        # Stable shuffled method order reduces fixed ordering effects.
        methods = list(args.methods)
        random.Random(query_seed ^ 777).shuffle(methods)
        for method in methods:
            row = dict(dataset=dataset["id"], method=method)
            kwargs = dict(prefix_block=args.prefix_block, zstd_block=args.zstd_block, level=args.zstd_level,
                          max_vertices=args.max_vertices, max_seconds=args.max_paper_seconds)
            started = perf_counter()
            try:
                blob, stats = pack(strings, method, **kwargs)
                reader = Reader(blob)
                assert reader.read_all() == strings
                assert [reader.read(i) for i in range(len(strings))] == strings
                (directory/(method+".spk")).write_bytes(blob)
                row.update(status="ok", archive_sha256=hashlib.sha256(blob).hexdigest(), **stats)
                row["pack_time"] = measure(lambda: pack(strings,method,**kwargs), args.pack_repeats)
                row["open_time"] = measure(lambda: Reader(blob), args.read_repeats)

                def random_read_batch():
                    total = 0
                    for i in trace:
                        total += len(reader.read(i))
                    return total

                row["random_batch_time"] = measure(random_read_batch, args.read_repeats)
                row["full_read_time"] = measure(reader.read_all, args.read_repeats)
                row["pack_ms"] = row["pack_time"]["median"]*1e3
                row["open_us"] = row["open_time"]["median"]*1e6
                row["random_us"] = row["random_batch_time"]["median"]*1e6/max(1,len(trace))
                row["full_read_ms"] = row["full_read_time"]["median"]*1e3
                row["full_read_mib_s"] = info["raw_bytes"]/2**20/row["full_read_time"]["median"]
                print(f"  {method:12} {len(blob):7} B pack={row['pack_ms']:.3f} ms "
                      f"get={row['random_us']:.3f} us full={row['full_read_ms']:.3f} ms", flush=True)
            except ResourceLimit as exc:
                row.update(status="resource_limit", reason=str(exc), elapsed_seconds=perf_counter()-started)
                print(f"  {method}: LIMIT {exc}", flush=True)
            except Exception as exc:
                # Do not silently downgrade to another algorithm.
                row.update(status="error", reason=f"{type(exc).__name__}: {exc}")
                result["rows"].append(row)
                (output/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
                raise
            result["rows"].append(row)
            (output/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    fields = ["dataset","method","status","total_bytes","payload_bytes","index_bytes","header_bytes",
              "pack_ms","open_us","random_us","full_read_ms","full_read_mib_s","reason"]
    with (output/"results.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["rows"])
    print("RESULTS", output.resolve(), flush=True)


if __name__ == "__main__":
    main()
