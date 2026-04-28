from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = ROOT / "benchmarks" / "custom_eco20"
AGENT = ROOT / "ECO_Agent.py"


def discover_cases() -> list[Path]:
    return sorted(path for path in BENCH_ROOT.iterdir() if path.is_dir() and path.name.startswith("case"))


def case_number(case_name: str) -> int | None:
    match = re.match(r"case(\d+)_", case_name)
    return int(match.group(1)) if match else None


def normalize_selector(selector: str) -> str:
    item = selector.strip()
    if item.isdigit():
        return f"case{int(item):02d}_"
    if re.fullmatch(r"case\d+", item):
        return f"{item[:4]}{int(item[4:]):02d}_"
    return item


def select_cases(all_cases: list[Path], selectors: list[str], run_all: bool) -> list[Path]:
    if run_all or not selectors:
        return all_cases

    selected: list[Path] = []
    missing: list[str] = []
    for raw_selector in selectors:
        selector = normalize_selector(raw_selector)
        matches = [
            case_root
            for case_root in all_cases
            if case_root.name == selector or case_root.name.startswith(selector)
        ]
        if not matches:
            missing.append(raw_selector)
            continue
        selected.extend(matches)

    if missing:
        known = ", ".join(case.name for case in all_cases)
        raise SystemExit(f"Unknown case selector(s): {', '.join(missing)}\nKnown cases: {known}")

    deduped: dict[str, Path] = {}
    for case_root in selected:
        deduped[case_root.name] = case_root
    return [deduped[name] for name in sorted(deduped)]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def retry_remove_readonly(func, path, exc_info) -> None:
    try:
        os.chmod(path, 0o700)
        func(path)
    except Exception:
        raise exc_info[1]


def run_case(case_root: Path, *, clean: bool) -> dict:
    patched_dir = case_root / "patched_netlist"
    if clean and patched_dir.exists():
        resolved_case = case_root.resolve()
        resolved_patched = patched_dir.resolve()
        if resolved_case not in resolved_patched.parents:
            raise RuntimeError(f"Refusing to clean output outside selected case: {patched_dir}")
        shutil.rmtree(patched_dir, onerror=retry_remove_readonly)

    print(f"[BENCH] Running {case_root.name}")
    start = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            str(AGENT),
            "--project-root",
            str(case_root),
            "--executor",
            "heuristic",
            "--max-syntax-retries",
            "0",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    duration = round(time.perf_counter() - start, 2)
    combined = (result.stdout or "") + (result.stderr or "")

    feasibility_path = patched_dir / "feasibility_report.json"
    patch_path = patched_dir / "patch_report.json"
    repair_log_path = patched_dir / "repair_session_log.txt"
    feasibility = load_json(feasibility_path) if feasibility_path.exists() else {}
    patch = load_json(patch_path) if patch_path.exists() else {}
    repair_log = repair_log_path.read_text(encoding="utf-8", errors="replace") if repair_log_path.exists() else combined
    exec_summary = patch.get("execution_summary", {})
    minimality = patch.get("minimality", {})
    bug_summary = patch.get("bug_summary", {})

    return {
        "case": case_root.name,
        "returncode": result.returncode,
        "duration_sec": duration,
        "feasibility_status": feasibility.get("status"),
        "supported_mode": feasibility.get("supported_mode"),
        "passed": bool(patch and patch.get("verification", {}).get("passed")),
        "strategy_attempts": exec_summary.get("strategy_attempts", count_matches(repair_log, r"^\[STATUS\] Trying strategy")),
        "syntax_attempts": exec_summary.get("syntax_attempts_for_selected_candidate", count_matches(repair_log, r"applying syntax-repair cycle")),
        "successful_candidates": exec_summary.get("successful_candidates", count_matches(repair_log, r"Passing candidate minimality")),
        "selected_strategy": exec_summary.get("selected_strategy", ""),
        "executor": exec_summary.get("executor", "heuristic"),
        "bug_type": bug_summary.get("bug_type", ""),
        "affected_outputs": ",".join(bug_summary.get("affected_outputs", [])),
        "changed_signals": ",".join(bug_summary.get("changed_signals", [])),
        "edit_hunks": minimality.get("edit_hunks"),
        "changed_line_count": minimality.get("changed_line_count"),
        "changed_signal_count": minimality.get("changed_signal_count"),
        "stdout_tail": "\n".join(combined.strip().splitlines()[-8:]),
    }


