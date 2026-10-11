"""Small file-oriented interface to the prototype."""
import argparse
import base64
import json
from pathlib import Path

from .storage import METHODS, Reader, pack


def main():
    parser = argparse.ArgumentParser(description="Indexed string archives, Python 3.14+")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("pack", help="JSON string list or base64 dataset -> SPK archive")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--method", choices=list(METHODS), default="paper128")
    p.add_argument("--max-vertices", type=int, default=20000)
    p.add_argument("--max-seconds", type=float, default=20)
    p = commands.add_parser("unpack", help="SPK archive -> base64 JSON in original order")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--text", action="store_true", help="UTF-8 JSON string list instead of base64")
    p = commands.add_parser("get", help="Read a string by its original zero-based ID")
    p.add_argument("input", type=Path)
    p.add_argument("id", type=int)
    p = commands.add_parser("info")
    p.add_argument("input", type=Path)
    args = parser.parse_args()
    if args.command == "pack":
        obj = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if isinstance(obj, list) and all(isinstance(s, str) for s in obj):
            strings = [s.encode("utf-8") for s in obj]
        elif isinstance(obj, dict) and obj.get("encoding") == "base64":
            strings = [base64.b64decode(s, validate=True) for s in obj["strings"]]
        else:
            parser.error("expected a JSON string list or {encoding: base64, strings: [...]}")
        blob, stats = pack(strings, args.method, max_vertices=args.max_vertices, max_seconds=args.max_seconds)
        if Reader(blob).read_all() != strings:
            raise AssertionError("round trip failed")
        args.output.write_bytes(blob)
        print(json.dumps(stats, indent=2))
    else:
        blob = args.input.read_bytes()
        reader = Reader(blob)
        if args.command == "get":
            value = reader.read(args.id)
            result = dict(id=args.id, bytes=len(value), base64=base64.b64encode(value).decode("ascii"))
            try:
                result["text"] = value.decode("utf-8")
            except UnicodeDecodeError:
                pass
            print(json.dumps(result, ensure_ascii=True))
        elif args.command == "unpack":
            strings = reader.read_all()
            result = ([s.decode("utf-8") for s in strings] if args.text else
                      dict(encoding="base64",strings=[base64.b64encode(s).decode("ascii") for s in strings]))
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(json.dumps(dict(method=reader.method, strings=len(reader), bytes=len(blob),
                                  block_size=reader.block_size, blocks=reader.blocks), indent=2))


if __name__ == "__main__":
    main()
