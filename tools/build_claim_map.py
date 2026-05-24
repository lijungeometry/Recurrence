#!/usr/bin/env python3
"""Build an Obsidian-friendly lemma/proposition claim map for a Recurrence run.

The decomposition prover already asks a harsh verifier to judge every planned
step. This tool turns those buried verification reports into a map:

- output/claim_map/claims.json
- output/claim_map/claim_map.md
- memory/claims/<run>/<claim>.md
- memory/claims/<run>/index.md

It does not call a model. It records the verifier's PASS/FAIL/UNCERTAIN as
YES/NO/UNCERTAIN for each lemma/proposition node.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

import yaml


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def latest_detailed_report(output_dir: Path) -> Path | None:
    reports = sorted(
        output_dir.glob("decomposition/attempt_*/revision_*/proof_*/detailed_verification.md"),
        key=lambda p: p.stat().st_mtime,
    )
    if not reports:
        return None
    pass_reports = [p for p in reports if re.search(r"Overall Verdict:\s*PASS", read_text(p), re.I)]
    return pass_reports[-1] if pass_reports else reports[-1]


def latest_structural_report(output_dir: Path) -> Path | None:
    reports = sorted(
        output_dir.glob("decomposition/attempt_*/revision_*/proof_*/structural_verification.md"),
        key=lambda p: p.stat().st_mtime,
    )
    return reports[-1] if reports else None


def decomposition_for_report(report: Path) -> Path:
    # .../decomposition/attempt_N/revision_M/proof_K/detailed_verification.md
    return report.parent.parent / "decomposition.yaml"


def proof_for_report(report: Path) -> Path:
    return report.parent / "proof.md"


def load_decomposition(path: Path) -> dict:
    text = read_text(path)
    if not text.strip():
        return {}
    return yaml.safe_load(text) or {}


def parse_step_reports(report_text: str) -> dict[str, dict]:
    results: dict[str, dict] = {}
    pattern = re.compile(r"^####\s+(STEP\d+|GOAL)\s*:?(.*)$", re.M)
    matches = list(pattern.finditer(report_text))
    for idx, match in enumerate(matches):
        step_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(report_text)
        block = report_text[start:end]

        verdict_match = re.search(r"\*\*Verdict:\*\*\s*(PASS|FAIL|UNCERTAIN)", block, re.I)
        bool_match = re.search(r"\*\*Boolean verdict:\*\*\s*(YES|NO|UNCERTAIN)", block, re.I)
        issues_match = re.search(r"\*\*Issues:\*\*\s*(.*?)(?:\n\n|$)", block, re.S)
        claim_match = re.search(r"\*\*Claim:\*\*\s*(.*?)(?:\n\n|\n\*\*)", block, re.S)

        verifier_verdict = verdict_match.group(1).upper() if verdict_match else "UNCERTAIN"
        if bool_match:
            boolean_verdict = bool_match.group(1).upper()
        elif verifier_verdict == "PASS":
            boolean_verdict = "YES"
        elif verifier_verdict == "FAIL":
            boolean_verdict = "NO"
        else:
            boolean_verdict = "UNCERTAIN"

        results[step_id] = {
            "title": title,
            "claim_from_report": clean(claim_match.group(1)) if claim_match else "",
            "verifier_verdict": verifier_verdict,
            "boolean_verdict": boolean_verdict,
            "issues": clean(issues_match.group(1)) if issues_match else "",
            "report_excerpt": clean(block[:1800]),
        }
    return results


def clean(text: str) -> str:
    return " ".join(text.strip().split())


def node_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def claim_nodes(decomposition: dict, step_reports: dict[str, dict]) -> list[dict]:
    nodes: list[dict] = []
    for step in decomposition.get("steps", []) or []:
        step_id = str(step.get("id", "")).strip()
        if not step_id:
            continue
        report = step_reports.get(step_id, {})
        nodes.append({
            "id": step_id,
            "claim_type": step.get("claim_type", "lemma" if step.get("is_key_step") else "proposition"),
            "statement": clean(step.get("statement", "")),
            "verification_question": clean(step.get("verification_question", f"Does the proof rigorously establish {step_id}?")),
            "inputs": step.get("inputs", []) or [],
            "difficulty": step.get("difficulty", ""),
            "is_key_step": bool(step.get("is_key_step", False)),
            "verifier_verdict": report.get("verifier_verdict", "UNCERTAIN"),
            "boolean_verdict": report.get("boolean_verdict", "UNCERTAIN"),
            "issues": report.get("issues", ""),
            "report_excerpt": report.get("report_excerpt", ""),
        })

    target = decomposition.get("target") or {}
    if target:
        step_id = str(target.get("id", "GOAL"))
        report = step_reports.get(step_id, {})
        nodes.append({
            "id": step_id,
            "claim_type": "goal",
            "statement": clean(target.get("statement", "")),
            "verification_question": clean(target.get("verification_question", "Does the proof establish the original target from the listed inputs?")),
            "inputs": target.get("inputs", []) or [],
            "difficulty": "",
            "is_key_step": False,
            "verifier_verdict": report.get("verifier_verdict", "UNCERTAIN"),
            "boolean_verdict": report.get("boolean_verdict", "UNCERTAIN"),
            "issues": report.get("issues", ""),
            "report_excerpt": report.get("report_excerpt", ""),
        })
    return nodes


def write_claim_json(path: Path, *, output_dir: Path, report: Path, decomposition: Path, proof: Path, nodes: list[dict]) -> None:
    payload = {
        "source_run": str(output_dir),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "proof": str(proof),
        "decomposition": str(decomposition),
        "detailed_verification": str(report),
        "nodes": nodes,
    }
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def verdict_badge(verdict: str) -> str:
    if verdict == "YES":
        return "YES"
    if verdict == "NO":
        return "NO"
    return "UNCERTAIN"


def write_run_map(path: Path, *, output_dir: Path, report: Path, decomposition: Path, proof: Path, nodes: list[dict]) -> None:
    yes = sum(1 for n in nodes if n["boolean_verdict"] == "YES")
    no = sum(1 for n in nodes if n["boolean_verdict"] == "NO")
    uncertain = sum(1 for n in nodes if n["boolean_verdict"] == "UNCERTAIN")

    lines = [
        "# Claim Verification Map",
        "",
        f"**Source run:** `{output_dir}`",
        f"**Generated:** {dt.datetime.now().isoformat(timespec='seconds')}",
        f"**Proof:** `{rel(proof, output_dir)}`",
        f"**Decomposition:** `{rel(decomposition, output_dir)}`",
        f"**Detailed verification:** `{rel(report, output_dir)}`",
        "",
        "## Verdict Counts",
        "",
        f"- YES: {yes}",
        f"- NO: {no}",
        f"- UNCERTAIN: {uncertain}",
        "",
        "## Dependency Graph",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for node in nodes:
        nid = node_id(node["id"])
        label = f"{node['id']}\\n{node['claim_type']}\\n{node['boolean_verdict']}"
        lines.append(f'  {nid}["{label}"]')
    known = {n["id"] for n in nodes}
    for node in nodes:
        for dep in node.get("inputs", []):
            if dep in known:
                lines.append(f"  {node_id(dep)} --> {node_id(node['id'])}")
    lines.extend(["```", "", "## Claim Table", ""])
    lines.append("| Claim | Type | Key | Boolean | Verifier | Inputs | Issue |")
    lines.append("|---|---|---:|---|---|---|---|")
    for node in nodes:
        issue = node["issues"] or "None"
        if len(issue) > 160:
            issue = issue[:157] + "..."
        inputs = ", ".join(node.get("inputs", []))
        lines.append(
            f"| `{node['id']}` | {node['claim_type']} | {str(node['is_key_step']).lower()} | "
            f"{verdict_badge(node['boolean_verdict'])} | {node['verifier_verdict']} | {inputs} | {issue} |"
        )
    write_text(path, "\n".join(lines) + "\n")


def write_obsidian_notes(memory_dir: Path, run_name: str, output_dir: Path, nodes: list[dict], run_map: Path) -> None:
    base = memory_dir / "claims" / run_name
    base.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Claim Map: {run_name}",
        "",
        f"Source run: `{output_dir}`",
        f"Run map: `{run_map}`",
        "",
        "## Claims",
        "",
    ]
    for node in nodes:
        note = base / f"{node['id']}.md"
        note_lines = [
            f"# {run_name} {node['id']}",
            "",
            f"- **Type:** {node['claim_type']}",
            f"- **Boolean verdict:** {node['boolean_verdict']}",
            f"- **Verifier verdict:** {node['verifier_verdict']}",
            f"- **Key step:** {str(node['is_key_step']).lower()}",
            f"- **Inputs:** {', '.join(node.get('inputs', [])) or 'None'}",
            "",
            "## Verification Question",
            "",
            node["verification_question"] or "(not provided)",
            "",
            "## Statement",
            "",
            node["statement"] or "(not provided)",
            "",
            "## Issues",
            "",
            node["issues"] or "None",
            "",
            "## Report Excerpt",
            "",
            node["report_excerpt"] or "(no report excerpt)",
            "",
        ]
        write_text(note, "\n".join(note_lines))
        lines.append(f"- [[claims/{run_name}/{node['id']}|{node['id']}]] - {node['boolean_verdict']} - {node['claim_type']}")
    write_text(base / "index.md", "\n".join(lines) + "\n")

    claims_index = memory_dir / "claims" / "index.md"
    existing = read_text(claims_index)
    global_link = "- [[global_claim_map|Global Claim Map]]"
    link = f"- [[claims/{run_name}/index|{run_name}]]"
    changed = False
    if global_link not in existing:
        if not existing.strip():
            existing = "# Claim Maps\n\n"
        existing = existing.rstrip() + "\n" + global_link + "\n"
        changed = True
    if link not in existing:
        if not existing.strip():
            existing = "# Claim Maps\n\n"
        existing = existing.rstrip() + "\n" + link + "\n"
        changed = True
    if changed:
        write_text(claims_index, existing)


def update_memory_index(memory_dir: Path, run_name: str) -> None:
    index = memory_dir / "index.md"
    text = read_text(index)
    if not text.strip():
        text = "# Recurrence Memory Index\n\n"
    section = "## Claim Maps"
    link = f"- [[claims/{run_name}/index|{run_name} claim map]]"
    if section not in text:
        text = text.rstrip() + "\n\n## Claim Maps\n\n" + link + "\n"
    elif link not in text:
        text = text.rstrip() + "\n" + link + "\n"
    write_text(index, text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--memory-dir", type=Path, default=Path("memory"))
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_dir():
        raise SystemExit(f"Output directory not found: {output_dir}")

    report = latest_detailed_report(output_dir)
    if report is None:
        structural = latest_structural_report(output_dir)
        if structural is None:
            raise SystemExit("No detailed or structural verification report found.")
        report = structural

    decomposition = decomposition_for_report(report)
    proof = proof_for_report(report)
    decomp = load_decomposition(decomposition)
    step_reports = parse_step_reports(read_text(report))
    nodes = claim_nodes(decomp, step_reports)
    if not nodes:
        raise SystemExit(f"No claim nodes found from {decomposition}")

    claim_dir = output_dir / "claim_map"
    json_path = claim_dir / "claims.json"
    md_path = claim_dir / "claim_map.md"
    write_claim_json(json_path, output_dir=output_dir, report=report, decomposition=decomposition, proof=proof, nodes=nodes)
    write_run_map(md_path, output_dir=output_dir, report=report, decomposition=decomposition, proof=proof, nodes=nodes)

    run_name = output_dir.resolve().name
    write_obsidian_notes(args.memory_dir, run_name, output_dir, nodes, md_path)
    update_memory_index(args.memory_dir, run_name)

    yes = sum(1 for n in nodes if n["boolean_verdict"] == "YES")
    no = sum(1 for n in nodes if n["boolean_verdict"] == "NO")
    uncertain = sum(1 for n in nodes if n["boolean_verdict"] == "UNCERTAIN")
    print(f"Claim map written: {md_path}")
    print(f"Claims JSON written: {json_path}")
    print(f"Obsidian notes: {args.memory_dir / 'claims' / run_name}")
    print(f"Verdicts: YES={yes}, NO={no}, UNCERTAIN={uncertain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
