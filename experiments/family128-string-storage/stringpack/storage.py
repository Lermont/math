"""Self-contained indexed byte-string archives; all sizes include the index.

SPK1 is a research format, little-endian with uint32 offsets. Files larger
than 4 GiB are deliberately unsupported. Readers have no decoded-block cache.
"""
from __future__ import annotations

import struct
from compression import zstd

from .paper128 import pack_superstring

HEADER = struct.Struct("<4sBBHIII")
METHODS = {"plain": 1, "dedup": 2, "paper128": 3, "prefix": 4,
           "zstd_blocks": 5, "zstd_whole": 6}
NAMES = {v: k for k, v in METHODS.items()}
U32 = struct.Struct("<I")


def u32s(values):
    return struct.pack(f"<{len(values)}I", *values)


def varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return out


def read_varint(data, pos, end):
    result = 0
    for shift in range(0, 35, 7):
        if pos >= end:
            raise ValueError("truncated varint")
        b = data[pos]
        pos += 1
        result |= (b & 127) << shift
        if not b & 128:
            return result, pos
    raise ValueError("oversized varint")


def indexed_raw(strings):
    offsets = [0]
    for s in strings:
        offsets.append(offsets[-1] + len(s))
    return u32s(offsets), b"".join(strings)


def pack(strings, method, *, prefix_block=16, zstd_block=32, level=3,
         max_vertices=12000, max_seconds=None):
    if method not in METHODS:
        raise ValueError(f"unknown method: {method}")
    if any(not isinstance(s, bytes) for s in strings):
        raise TypeError("strings must be bytes")
    n, count, block_size = len(strings), 0, 0
    details = {}
    if method == "plain":
        index, payload = indexed_raw(strings)
    elif method in ("dedup", "paper128"):
        if method == "paper128":
            payload, details = pack_superstring(strings, max_vertices=max_vertices,
                                               max_seconds=max_seconds)
            positions = {s: payload.find(s) for s in set(strings)}
            assert all(p >= 0 for p in positions.values())
        else:
            positions, chunks, length = {}, [], 0
            for s in strings:
                if s not in positions:
                    positions[s] = length
                    chunks.append(s)
                    length += len(s)
            payload = b"".join(chunks)
        index = u32s([v for s in strings for v in (positions[s], len(s))])
    elif method == "prefix":
        if not 1 <= prefix_block <= 65535:
            raise ValueError("invalid prefix block size")
        block_size = prefix_block
        ordered = sorted(range(n), key=lambda i: strings[i])
        ranks = [0] * n
        offsets, chunks, length = [0], [], 0
        for first in range(0, n, block_size):
            chunk, previous = bytearray(), b""
            for rank in range(first, min(first + block_size, n)):
                original = ordered[rank]
                ranks[original] = rank
                s, common = strings[original], 0
                for a, b in zip(previous, s):
                    if a != b:
                        break
                    common += 1
                suffix = s[common:]
                chunk += varint(common) + varint(len(suffix)) + suffix
                previous = s
            chunks.append(chunk)
            length += len(chunk)
            offsets.append(length)
        count = len(chunks)
        index, payload = u32s(ranks) + u32s(offsets), b"".join(chunks)
    else:
        if not 1 <= zstd_block <= 65535:
            raise ValueError("invalid zstd block size")
        block_size = zstd_block if method == "zstd_blocks" else 0
        stride = block_size or max(n, 1)
        offsets, frames, length = [0], [], 0
        for first in range(0, n, stride):
            idx, data = indexed_raw(strings[first:first+stride])
            frame = zstd.compress(idx + data, level=level)
            frames.append(frame)
            length += len(frame)
            offsets.append(length)
        count = len(frames)
        index, payload = u32s(offsets), b"".join(frames)
        details = {"level": level, "zstd_version": zstd.zstd_version,
                   "inner_index": "uint32 string offsets, compressed inside frames"}
    payload_start = HEADER.size + len(index)
    if payload_start + len(payload) >= 2**32:
        raise ValueError("research format supports archives below 4 GiB")
    header = HEADER.pack(b"SPK1", METHODS[method], 0, block_size, n, count, payload_start)
    blob = header + index + payload
    stats = dict(method=method, count=n, input_bytes=sum(map(len, strings)),
                 total_bytes=len(blob), header_bytes=len(header), index_bytes=len(index),
                 payload_bytes=len(payload), block_size=block_size, blocks=count,
                 details=details)
    return blob, stats


