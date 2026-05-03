#!/usr/bin/env python3
"""scripts/eval-runner.py

Runs the prompt evaluation suite (docs/prompts/eval-*.md) against a chosen
LLM and produces eval-report-YYYYMMDD.md.

v0.1 scope (this file):
  - Parse eval YAML blocks out of `docs/prompts/eval-*.md`
  - Pretty-print summary by scenario / target
  - **Stub** the LLM call (returns 'TODO') — wiring the real LLM proxy is
    a W2 task once gateway is deployable.

Usage:
    python3 scripts/eval-runner.py
    python3 scripts/eval-runner.py --scenario S2
    python3 scripts/eval-runner.py --provider deepseek --report eval-report.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "docs" / "prompts"


def discover_eval_files() -> List[Path]:
    return sorted(PROMPTS_DIR.glob("eval-S*.md"))


def parse_eval_blocks(md: str) -> List[Dict[str, Any]]:
    """Extract YAML blocks delimited by ```yaml ... ``` from markdown.

    Each block is expected to start with `- id:` (a list item).
    Tolerant: skips blocks that fail to parse.
    """
    blocks: List[Dict[str, Any]] = []
    pattern = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
    for match in pattern.finditer(md):
        body = match.group(1)
        # Lightweight YAML-ish parse — full YAML is overkill and adds a dep
        # we don't need. We extract just `id:`, `scenario:`, `eval_target:`,
        # `category:`, `difficulty:`. Full payloads are kept as raw text.
        rec: Dict[str, Any] = {"_raw": body}
        for line in body.splitlines():
            line = line.strip()
            for key in ("id", "scenario", "eval_target", "category", "difficulty"):
                prefix = f"- {key}:"
                if line.startswith(prefix):
                    rec[key] = line[len(prefix):].strip().strip('"')
                    break
                prefix2 = f"{key}:"
                if line.startswith(prefix2) and key not in rec:
                    rec[key] = line[len(prefix2):].strip().strip('"')
                    break
        if "id" in rec:
            blocks.append(rec)
    return blocks


def collect_evals() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in discover_eval_files():
        md = f.read_text(encoding="utf-8")
        blocks = parse_eval_blocks(md)
        for b in blocks:
            b["_file"] = f.name
        out.extend(blocks)
    return out


def call_llm_stub(eval_record: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Placeholder. v0.2 will wire to gateway/api/llm_proxy via httpx."""
    return {
        "status": "stub",
        "note": f"TODO(W2): call {provider} via gateway with eval input",
    }


def run_one(eval_record: Dict[str, Any], provider: str) -> Dict[str, Any]:
    eid = eval_record.get("id", "?")
    target = eval_record.get("eval_target", "?")
    output = call_llm_stub(eval_record, provider)
    return {
        "id": eid,
        "scenario": eval_record.get("scenario", "?"),
        "eval_target": target,
        "category": eval_record.get("category", "?"),
        "difficulty": eval_record.get("difficulty", "?"),
        "result": "stub",
        "details": output,
    }


def write_report(
    runs: List[Dict[str, Any]],
    report_path: Path,
    provider: str,
    when: dt.datetime,
) -> None:
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in runs:
        by_scenario[r["scenario"]].append(r)

    lines: List[str] = []
    lines.append(f"# Eval report — {when.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"- Provider: `{provider}` (v0.1 stub — see scripts/eval-runner.py)")
    lines.append(f"- Total evals: {len(runs)}")
    lines.append("")
    for scenario in sorted(by_scenario):
        rs = by_scenario[scenario]
        lines.append(f"## {scenario} ({len(rs)} evals)")
        lines.append("")
        lines.append("| ID | Target | Category | Difficulty | Result |")
        lines.append("|---|---|---|---|---|")
        for r in rs:
            lines.append(
                f"| {r['id']} | {r['eval_target']} | {r['category']} | "
                f"{r['difficulty']} | {r['result']} |"
            )
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", help="Filter by scenario (S1/S2/S5/S8)")
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument(
        "--report",
        default=f"eval-reports/eval-report-{dt.date.today().isoformat()}.md",
    )
    args = ap.parse_args()

    evals = collect_evals()
    if args.scenario:
        evals = [e for e in evals if e.get("scenario") == args.scenario]

    if not evals:
        print("No eval blocks found.")
        return 2

    print(f"Found {len(evals)} eval pairs")
    print()
    runs = [run_one(e, args.provider) for e in evals]

    by_target = defaultdict(int)
    for r in runs:
        by_target[r["eval_target"]] += 1
    for target, n in by_target.items():
        print(f"  {target:20s}: {n}")

    report_path = REPO_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(runs, report_path, args.provider, dt.datetime.now())
    print(f"\nReport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
