#!/usr/bin/env python3
"""Extract durable research-memory notes from a Recurrence output directory.

This is intentionally a sidecar tool: it does not change the proof pipeline.
It scans run artifacts, writes machine-readable JSONL memory items, and writes
a human-readable per-run memory note.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
from pathlib import Path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def stable_id(item: dict) -> str:
    key = "\n".join([
        item.get("type", ""),
        item.get("claim_or_strategy", ""),
        item.get("evidence", ""),
    ])
    return "mem_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def load_existing_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("id"):
            ids.add(data["id"])
    return ids


def add_item(items: list[dict], *, item_type: str, claim: str, status: str,
             evidence: str, confidence: str, source_files: list[Path],
             output_dir: Path, domain: str = "unknown",
             reuse_condition: str = "") -> None:
    claim = " ".join(claim.strip().split())
    evidence = " ".join(evidence.strip().split())
    if not claim or not evidence:
        return
    item = {
        "type": item_type,
        "problem_domain": domain,
        "claim_or_strategy": claim,
        "status": status,
        "evidence": evidence,
        "confidence": confidence,
        "reuse_condition": reuse_condition,
        "source_run": str(output_dir),
        "source_files": [rel(p, output_dir) for p in source_files],
    }
    item["id"] = stable_id(item)
    items.append(item)


def extract_problem(output_dir: Path) -> str:
    problem = read_text(output_dir / "problem.tex").strip()
    return " ".join(problem.split())


def extract_domain(related_work: str, summary: str) -> str:
    text = (related_work + "\n" + summary).lower()
    if any(key in text for key in [
        "brieskorn", "stein", "pseudoconvex", "contact topology",
        "heegaard floer", "symplectic filling", "low-dimensional topology",
    ]):
        return "low_dimensional_topology"
    if "prime" in text or "number theory" in text:
        return "number_theory"
    if "pde" in text or "differential equation" in text:
        return "analysis_pde"
    if "probability" in text or "random walk" in text:
        return "probability"
    return "unknown"


def extract_counterexamples_and_pitfalls(output_dir: Path, related_work: str,
                                         domain: str) -> list[dict]:
    items: list[dict] = []
    source = output_dir / "related_info" / "related_work.md"
    marker = "## Counterexamples and Pitfalls"
    if marker not in related_work:
        return items
    section = related_work.split(marker, 1)[1]
    next_header = re.search(r"\n## ", section)
    if next_header:
        section = section[:next_header.start()]
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        text = line[2:].strip()
        lower = text.lower()
        if "need not" in lower or "do not" in lower or "pitfall" in lower:
            item_type = "false_lemma"
            status = "confirmed_false"
            confidence = "high"
        else:
            item_type = "pitfall"
            status = "active"
            confidence = "medium"
        add_item(
            items,
            item_type=item_type,
            claim=text,
            status=status,
            evidence=f"Recorded in Counterexamples and Pitfalls: {text}",
            confidence=confidence,
            source_files=[source],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Consult before choosing a proof strategy in this domain.",
        )
    return items


def extract_summary_items(output_dir: Path, summary: str, domain: str) -> list[dict]:
    items: list[dict] = []
    source = output_dir / "proof_effort_summary.md"

    if "## 4. Approaches Tried" in summary:
        section = summary.split("## 4. Approaches Tried", 1)[1]
        next_header = re.search(r"\n## ", section)
        if next_header:
            section = section[:next_header.start()]
        for raw in section.splitlines():
            line = raw.strip()
            if not line.startswith("- "):
                continue
            text = line[2:].strip()
            if not text:
                continue
            if "not attempted" in text.lower() or "unnecessary" in text.lower():
                item_type = "unused_direction"
                status = "active"
                confidence = "medium"
            else:
                item_type = "useful_strategy"
                status = "confirmed_useful"
                confidence = "high"
            add_item(
                items,
                item_type=item_type,
                claim=text,
                status=status,
                evidence=f"Proof effort summary listed this under approaches tried: {text}",
                confidence=confidence,
                source_files=[source],
                output_dir=output_dir,
                domain=domain,
                reuse_condition="Prefer confirmed useful strategies for similar problems; treat unused directions as optional alternatives.",
            )

    if "## 5. Key Mathematical Insights" in summary:
        section = summary.split("## 5. Key Mathematical Insights", 1)[1]
        next_header = re.search(r"\n## ", section)
        if next_header:
            section = section[:next_header.start()]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
        for paragraph in paragraphs[:4]:
            if paragraph.startswith("|") or len(paragraph) < 40:
                continue
            add_item(
                items,
                item_type="useful_insight",
                claim=paragraph,
                status="confirmed_useful",
                evidence="Recorded as a key mathematical insight in proof_effort_summary.md.",
                confidence="high",
                source_files=[source],
                output_dir=output_dir,
                domain=domain,
                reuse_condition="Retrieve for related proof planning or verifier checks.",
            )
    return items


def extract_recurrence_items(output_dir: Path, domain: str) -> list[dict]:
    items: list[dict] = []
    journal_path = output_dir / "recurrence" / "approach_journal.md"
    return_path = output_dir / "recurrence" / "conjecture_return_map.md"
    queue_path = output_dir / "recurrence" / "approach_queue.md"
    no_output_path = output_dir / "recurrence" / "no_output_decisions.md"
    attack_report_path = output_dir / "recurrence" / "attack_report.md"
    method_matrix_path = output_dir / "recurrence" / "method_matrix.md"
    counterexample_path = output_dir / "recurrence" / "counterexample_search.md"
    attack_decision_path = output_dir / "recurrence" / "attack_decision.json"

    journal = read_text(journal_path)
    ranking_header = "## Final Ranking Rationale"
    if ranking_header not in journal and "## Final Decision Rationale" in journal:
        ranking_header = "## Final Decision Rationale"
    if ranking_header in journal:
        section = journal.split(ranking_header, 1)[1]
        next_header = re.search(r"\n## ", section)
        if next_header:
            section = section[:next_header.start()]
        add_item(
            items,
            item_type="ranking_rationale",
            claim="Final Recurrence ranking rationale for this run.",
            status="active",
            evidence=section.strip()[:2200],
            confidence="medium",
            source_files=[journal_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Read before choosing the next branch in the same conjecture cluster.",
        )

    if "## Lessons For Future Prompts" in journal:
        section = journal.split("## Lessons For Future Prompts", 1)[1]
        next_header = re.search(r"\n## ", section)
        if next_header:
            section = section[:next_header.start()]
        add_item(
            items,
            item_type="prompt_lesson",
            claim="Prompt lessons recorded by Recurrence.",
            status="active",
            evidence=section.strip()[:2200],
            confidence="medium",
            source_files=[journal_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Use when writing the next problem prompt in this cluster.",
        )

    return_map = read_text(return_path)
    if return_map:
        for header, item_type in [
            ("## Current Frontier", "conjecture_frontier"),
            ("## Branch Return Table", "branch_return_map"),
            ("## Recommended Next Problem File", "next_problem"),
            ("## Dead Ends / Do Not Spend More Budget", "dead_end"),
        ]:
            if header not in return_map:
                continue
            section = return_map.split(header, 1)[1]
            next_header = re.search(r"\n## ", section)
            if next_header:
                section = section[:next_header.start()]
            add_item(
                items,
                item_type=item_type,
                claim=header.replace("## ", ""),
                status="active",
                evidence=section.strip()[:2200],
                confidence="medium",
                source_files=[return_path],
                output_dir=output_dir,
                domain=domain,
                reuse_condition="Use to keep future runs attached to the original conjecture.",
            )

    queue = read_text(queue_path)
    if queue:
        add_item(
            items,
            item_type="approach_queue",
            claim="Ranked approach queue from Recurrence.",
            status="active",
            evidence=queue.strip()[:2200],
            confidence="medium",
            source_files=[queue_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Use as the branch menu for future campaign runs.",
        )

    no_output = read_text(no_output_path)
    if no_output:
        add_item(
            items,
            item_type="search_control",
            claim="No-output and pause decisions from Recurrence.",
            status="active",
            evidence=no_output.strip()[:2200],
            confidence="medium",
            source_files=[no_output_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Avoid rerunning branches already refused or paused without new evidence.",
        )

    attack_report = read_text(attack_report_path)
    if attack_report:
        add_item(
            items,
            item_type="attack_report",
            claim="Recurrence attack-mode report.",
            status="active",
            evidence=attack_report.strip()[:2200],
            confidence="medium",
            source_files=[attack_report_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Read before deciding whether to prove the conjecture, verify a counterexample, or attack a bottleneck.",
        )

    method_matrix = read_text(method_matrix_path)
    if method_matrix:
        add_item(
            items,
            item_type="method_matrix",
            claim="Attack-mode method matrix.",
            status="active",
            evidence=method_matrix.strip()[:2200],
            confidence="medium",
            source_files=[method_matrix_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Use to avoid repeating blocked proof or disproof methods.",
        )

    counterexample_search = read_text(counterexample_path)
    if counterexample_search:
        add_item(
            items,
            item_type="counterexample_search",
            claim="Attack-mode counterexample search record.",
            status="active",
            evidence=counterexample_search.strip()[:2200],
            confidence="medium",
            source_files=[counterexample_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Read before rerunning counterexample searches in this cluster.",
        )

    attack_decision = read_text(attack_decision_path)
    if attack_decision:
        try:
            decision = json.loads(attack_decision)
            claim = f"Attack decision: {decision.get('decision', 'unknown')}"
            evidence = json.dumps(decision, indent=2)[:2200]
            confidence = str(decision.get("confidence", "medium"))
        except json.JSONDecodeError:
            claim = "Attack decision recorded by Recurrence."
            evidence = attack_decision.strip()[:2200]
            confidence = "medium"
        add_item(
            items,
            item_type="attack_decision",
            claim=claim,
            status="active",
            evidence=evidence,
            confidence=confidence,
            source_files=[attack_decision_path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Use as the current proof/disproof routing decision for this conjecture.",
        )
    return items


def extract_verification_issues(output_dir: Path, domain: str) -> list[dict]:
    items: list[dict] = []
    for path in output_dir.glob("**/*verification*.md"):
        text = read_text(path)
        if not text:
            continue
        if re.search(r"Overall Verdict:\s*PASS", text, re.IGNORECASE):
            if not re.search(r"\b(UNCERTAIN|UNABLE_TO_VERIFY)\b", text):
                continue
        failed_block = ""
        if "Failed/Uncertain Items" in text:
            failed_block = text.split("Failed/Uncertain Items", 1)[1][:1200]
        if "Specific Issues to Fix" in text:
            failed_block += "\n" + text.split("Specific Issues to Fix", 1)[1][:1200]
        failed_block = re.sub(r"\(if FAIL\):\s*N/A\.?", "", failed_block, flags=re.IGNORECASE)
        failed_block = re.sub(r"\(if any\):\s*None\.?", "", failed_block, flags=re.IGNORECASE)
        if re.search(r"\b(FAIL|UNCERTAIN|UNABLE_TO_VERIFY)\b", failed_block):
            add_item(
                items,
                item_type="verification_issue",
                claim=f"Verifier reported an issue in {path.name}.",
                status="active",
                evidence=failed_block,
                confidence="medium",
                source_files=[path],
                output_dir=output_dir,
                domain=domain,
                reuse_condition="Review before retrying or revising this proof strategy.",
            )
    return items


def extract_regulator_items(output_dir: Path, domain: str) -> list[dict]:
    items: list[dict] = []
    for path in output_dir.glob("**/regulator_decision.md"):
        text = read_text(path)
        if not text:
            continue
        match = re.search(r"## Decision:\s*([A-Z_]+)", text)
        decision = match.group(1) if match else "UNKNOWN"
        add_item(
            items,
            item_type="failed_or_revised_attempt",
            claim=f"Regulator decision: {decision}",
            status="active",
            evidence=text[:1800],
            confidence="medium",
            source_files=[path],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Use as attempt history if continuing this problem.",
        )

    failure = output_dir / "decomposition" / "failure_analysis.md"
    text = read_text(failure)
    if text:
        add_item(
            items,
            item_type="failure_analysis",
            claim="All configured decomposition retries were exhausted.",
            status="active",
            evidence=text[:2200],
            confidence="medium",
            source_files=[failure],
            output_dir=output_dir,
            domain=domain,
            reuse_condition="Read before restarting with a new strategy.",
        )
    return items


def write_markdown(run_memory_path: Path, output_dir: Path, problem: str,
                   items: list[dict]) -> None:
    lines = [
        "# Recurrence Run Memory",
        "",
        f"**Source run:** `{output_dir}`",
        f"**Extracted:** {_dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Problem",
        "",
        problem or "(problem file not found)",
        "",
        "## Memory Items",
        "",
    ]
    if not items:
        lines.append("No memory items extracted.")
    for item in items:
        lines.extend([
            f"### {item['id']} - {item['type']}",
            "",
            f"- **Status:** {item['status']}",
            f"- **Confidence:** {item['confidence']}",
            f"- **Claim/strategy:** {item['claim_or_strategy']}",
            f"- **Evidence:** {item['evidence']}",
            f"- **Reuse condition:** {item['reuse_condition'] or 'N/A'}",
            f"- **Source files:** {', '.join(item['source_files'])}",
            "",
        ])
    run_memory_path.parent.mkdir(parents=True, exist_ok=True)
    run_memory_path.write_text("\n".join(lines), encoding="utf-8")


def write_index(memory_dir: Path) -> None:
    items_path = memory_dir / "items.jsonl"
    runs_dir = memory_dir / "runs"
    counts: dict[str, int] = {}
    domains: dict[str, int] = {}
    if items_path.exists():
        for line in items_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts[item.get("type", "unknown")] = counts.get(item.get("type", "unknown"), 0) + 1
            domains[item.get("problem_domain", "unknown")] = domains.get(item.get("problem_domain", "unknown"), 0) + 1

    lines = [
        "# Recurrence Memory Index",
        "",
        "This folder is Obsidian-friendly plain Markdown. Use it as a map, not as a dumping ground: each run note should link back to claims, failures, and the next target.",
        "",
        "## Counts By Type",
        "",
    ]
    if counts:
        for key, value in sorted(counts.items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- No items yet.")

    lines.extend(["", "## Counts By Domain", ""])
    if domains:
        for key, value in sorted(domains.items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- No domains yet.")

    lines.extend(["", "## Run Notes", ""])
    if runs_dir.exists():
        notes = sorted(runs_dir.glob("*/memory.md"))
        if notes:
            for note in notes:
                lines.append(f"- [{note.parent.name}]({note.relative_to(memory_dir)})")
        else:
            lines.append("- No run notes yet.")
    else:
        lines.append("- No run notes yet.")

    lines.extend([
        "",
        "## Operating Rule",
        "",
        "Before launching a related problem, read the current cluster's run notes and ask: what returns to the conjecture, what is a side result, and what should not be run again without new evidence?",
        "",
    ])
    (memory_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path, help="Recurrence proof output directory")
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=Path("memory"),
        help="Directory for memory/items.jsonl and per-run notes",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append new items to memory/items.jsonl, skipping duplicate ids",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_dir():
        raise SystemExit(f"Output directory not found: {output_dir}")

    problem = extract_problem(output_dir)
    related_work = read_text(output_dir / "related_info" / "related_work.md")
    summary = read_text(output_dir / "proof_effort_summary.md")
    domain = extract_domain(related_work, summary)

    items: list[dict] = []
    items.extend(extract_counterexamples_and_pitfalls(output_dir, related_work, domain))
    items.extend(extract_summary_items(output_dir, summary, domain))
    items.extend(extract_recurrence_items(output_dir, domain))
    items.extend(extract_verification_issues(output_dir, domain))
    items.extend(extract_regulator_items(output_dir, domain))

    # Deduplicate within this extraction.
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        deduped.append(item)
    items = deduped

    memory_dir = args.memory_dir
    memory_dir.mkdir(parents=True, exist_ok=True)
    items_path = memory_dir / "items.jsonl"
    existing_ids = load_existing_ids(items_path) if args.append else set()

    mode = "a" if args.append else "w"
    written = 0
    with items_path.open(mode, encoding="utf-8") as f:
        for item in items:
            if item["id"] in existing_ids:
                continue
            f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            written += 1

    run_name = output_dir.resolve().name
    run_memory_path = memory_dir / "runs" / run_name / "memory.md"
    write_markdown(run_memory_path, output_dir, problem, items)
    write_index(memory_dir)

    print(f"Extracted {len(items)} item(s); wrote {written} new item(s) to {items_path}")
    print(f"Run memory note: {run_memory_path}")
    print(f"Memory index: {memory_dir / 'index.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
