"""Post-test gap analyser for the PoC-6 heartbeat CSV.

Reads the CSV pulled via `adb pull` and reports any gap > 60 s, plus a
PASS/FAIL verdict per the engineering plan §3 PoC-6 criteria.

Usage:
    python3 analyze_heartbeat.py heartbeat.csv [--gap-threshold-sec 60]

Pure standard library — runs anywhere.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from typing import List, Tuple


def parse_csv(path: str) -> List[Tuple[dt.datetime, int]]:
    rows: List[Tuple[dt.datetime, int]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = dt.datetime.fromisoformat(r["timestamp_iso"])
            counter = int(r["counter"])
            rows.append((ts, counter))
    return rows


def find_gaps(
    rows: List[Tuple[dt.datetime, int]],
    threshold_sec: float,
) -> List[Tuple[dt.datetime, dt.datetime, float]]:
    out = []
    for prev, cur in zip(rows, rows[1:]):
        delta = (cur[0] - prev[0]).total_seconds()
        if delta > threshold_sec:
            out.append((prev[0], cur[0], delta))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--gap-threshold-sec", type=float, default=60.0)
    ap.add_argument("--target-runtime-h", type=float, default=12.0,
                    help="Target runtime to consider a 'pass' (default 12h).")
    args = ap.parse_args()

    rows = parse_csv(args.csv_path)
    if not rows:
        print("ERROR: empty CSV")
        return 2

    runtime = (rows[-1][0] - rows[0][0]).total_seconds()
    gaps = find_gaps(rows, args.gap_threshold_sec)

    print(f"== PoC-6 heartbeat analysis ==")
    print(f"  Rows         : {len(rows):,}")
    print(f"  First tick   : {rows[0][0].isoformat()} (counter={rows[0][1]})")
    print(f"  Last  tick   : {rows[-1][0].isoformat()} (counter={rows[-1][1]})")
    print(f"  Runtime      : {runtime/3600:.2f} h ({int(runtime)} s)")
    print(f"  Gap threshold: {args.gap_threshold_sec} s")
    print(f"  Gaps found   : {len(gaps)}")

    longest_gap = max((g[2] for g in gaps), default=0.0)
    print(f"  Longest gap  : {longest_gap:.1f} s")

    if gaps:
        print()
        print("  Top-5 longest gaps:")
        for g in sorted(gaps, key=lambda x: -x[2])[:5]:
            start, end, delta = g
            print(f"    {start.isoformat()} -> {end.isoformat()}  "
                  f"({delta:.0f}s, {delta/60:.1f} min)")

    runtime_pass = runtime >= args.target_runtime_h * 3600
    no_severe_gaps = len(gaps) == 0

    print()
    print(f"  Runtime ≥ {args.target_runtime_h}h : "
          f"{'PASS ✓' if runtime_pass else 'FAIL ✗'}")
    print(f"  Zero gaps > {args.gap_threshold_sec}s: "
          f"{'PASS ✓' if no_severe_gaps else 'FAIL ✗'}")
    print()
    overall_pass = runtime_pass and no_severe_gaps
    print(f"  Overall: {'PASS ✓' if overall_pass else 'FAIL ✗'}")
    print()
    print("  Next: open results.md and append a row for this ROM.")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
