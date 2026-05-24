#!/usr/bin/env python3
"""Build a global Obsidian map from all Recurrence claim maps."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def mermaid_label(text: str) -> str:
    return text.replace('"', "'").replace("\n", "<br/>")


def load_claim_maps(runs_root: Path) -> list[dict]:
    maps: list[dict] = []
    for path in sorted(runs_root.glob("*/claim_map/claims.json")):
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError:
            continue
        run_name = path.parents[1].name
        data["run_name"] = run_name
        data["claim_json"] = str(path)
        maps.append(data)
    return maps


def load_memory_items(memory_dir: Path) -> list[dict]:
    path = memory_dir / "items.jsonl"
    items: list[dict] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def short_statement(text: str, limit: int = 120) -> str:
    text = " ".join(text.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def write_global_map(memory_dir: Path, maps: list[dict], items: list[dict]) -> Path:
    path = memory_dir / "global_claim_map.md"
    lines = [
        "# Global Claim Map",
        "",
        f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "This map combines local lemma/proposition maps across Recurrence runs. Use it to find the current frontier: failed claims, uncertain claims, and next problem files.",
        "",
        "## Run Summary",
        "",
        "| Run | YES | NO | UNCERTAIN | Claim Map |",
        "|---|---:|---:|---:|---|",
    ]

    for data in maps:
        run = data["run_name"]
        nodes = data.get("nodes", [])
        yes = sum(1 for n in nodes if n.get("boolean_verdict") == "YES")
        no = sum(1 for n in nodes if n.get("boolean_verdict") == "NO")
        uncertain = sum(1 for n in nodes if n.get("boolean_verdict") == "UNCERTAIN")
        lines.append(
            f"| [[claims/{run}/index|{run}]] | {yes} | {no} | {uncertain} | [[claims/{run}/claim_map|map]] |"
        )

    lines.extend([
        "",
        "## Global Graph",
        "",
        "```mermaid",
        "flowchart TD",
        "  classDef yes fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20",
        "  classDef no fill:#ffebee,stroke:#c62828,color:#7f0000",
        "  classDef uncertain fill:#fff8e1,stroke:#f9a825,color:#5f4300",
        "  classDef run fill:#e3f2fd,stroke:#1565c0,color:#0d47a1",
    ])

    all_node_ids: set[str] = set()
    for data in maps:
        run = data["run_name"]
        run_node = safe_id(f"run_{run}")
        lines.append(f'  {run_node}["{mermaid_label(run)}"]:::run')
        for node in data.get("nodes", []):
            claim_id = str(node.get("id", "claim"))
            node_id = safe_id(f"{run}_{claim_id}")
            all_node_ids.add(node_id)
            verdict = node.get("boolean_verdict", "UNCERTAIN")
            label = f"{claim_id}<br/>{node.get('claim_type', 'claim')}<br/>{verdict}"
            cls = "yes" if verdict == "YES" else "no" if verdict == "NO" else "uncertain"
            lines.append(f'  {node_id}["{mermaid_label(label)}"]:::{cls}')
            lines.append(f"  {run_node} --> {node_id}")

        local_ids = {str(n.get("id", "")) for n in data.get("nodes", [])}
        for node in data.get("nodes", []):
            claim_id = str(node.get("id", "claim"))
            target = safe_id(f"{run}_{claim_id}")
            for dep in node.get("inputs", []) or []:
                dep = str(dep)
                if dep in local_ids:
                    source = safe_id(f"{run}_{dep}")
                    lines.append(f"  {source} --> {target}")

    lines.extend(["```", "", "## Frontier: NO / UNCERTAIN Claims", ""])
    frontier_count = 0
    for data in maps:
        run = data["run_name"]
        for node in data.get("nodes", []):
            verdict = node.get("boolean_verdict")
            if verdict not in {"NO", "UNCERTAIN"}:
                continue
            frontier_count += 1
            lines.extend([
                f"### [[claims/{run}/{node.get('id')}|{run} {node.get('id')}]] - {verdict}",
                "",
                f"- **Type:** {node.get('claim_type', 'claim')}",
                f"- **Statement:** {short_statement(node.get('statement', ''))}",
                f"- **Issues:** {node.get('issues') or 'None recorded'}",
                "",
            ])
    if frontier_count == 0:
        lines.append("No `NO` or `UNCERTAIN` claim nodes found yet.")

    next_items = [
        i for i in items
        if i.get("type") in {
            "next_problem",
            "conjecture_frontier",
            "dead_end",
            "attack_decision",
            "counterexample_search",
        }
    ]
    lines.extend(["", "## Research Frontier From Memory", ""])
    if not next_items:
        lines.append("No frontier memory items found yet.")
    else:
        for item in next_items[-20:]:
            lines.extend([
                f"### {item.get('type', 'item')} - {item.get('problem_domain', 'unknown')}",
                "",
                f"- **Claim:** {item.get('claim_or_strategy', '')}",
                f"- **Evidence:** {short_statement(item.get('evidence', ''), 300)}",
                f"- **Source run:** `{item.get('source_run', '')}`",
                "",
            ])

    write_text(path, "\n".join(lines) + "\n")
    return path


def update_indices(memory_dir: Path, global_path: Path) -> None:
    index = memory_dir / "index.md"
    text = read_text(index)
    if not text.strip():
        text = "# Recurrence Memory Index\n\n"
    link = "- [[global_claim_map|Global Claim Map]]"
    if link not in text:
        if "## Claim Maps" not in text:
            text = text.rstrip() + "\n\n## Claim Maps\n\n"
        text = text.rstrip() + "\n" + link + "\n"
    write_text(index, text)

    claims_index = memory_dir / "claims" / "index.md"
    claims_text = read_text(claims_index)
    if not claims_text.strip():
        claims_text = "# Claim Maps\n\n"
    global_link = "- [[global_claim_map|Global Claim Map]]"
    if global_link not in claims_text:
        claims_text = claims_text.rstrip() + "\n" + global_link + "\n"
    write_text(claims_index, claims_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("runs"))
    parser.add_argument("--memory-dir", type=Path, default=Path("memory"))
    args = parser.parse_args()

    maps = load_claim_maps(args.runs_root)
    if not maps:
        raise SystemExit(f"No claim maps found under {args.runs_root}/*/claim_map/claims.json")

    items = load_memory_items(args.memory_dir)
    global_path = write_global_map(args.memory_dir, maps, items)
    update_indices(args.memory_dir, global_path)
    print(f"Global map written: {global_path}")
    print(f"Runs included: {len(maps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
