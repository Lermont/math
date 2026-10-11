"""Bounded-memory full scan of the official background ZIP, no pickle loading."""
from __future__ import annotations

import hashlib
import io
import json
import struct
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import requests
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/elliptic2-context'
RAW = ROOT / 'results/elliptic2/raw'
URL = 'https://www.kaggle.com/api/v1/datasets/download/ellipticco/elliptic2-data-set/background_edges.csv?datasetVersionNumber=1'
SEED = 1312027


def select():
    OUT.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(RAW / 'connected_components.csv')
    old = {r['id'] for r in json.loads((RAW.parent / 'sample.json').read_text())}
    eligible = labels[~labels.ccId.isin(old)].copy()
    ids = eligible.ccId.to_numpy()
    ys = (eligible.ccLabel == 'suspicious').to_numpy(dtype=int)
    keep, _ = train_test_split(np.arange(len(ids)), train_size=6000, stratify=ys, random_state=SEED)
    train, rest = train_test_split(keep, test_size=.6, stratify=ys[keep], random_state=SEED+1)
    val, test = train_test_split(rest, test_size=2/3, stratify=ys[rest], random_state=SEED+2)
    records = [{'id': int(ids[i]), 'y': int(ys[i]), 'split': s} for s, inds in [('train',train),('val',val),('test',test)] for i in inds]
    records.sort(key=lambda r:r['id'])
    (OUT / 'selection.json').write_text(json.dumps(records, separators=(',',':')))
    pd.DataFrame(records).to_csv(OUT/'selection.csv',index=False)
    selected = pd.read_csv(RAW / 'nodes.csv')
    selected = selected[selected.ccId.isin([r['id'] for r in records])]
    selected.to_csv(OUT/'selected-nodes.csv',index=False)
    return selected.clId.to_numpy(dtype=np.uint32)


class DeflatedRanges(io.RawIOBase):
    """Parallel compressed range fetch, ordered decompression and CRC validation."""
    def __init__(self, url, archive_size, offset, compressed, expected_size, crc):
        super().__init__()
        self.url, self.archive_size = url, archive_size
        self.offset, self.compressed = offset, compressed
        self.expected_size, self.expected_crc = expected_size, crc
        self.size = 16 * 2**20
        self.parts = (compressed + self.size - 1)//self.size
        self.pool = ThreadPoolExecutor(max_workers=6)
        self.pending = {}
        self.part = self.scheduled = 0
        self.decoder = zlib.decompressobj(-15)
        self.buffer = b''
        self.buffer_pos = 0
        self.crc = self.raw_bytes = self.download_bytes = 0
        self.sha = hashlib.sha256()
        self.finished = False
        self._fill()

    def _fetch(self, i):
        start = self.offset + i*self.size
        end = min(self.offset+self.compressed, start+self.size)-1
        for attempt in range(5):
            try:
                r=requests.get(self.url,headers={'Range':f'bytes={start}-{end}'},timeout=(30,120))
                r.raise_for_status()
                if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {start}-{end}/{self.archive_size}' or len(r.content) != end-start+1:
                    raise ValueError('Incorrect HTTP range response')
                return r.content
            except (requests.RequestException,ValueError):
                if attempt==4: raise
                time.sleep(2**attempt)

    def _fill(self):
        while self.scheduled < self.parts and len(self.pending)<8:
            i=self.scheduled
            self.pending[i]=self.pool.submit(self._fetch,i)
            self.scheduled+=1

    def readable(self): return True

    def readinto(self, dest):
        if self.buffer_pos == len(self.buffer):
            if self.part == self.parts:
                if not self.finished:
                    assert self.decoder.eof
                    assert self.raw_bytes == self.expected_size, (self.raw_bytes,self.expected_size)
                    assert self.crc == self.expected_crc, (self.crc,self.expected_crc)
                    self.finished=True
                    self.pool.shutdown(wait=True)
                return 0
            compressed=self.pending.pop(self.part).result()
            self.part+=1
            self._fill()
            self.download_bytes+=len(compressed)
            self.buffer=self.decoder.decompress(compressed)
            self.buffer_pos=0
            self.sha.update(self.buffer)
            self.crc=zlib.crc32(self.buffer,self.crc)
            self.raw_bytes+=len(self.buffer)
        n=min(len(dest),len(self.buffer)-self.buffer_pos)
        dest[:n]=self.buffer[self.buffer_pos:self.buffer_pos+n]
        self.buffer_pos+=n
        return n


def scan():
    started=time.perf_counter()
    targets=select()
    rawout=OUT/'raw';rawout.mkdir(exist_ok=True)
    result=rawout/'incident-edges.csv'
    if result.exists(): raise FileExistsError('Refusing to overwrite a previous acquisition')
    response=requests.get(URL,stream=True,timeout=90);response.raise_for_status()
    url=response.url
    archive_size=int(response.headers['Content-Length'])
    head=response.raw.read(4096);response.close()
    assert head[:4]==b'PK\x03\x04'
    flags,method=struct.unpack_from('<HH',head,6)
    assert method==8 and not (flags & 8), 'Need known deflate entry sizes'
    crc=struct.unpack_from('<I',head,14)[0]
    name_len,extra_len=struct.unpack_from('<HH',head,26)
    assert head[30:30+name_len]==b'background_edges.csv'
    extra=head[30+name_len:30+name_len+extra_len]
    assert struct.unpack_from('<HH',extra)==(1,16)
    raw_size,compressed=struct.unpack_from('<QQ',extra,4)
    stream=DeflatedRanges(url,archive_size,30+name_len+extra_len,compressed,raw_size,crc)
    rows=hits=0
    last=0
    print(json.dumps({'phase':'scan_started','targets':len(targets),'archive_bytes':archive_size,'raw_bytes':raw_size}),flush=True)
    with result.open('w',encoding='utf-8',newline='') as f:
        f.write('clId1,clId2,txId\n')
        with io.BufferedReader(stream,buffer_size=2**20) as reader:
            for chunk in pd.read_csv(reader,usecols=[0,1,2],dtype=np.uint32,chunksize=200000):
                mask=chunk.clId1.isin(targets)|chunk.clId2.isin(targets)
                chosen=chunk[mask]
                chosen.to_csv(f,index=False,header=False)
                rows+=len(chunk);hits+=len(chosen)
                elapsed=time.perf_counter()-started
                if elapsed-last>30:
                    status={'phase':'scan','rows':rows,'hits':hits,'compressed_GB':round(stream.download_bytes/1e9,3),'percent':round(stream.download_bytes/compressed*100,2),'seconds':round(elapsed,1)}
                    (OUT/'acquisition-progress.json').write_text(json.dumps(status))
                    print(json.dumps(status),flush=True);last=elapsed
    assert stream.finished
    audit={'source_url':URL,'version':1,'archive_bytes':archive_size,'compressed_entry_bytes':compressed,'uncompressed_bytes':stream.raw_bytes,'crc32':f'{stream.crc:08x}','crc_verified':True,'source_csv_sha256':stream.sha.hexdigest(),'rows_scanned':rows,'incident_rows_retained':hits,'selected_core_nodes':len(targets),'elapsed_seconds':time.perf_counter()-started,'peak_rss_mib':psutil.Process().memory_info().peak_wset/2**20,'retained_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),'selection_sha256':hashlib.sha256((OUT/'selection.json').read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256((ROOT/'graph131/CONTEXT_PLAN.md').read_bytes()).hexdigest()}
    (OUT/'acquisition.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit),flush=True)


if __name__=='__main__': scan()