def write_reports(rows: list[dict]) -> None:
    summary_dir = BENCH_ROOT / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    json_path = summary_dir / "benchmark_results.json"
    csv_path = summary_dir / "benchmark_results.csv"
    md_path = summary_dir / "benchmark_results.md"

    totals = {
        "total_cases": len(rows),
        "passed_cases": sum(1 for row in rows if row["passed"]),
        "failed_cases": sum(1 for row in rows if not row["passed"]),
        "avg_duration_sec": round(sum(row["duration_sec"] for row in rows) / max(len(rows), 1), 2),
        "avg_strategy_attempts": round(sum(row["strategy_attempts"] for row in rows) / max(len(rows), 1), 2),
        "avg_selected_syntax_attempts": round(sum(row["syntax_attempts"] for row in rows) / max(len(rows), 1), 2),
        "minimal_patch_case": "",
    }
    passed_rows = [row for row in rows if row["passed"] and row["edit_hunks"] is not None]
    if passed_rows:
        best = min(
            passed_rows,
            key=lambda row: (
                row["edit_hunks"],
                row["changed_line_count"],
                row["changed_signal_count"],
            ),
        )
        totals["minimal_patch_case"] = best["case"]

    payload = {"totals": totals, "cases": rows}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fieldnames = [
        "case",
        "passed",
        "returncode",
        "duration_sec",
        "feasibility_status",
        "supported_mode",
        "strategy_attempts",
        "syntax_attempts",
        "successful_candidates",
        "selected_strategy",
        "executor",
        "bug_type",
        "affected_outputs",
        "changed_signals",
        "edit_hunks",
        "changed_line_count",
        "changed_signal_count",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})

    lines = [
        "# Custom ECO20 Benchmark Results",
        "",
        f"- Total cases: {totals['total_cases']}",
        f"- Passed: {totals['passed_cases']}",
        f"- Failed: {totals['failed_cases']}",
        f"- Average runtime (s): {totals['avg_duration_sec']}",
        f"- Average strategy attempts: {totals['avg_strategy_attempts']}",
        f"- Average selected syntax attempts: {totals['avg_selected_syntax_attempts']}",
        f"- Minimal patch case: {totals['minimal_patch_case'] or '(none)'}",
        "",
        "| Case | Pass | Bug Type | Strategy Attempts | Minimality |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        minimality = (
            f"h{row['edit_hunks']}/l{row['changed_line_count']}/s{row['changed_signal_count']}"
            if row["edit_hunks"] is not None
            else "-"
        )
        lines.append(
            f"| {row['case']} | {'yes' if row['passed'] else 'no'} | {row['bug_type'] or '-'} | "
            f"{row['strategy_attempts']} | {minimality} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(totals, indent=2))
    print(f"JSON: {json_path}")
    print(f"CSV : {csv_path}")
    print(f"MD  : {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the custom ECO20 benchmark suite")
    parser.add_argument(
        "cases",
        nargs="*",
        help="Case numbers or names to run, e.g. 1 5 case20_checksum_slice",
    )
    parser.add_argument("--all", action="store_true", help="Run all 20 benchmark cases")
    parser.add_argument("--list", action="store_true", help="List available benchmark cases and exit")
    parser.add_argument(
        "--keep-outputs",
        action="store_true",
        help="Do not delete a case's existing patched_netlist directory before running",
    )
    args = parser.parse_args()

    cases = discover_cases()
    if args.list:
        for case_root in cases:
            number = case_number(case_root.name)
            label = f"{number:02d}" if number is not None else "--"
            print(f"{label}  {case_root.name}")
        return

    selected_cases = select_cases(cases, args.cases, args.all)
    print(f"[BENCH] Selected {len(selected_cases)} case(s)")
    rows = [run_case(case_root, clean=not args.keep_outputs) for case_root in selected_cases]
    write_reports(rows)


if __name__ == "__main__":
    main()
