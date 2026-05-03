# PoC-4: Memory Engine Spike (sqlite-vec)

> Verifies the memory-engine foundation: SQLite + sqlite-vec works at scale,
> with our 384-dim BGE-small-zh embedding shape, on plain Python.
>
> What this **does NOT** verify: React Native native module integration.
> That is a separate spike that must run on an actual Android device
> (we cannot do that here — no Android SDK on this Linux dev box).
>
> But: if sqlite-vec itself works on a 1k-row workload here, the underlying
> engine is sound. The RN integration risk reduces to "writing the JNI/TS
> binding correctly", not "the engine fundamentally works".

## Why this PoC matters (engineering plan §1.6 + §3 PoC-4)

The memory engine is the spine of philosophy bullet #1 ("AI 主动获取上下文,
用户只说'当下'"). Without a working vector retriever:
  - cross-scenario RAG is impossible
  - persona/event recall degrades to keyword matching
  - the product becomes "豆包 with extra steps"

If sqlite-vec doesn't work, we fall back to ObjectBox (4 person-days switch).
We need to know **today** which path we're on.

## Validation criteria (mirrors §3 PoC-4)

| Metric | Target | Actual (latest run) |
|---|---|---|
| Write 1000 entries  | < 1 s   | filled by `run.py` |
| Top-5 vector lookup | < 50 ms | filled by `run.py` |
| Embedding dim       | 384     | hardcoded         |
| Memory footprint    | < 50 MB | informational     |

## Run

```bash
cd poc/poc-4-memory-engine
python3 -m venv --without-pip .venv
.venv/bin/python3 /tmp/get-pip.py     # one-time
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
.venv/bin/python3 run.py
```

## Outcome interpretation

- **All targets pass** → proceed with sqlite-vec in app/src/core/memory/db.ts
  (write the RN native module wrapper next)
- **Top-5 > 50 ms** → still OK if < 100 ms; otherwise reduce embedding dim or
  switch to ObjectBox
- **Crash on extension load** → switch to ObjectBox immediately

## File map

- `run.py`     — entry script, runs the full validation
- `schema.sql` — minimal schema mirroring `app/src/core/memory/schema.sql`
                 (which doesn't exist yet — this is the source-of-truth draft)
