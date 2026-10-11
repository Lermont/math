import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def test_file_round_trip_with_binary_duplicates_and_empty(self):
        root = Path(__file__).resolve().parents[1]
        values = [b"banana", b"ananas", b"", b"\x00\xffa", b"banana"]
        expected = dict(encoding="base64", strings=[base64.b64encode(v).decode() for v in values])
        with tempfile.TemporaryDirectory(prefix="stringpack-test-") as directory:
            p = Path(directory)
            (p/"input.json").write_text(json.dumps(expected), encoding="utf-8")
            command = [sys.executable, "-m", "stringpack"]
            subprocess.run(command+["pack", str(p/"input.json"), str(p/"data.spk")],
                           cwd=root, check=True, capture_output=True)
            subprocess.run(command+["unpack", str(p/"data.spk"), str(p/"restored.json")],
                           cwd=root, check=True, capture_output=True)
            self.assertEqual(json.loads((p/"restored.json").read_text()), expected)
            result = subprocess.run(command+["get", str(p/"data.spk"), "3"],
                                    cwd=root, check=True, capture_output=True, text=True)
            self.assertEqual(base64.b64decode(json.loads(result.stdout)["base64"]), values[3])
