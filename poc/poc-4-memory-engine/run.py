"""PoC-4: Memory Engine spike (sqlite-vec).

Validates the foundation of the memory engine on plain Python:
  1. sqlite-vec extension loads on Linux (this dev box)
  2. We can store our 384-dim BGE-small-zh-shaped embeddings
  3. Top-5 vector lookup over 1000 rows is fast (<50 ms target)
  4. Schema from `schema.sql` actually compiles

If all 4 pass, the RN integration risk reduces to "wire JNI binding correctly",
which is a known engineering effort, not an unknown.

Output: a written `report.md` in the same directory.
"""
from __future__ import annotations

import sqlite3
import struct
import time
import uuid
from pathlib import Path

import numpy as np
import sqlite_vec

HERE = Path(__file__).parent
DB_PATH = HERE / "spike.db"
SCHEMA_PATH = HERE / "schema.sql"
REPORT_PATH = HERE / "report.md"

EMBEDDING_DIM = 384   # mirrors §1.7 BGE-small-zh ONNX 384-d decision
N_ROWS = 1000         # mirrors §3 PoC-4 validation criterion
TOP_K = 5
N_QUERIES = 50        # we average top-k latency over this many queries


def fresh_db() -> sqlite3.Connection:
    """Open a fresh DB file with sqlite-vec loaded."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    # vec0 virtual table must be created in code (not in schema.sql) since
    # it depends on the loaded extension at session time
    conn.execute("CREATE VIRTUAL TABLE events_vec USING vec0(embedding float[384])")


def vec_to_blob(v: np.ndarray) -> bytes:
    """sqlite-vec stores float[D] as packed little-endian float32."""
    assert v.dtype == np.float32 and v.shape == (EMBEDDING_DIM,)
    return struct.pack(f"{EMBEDDING_DIM}f", *v.tolist())


def synthesize_corpus(n: int, rng: np.random.Generator):
    """Generate n synthetic events with random 384-d unit vectors."""
    embs = rng.standard_normal((n, EMBEDDING_DIM)).astype(np.float32)
    embs /= np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return embs


def main() -> None:
    print("=" * 60)
    print("LiveT — PoC-4: Memory Engine spike (sqlite-vec)")
    print("=" * 60)

    conn = fresh_db()
    print(f"\n  sqlite-vec loaded successfully (db={DB_PATH.name})")
    cur = conn.execute("SELECT vec_version()")
    print(f"  vec_version: {cur.fetchone()[0]}")

    # --- Schema apply ---
    t0 = time.time()
    apply_schema(conn)
    print(f"  schema.sql compiled in {(time.time() - t0) * 1000:.1f} ms")

    # --- Corpus + insert benchmark ---
    rng = np.random.default_rng(42)
    embs = synthesize_corpus(N_ROWS, rng)
    print(f"\n  Generating {N_ROWS} synthetic 384-d unit vectors... done")

    # Insert into events + events_vec, in a single tx
    t0 = time.time()
    with conn:
        for i, e in enumerate(embs):
            eid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO events (id, at, title, importance, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                (eid, "2026-05-03T10:00:00+08:00", f"event#{i}", "mid", "high"),
            )
            conn.execute(
                "INSERT INTO events_vec (rowid, embedding) VALUES (?, ?)",
                (i, vec_to_blob(e)),
            )
    insert_ms = (time.time() - t0) * 1000
    insert_pass = insert_ms < 1000
    print(f"  Insert {N_ROWS} rows: {insert_ms:.1f} ms "
          f"({'✓ PASS' if insert_pass else '✗ FAIL'} target <1000ms)")

    # --- Top-K query benchmark ---
    query_embs = synthesize_corpus(N_QUERIES, rng)
    latencies = []
    for q in query_embs:
        t0 = time.time()
        rows = conn.execute(
            "SELECT rowid, distance "
            "FROM events_vec "
            "WHERE embedding MATCH ? AND k = ? "
            "ORDER BY distance",
            (vec_to_blob(q), TOP_K),
        ).fetchall()
        latencies.append((time.time() - t0) * 1000)
    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    query_pass = avg < 50
    print(f"  Top-{TOP_K} over {N_ROWS} rows: avg={avg:.2f}ms p50={p50:.2f}ms p95={p95:.2f}ms "
          f"({'✓ PASS' if query_pass else '✗ FAIL'} target <50ms)")
    print(f"  Last query returned {len(rows)} rows; closest distance={rows[0][1]:.3f}")

    # --- Footprint ---
    db_kb = DB_PATH.stat().st_size / 1024
    print(f"  DB on-disk size: {db_kb:.1f} KB ({db_kb/1024:.2f} MB)")

    # --- Cross-table sanity: insert a person, link via events =====
    pid = str(uuid.uuid4())
    eid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO persons (id, name, role, traits_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (pid, "张总", "B 公司项目负责人", '{"关注点":["预算","ROI"]}',
             "2026-05-03T10:00:00+08:00"),
        )
        conn.execute(
            "INSERT INTO events (id, at, title, importance, confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (eid, "2026-05-03T11:00:00+08:00",
             "与张总会议讨论 100 万方案", "high", "high"),
        )
        conn.execute("INSERT INTO event_persons (event_id, person_id) VALUES (?, ?)",
                     (eid, pid))
    rows = conn.execute(
        "SELECT e.title, p.name FROM events e "
        "JOIN event_persons ep ON ep.event_id = e.id "
        "JOIN persons p ON p.id = ep.person_id "
        "WHERE p.id = ?",
        (pid,),
    ).fetchall()
    print(f"  Cross-table FK lookup: {len(rows)} row(s); first: {rows[0]}")

    # --- Write report.md =====
    report = (
        "# PoC-4 sqlite-vec spike — Report\n\n"
        f"- vec_version: {cur.fetchone() or '(see stdout)'}\n"
        f"- Insert {N_ROWS} rows: **{insert_ms:.1f} ms** "
        f"({'PASS ✓' if insert_pass else 'FAIL ✗'})\n"
        f"- Top-{TOP_K} query (avg over {N_QUERIES}): **{avg:.2f} ms** "
        f"(p50={p50:.2f} / p95={p95:.2f}; "
        f"{'PASS ✓' if query_pass else 'FAIL ✗'})\n"
        f"- DB size: {db_kb:.1f} KB\n"
        f"- Schema: compiled OK\n"
        f"- Cross-table FK: works\n\n"
        f"**Overall verdict**: "
        f"{'**PASS — proceed with sqlite-vec for memory engine.**' if (insert_pass and query_pass) else '**FAIL — fall back to ObjectBox (4 person-days switch, see §5 R5).**'}\n"
        "\n"
        "Tested on:\n"
        "- Linux x86_64 dev box\n"
        "- Python 3.8 + sqlite-vec 0.1.9 + numpy 1.24\n"
        "- Synthetic 384-d unit vectors\n\n"
        "**Caveat**: this does NOT validate React Native + Android JNI integration. "
        "That's a separate spike requiring an actual Android device.\n"
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\n  Wrote report: {REPORT_PATH}")
    print(f"\n  Verdict: {'PASS ✓' if (insert_pass and query_pass) else 'FAIL ✗'}")


if __name__ == "__main__":
    main()
