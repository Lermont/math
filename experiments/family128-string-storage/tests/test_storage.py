import random
import unittest

from stringpack.storage import METHODS, Reader, pack


class StorageTests(unittest.TestCase):
    def test_round_trip_and_size_accounting(self):
        rng = random.Random(2026)
        cases = [[], [b""], [b"", b"x", b"x", b""],
                 [s.encode() for s in ["кот", "отпуск", "пуск", "🙂кот", "кот"]],
                 [bytes(range(32)), b"\x00\xff", b"\xff\x00"],
                 [bytes(rng.choices(b"abc\x00\xff", k=rng.randrange(20))) for _ in range(67)]]
        for method in METHODS:
            for strings in cases:
                with self.subTest(method=method, strings=len(strings)):
                    blob, stats = pack(strings, method, prefix_block=3, zstd_block=4)
                    reader = Reader(blob)
                    self.assertEqual(len(reader), len(strings))
                    self.assertEqual(reader.read_all(), strings)
                    self.assertEqual([reader.read(i) for i in range(len(strings))], strings)
                    self.assertEqual(len(blob), stats["total_bytes"])
                    self.assertEqual(len(blob), stats["header_bytes"] + stats["index_bytes"] + stats["payload_bytes"])
                    with self.assertRaises(IndexError):
                        reader.read(len(strings))
                    with self.assertRaises(IndexError):
                        reader.read(-1)

    def test_reject_unknown_and_truncated_archives(self):
        for data in (b"", b"SPK1", b"x"*24):
            with self.assertRaises(ValueError):
                Reader(data)
        blob, _ = pack([b"one", b"two"], "plain")
        with self.assertRaises(ValueError):
            Reader(blob[:-1])


if __name__ == "__main__":
    unittest.main()
