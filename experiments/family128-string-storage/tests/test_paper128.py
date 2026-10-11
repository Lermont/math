import itertools
import random
import unittest
from collections import Counter

from stringpack.paper128 import ResourceLimit, pack_superstring


def exact_length(strings):
    """Independent subset-DP oracle, exponential and for tiny tests only."""
    unique = set(strings) - {b""}
    words = sorted(s for s in unique if not any(s != t and s in t for t in unique))
    if not words:
        return 0
    n = len(words)
    overlap = [[0] * n for _ in words]
    for i, a in enumerate(words):
        for j, b in enumerate(words):
            if i != j:
                overlap[i][j] = max(k for k in range(min(len(a), len(b))+1)
                                    if a[len(a)-k:] == b[:k])
    dp = {(1 << i, i): len(s) for i, s in enumerate(words)}
    for mask in range(1, 1 << n):
        for last in range(n):
            if (mask, last) not in dp:
                continue
            for nxt in range(n):
                if not mask & (1 << nxt):
                    key = mask | (1 << nxt), nxt
                    cost = dp[mask, last] + len(words[nxt]) - overlap[last][nxt]
                    dp[key] = min(dp.get(key, cost), cost)
    return min(dp[(1 << n)-1, i] for i in range(n))


class Paper128Tests(unittest.TestCase):
    def check_case(self, strings):
        result, stats = pack_superstring(strings, max_vertices=20000)
        opt = exact_length(strings)
        self.assertTrue(all(s in result for s in strings))
        self.assertLessEqual(stats["lower_bound"], opt)
        self.assertLessEqual(len(result), 2 * opt)
        self.assertGreaterEqual(len(result), opt)
        return stats

    def test_exhaustive_binary_up_to_four_words_length_three(self):
        words = [bytes(x) for n in range(1, 4)
                 for x in itertools.product(b"ab", repeat=n)]
        cases = 0
        for n in range(5):
            for subset in itertools.combinations(words, n):
                self.check_case(list(subset))
                cases += 1
        self.assertEqual(cases, 1471)

    def test_random_against_exact_oracle(self):
        rng = random.Random(128)
        branches = Counter()
        for _ in range(250):
            alphabet = rng.choice([b"ab", b"abc", b"abcdef"])
            strings = [bytes(rng.choices(alphabet, k=rng.randint(1, 18)))
                       for _ in range(rng.randint(1, 7))]
            stats = self.check_case(strings)
            branches.update(stats["branch_counts"])
        self.assertGreater(branches["easy_root"], 0)

    def test_periods_duplicates_empty_and_binary(self):
        for strings in [[], [b"", b""], [b"aaaa"], [b"ababa", b"babab"],
                        [b"abcabcabc", b"bcabcabca", b"cabcabcab"],
                        [b"\x00\xffa", b"\xffab", b"\x00\xffa", b"", b"a"],
                        [s.encode() for s in ["кот", "отпуск", "пуск", "кот", ""]]]:
            with self.subTest(strings=strings):
                self.check_case(strings)

    def test_intermediate_length_blocker_regression(self):
        # B_A(w) must include counts fixed after the longer trigger v.
        self.check_case([b'babbb', b'bbbabaabbb', b'bbbabbbaba',
                         b'babbaaaaabbaaab', b'abaabaab'])

    def test_collective_connection_against_exact_oracle(self):
        strings = [bytes.fromhex(s) for s in [
            "626162626261616162616161626261626161626162",
            "6161616262626162626262626262616161616162616161",
            "616261626262",
            "62626162616261626261616262626261616261616161626262616261",
            "626261626161616262626162616162626262626262626162"]]
        stats = self.check_case(strings)
        self.assertGreater(stats["branch_counts"].get("collective", 0), 0)

    def test_deterministic_and_limit_is_explicit(self):
        words = [b"banana", b"ananas", b"nasty"]
        first, _ = pack_superstring(words)
        second, _ = pack_superstring(list(reversed(words)))
        self.assertEqual(first, second)
        with self.assertRaises(ResourceLimit):
            pack_superstring([b"abcdefghij"], max_vertices=10)
        with self.assertRaises(TypeError):
            pack_superstring(["text"])


if __name__ == "__main__":
    unittest.main()