class Reader:
    def __init__(self, blob):
        if len(blob) < HEADER.size:
            raise ValueError("truncated header")
        magic, kind, flags, self.block_size, self.n, self.blocks, start = HEADER.unpack_from(blob)
        if magic != b"SPK1" or flags or kind not in NAMES:
            raise ValueError("unknown archive format")
        if not HEADER.size <= start <= len(blob):
            raise ValueError("invalid payload offset")
        self.method = NAMES[kind]
        self.data = memoryview(blob)[start:]
        index = memoryview(blob)[HEADER.size:start]
        if self.method == "plain":
            size = 4 * (self.n+1)
        elif self.method in ("dedup", "paper128"):
            size = 8 * self.n
        elif self.method == "prefix":
            size = 4 * (self.n+self.blocks+1)
        else:
            size = 4 * (self.blocks+1)
        if len(index) != size:
            raise ValueError("invalid index size")
        self.index = struct.unpack(f"<{size//4}I", index)
        if self.method in ("dedup", "paper128"):
            if any(self.index[2*i]+self.index[2*i+1] > len(self.data) for i in range(self.n)):
                raise ValueError("string outside payload")
        else:
            offsets = self.index[self.n:] if self.method == "prefix" else self.index
            if offsets[0] != 0 or offsets[-1] != len(self.data) or any(a > b for a,b in zip(offsets, offsets[1:])):
                raise ValueError("invalid block offsets")
            self.offsets = offsets
            if self.method in ("prefix", "zstd_blocks", "zstd_whole"):
                if self.method != "zstd_whole" and self.block_size == 0:
                    raise ValueError("zero block size")
                stride = self.block_size or max(self.n, 1)
                if self.blocks != (self.n+stride-1)//stride:
                    raise ValueError("invalid block count")
            if self.method == "prefix" and sorted(self.index[:self.n]) != list(range(self.n)):
                raise ValueError("invalid ID permutation")

    def __len__(self):
        return self.n

    def _prefix_block(self, block, stop=None):
        pos, end = self.offsets[block], self.offsets[block+1]
        count = min(self.block_size, self.n-block*self.block_size)
        previous = b""
        for i in range(count if stop is None else stop+1):
            common, pos = read_varint(self.data, pos, end)
            length, pos = read_varint(self.data, pos, end)
            if common > len(previous) or pos+length > end:
                raise ValueError("invalid prefix record")
            previous = previous[:common] + bytes(self.data[pos:pos+length])
            pos += length
            yield previous

    def read(self, i):
        if not 0 <= i < self.n:
            raise IndexError(i)
        if self.method == "plain":
            return bytes(self.data[self.index[i]:self.index[i+1]])
        if self.method in ("dedup", "paper128"):
            pos, length = self.index[2*i:2*i+2]
            return bytes(self.data[pos:pos+length])
        if self.method == "prefix":
            rank = self.index[i]
            block, local = divmod(rank, self.block_size)
            value = b""
            for value in self._prefix_block(block, local):
                pass
            return value
        stride = self.block_size or self.n
        block, local = divmod(i, stride)
        raw = zstd.decompress(self.data[self.offsets[block]:self.offsets[block+1]])
        count = min(stride, self.n-block*stride)
        start, end = struct.unpack_from("<II", raw, 4*local)
        data_start = 4*(count+1)
        if data_start+end > len(raw) or start > end:
            raise ValueError("invalid decompressed string offsets")
        return raw[data_start+start:data_start+end]

    def read_all(self):
        if self.method in ("plain", "dedup", "paper128"):
            return [self.read(i) for i in range(self.n)]
        if self.method == "prefix":
            ordered = [s for block in range(self.blocks) for s in self._prefix_block(block)]
            return [ordered[self.index[i]] for i in range(self.n)]
        result = []
        stride = self.block_size or max(self.n, 1)
        for block in range(self.blocks):
            raw = zstd.decompress(self.data[self.offsets[block]:self.offsets[block+1]])
            count = min(stride, self.n-block*stride)
            offsets = struct.unpack_from(f"<{count+1}I", raw)
            data_start = 4*(count+1)
            if data_start+offsets[-1] != len(raw) or offsets[0] != 0 or any(a>b for a,b in zip(offsets, offsets[1:])):
                raise ValueError("invalid decompressed index")
            result.extend(raw[data_start+a:data_start+b] for a,b in zip(offsets, offsets[1:]))
        return result
