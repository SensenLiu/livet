# PoC-4 sqlite-vec spike — Report

- vec_version: (see stdout)
- Insert 1000 rows: **24.7 ms** (PASS ✓)
- Top-5 query (avg over 50): **0.29 ms** (p50=0.27 / p95=0.33; PASS ✓)
- DB size: 4.0 KB
- Schema: compiled OK
- Cross-table FK: works

**Overall verdict**: **PASS — proceed with sqlite-vec for memory engine.**

Tested on:
- Linux x86_64 dev box
- Python 3.8 + sqlite-vec 0.1.9 + numpy 1.24
- Synthetic 384-d unit vectors

**Caveat**: this does NOT validate React Native + Android JNI integration. That's a separate spike requiring an actual Android device.
