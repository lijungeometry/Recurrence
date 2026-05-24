#!/usr/bin/env python3
"""Run Recurrence over a queue of problem files.

This is a campaign runner, not a proof agent. It runs one problem file at a
time, writes each result under an output root, and keeps a small campaign log.
It intentionally does not split a runbook into targets. Each serious question
should be its own problem file so verification can compare the proof against a
single target.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path


def slugify(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-")
    return slug or "problem"


def is_complete(output_dir: Path) -> bool:
    proof = output_dir / "proof.md"
    summary = output_dir / "proof_effort_summary.md"
    log = output_dir / "decomposition" / "log.txt"
    summary_status = output_dir / "summary_log" / "AUTO_RUN_STATUS.md"

    if log.exists() and "Proof completed successfully" in log.read_text(encoding="utf-8", errors="ignore"):
        return True
    if summary_status.exists() and "FINISHED" in summary_status.read_text(encoding="utf-8", errors="ignore"):
        return proof.exists() and proof.stat().st_size > 0
    return proof.exists() and proof.stat().st_size > 0 and summary.exists() and summary.stat().st_size > 0


def token_summary(output_dir: Path) -> str:
    path = output_dir / "TOKEN_USAGE.md"
    if not path.exists():
        return "token usage unavailable"
    text = path.read_text(encoding="utf-8", errors="ignore")
    fields = {}
    for line in text.splitlines():
        match = re.match(r"\| (Total input tokens|Total output tokens|Total tokens|Agent calls|Total elapsed) \| ([^|]+) \|", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    if not fields:
        return "token usage unavailable"
    return ", ".join(f"{key}: {value}" for key, value in fields.items())


def discover_problems(problem_dir: Path, pattern: str) -> list[Path]:
    paths = sorted(problem_dir.glob(pattern))
    return [p for p in paths if p.is_file()]


def append_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def run_one(
    *,
    problem: Path,
    output_dir: Path,
    config: Path,
    run_script: Path,
    log_file: Path,
    dry_run: bool,
    extract_memory: bool,
    memory_dir: Path,
) -> int:
    cmd = [str(run_script), str(problem), str(output_dir), str(config)]
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    append_log(log_file, f"\n## {stamp} `{problem}`\n\n")
    append_log(log_file, f"- Output: `{output_dir}`\n")
    append_log(log_file, f"- Command: `{' '.join(cmd)}`\n")

    if dry_run:
        append_log(log_file, "- Status: DRY_RUN\n")
        print("DRY RUN:", " ".join(cmd))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    run_log = output_dir / "campaign_run.log"
    start = dt.datetime.now()
    print(f"\n=== Running {problem} ===")
    print(f"Output: {output_dir}")
    with run_log.open("a", encoding="utf-8") as f:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            f.write(line)
        code = proc.wait()
    elapsed = int((dt.datetime.now() - start).total_seconds())
    append_log(log_file, f"- Exit code: `{code}`\n")
    append_log(log_file, f"- Elapsed seconds: `{elapsed}`\n")
    append_log(log_file, f"- Tokens: {token_summary(output_dir)}\n")

    if code == 0 and extract_memory:
        mem_cmd = [
            sys.executable,
            str(Path(__file__).with_name("extract_memory.py")),
            str(output_dir),
            "--memory-dir",
            str(memory_dir),
            "--append",
        ]
        mem = subprocess.run(mem_cmd, text=True, capture_output=True)
        append_log(log_file, f"- Memory extraction exit code: `{mem.returncode}`\n")
        if mem.stdout.strip():
            append_log(log_file, "```text\n" + mem.stdout.strip() + "\n```\n")
        if mem.stderr.strip():
            append_log(log_file, "```text\n" + mem.stderr.strip() + "\n```\n")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("problems", nargs="*", type=Path, help="Problem files to run")
    parser.add_argument("--problem-dir", type=Path, default=Path("problem"))
    parser.add_argument("--glob", default="*.md", help="Glob used when no explicit problem files are passed")
    parser.add_argument("--output-root", type=Path, default=Path("runs"))
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--run-script", type=Path, default=Path("./run_recurrence.sh"))
    parser.add_argument("--limit", type=int, default=0, help="Run at most N pending problems; 0 means no limit")
    parser.add_argument("--force", action="store_true", help="Run even when output appears complete")
    parser.add_argument("--continue-on-fail", action="store_true", help="Continue to the next problem after a failure")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--extract-memory", action="store_true", help="Run tools/extract_memory.py after successful runs")
    parser.add_argument("--memory-dir", type=Path, default=Path("memory"))
    args = parser.parse_args()

    problems = args.problems or discover_problems(args.problem_dir, args.glob)
    if not problems:
        raise SystemExit("No problem files found.")

    log_file = args.output_root / "campaign_log.md"
    append_log(log_file, f"\n# Campaign Run {dt.datetime.now().isoformat(timespec='seconds')}\n")

    pending: list[Path] = []
    for problem in problems:
        output_dir = args.output_root / slugify(problem)
        if not args.force and is_complete(output_dir):
            append_log(log_file, f"\n## SKIP `{problem}`\n\n- Output: `{output_dir}`\n- Reason: already complete\n")
            print(f"SKIP complete: {problem} -> {output_dir}")
            continue
        pending.append(problem)

    if args.limit > 0:
        pending = pending[:args.limit]

    if not pending:
        print("No pending problems.")
        return 0

    run_script = args.run_script
    if not run_script.is_absolute():
        run_script = (Path.cwd() / run_script).resolve()
    config = args.config
    if not config.is_absolute():
        config = (Path.cwd() / config).resolve()

    failures = 0
    for problem in pending:
        output_dir = args.output_root / slugify(problem)
        code = run_one(
            problem=problem,
            output_dir=output_dir,
            config=config,
            run_script=run_script,
            log_file=log_file,
            dry_run=args.dry_run,
            extract_memory=args.extract_memory,
            memory_dir=args.memory_dir,
        )
        if code != 0:
            failures += 1
            if not args.continue_on_fail:
                break

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
