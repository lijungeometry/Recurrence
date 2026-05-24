# Recurrence Campaigns And Memory

## What To Improve

The main weakness in the current setup is not model strength. It is target management.

Do not ask one run to handle a whole problem list. A runbook is useful for human planning, but a proof verifier needs a single deliverable. Split a runbook into separate problem files, each with:

- the exact target,
- allowed scope,
- acceptable output format,
- known source constraints,
- what counts as `UNRESOLVED`,
- what would count as real progress toward the parent conjecture.

## Campaign Loop

Use `run_campaign.sh` for a sequence of problem files:

```bash
./run_campaign.sh --problem-dir problem --glob "*.md" --output-root runs --config config.yaml --extract-memory
```

Useful variants:

```bash
./run_campaign.sh --problem-dir problem --glob "*.md" --output-root runs --config config.yaml --limit 1
./run_campaign.sh problem/gompf-16.md problem/gompf-20.md --output-root runs --config config.yaml
./run_campaign.sh --problem-dir problem --glob "*.md" --output-root runs --config config.light.yaml --dry-run
```

The campaign runner:

- runs one file at a time,
- skips completed outputs unless `--force` is passed,
- writes `runs/campaign_log.md`,
- writes `campaign_run.log` inside each output folder,
- can call `tools/extract_memory.py` after a successful run.

## Recurrence Discipline

Recurrence should not merely wander. Every run must produce:

- `recurrence/approach_journal.md`: what was tried and why,
- `recurrence/conjecture_return_map.md`: how each branch returns to the original conjecture,
- `proof_effort_summary.md`: what was proved, failed, or left unresolved.

The return map is the important piece. A branch is valuable only if it becomes one of:

- a certified piece of the conjecture,
- a reduction of the conjecture,
- an obstruction to a tempting false route,
- finite evidence that motivates a precise next question,
- a side result explicitly marked as side result,
- a dead end that should not be rerun.

## Obsidian

Obsidian is a good fit only if it is used as a map, not as storage. The right unit is not "interesting note"; it is "state change in the research program."

No account is needed. Open the local `memory/` folder as a vault. Obsidian Sync is optional and separate from Recurrence.

Recommended vault:

```text
memory/
├── .obsidian/
├── _templates/
├── index.md
├── items.jsonl
├── claims/
├── clusters/
└── runs/
    └── <run-name>/
        └── memory.md
```

Open `memory/` as an Obsidian vault. Use links between:

- parent conjectures,
- finite subproblems,
- obstruction families,
- failed approaches,
- verified achievements,
- next-run targets.

Bad note: "Maybe use Donaldson."

Good note: "Donaldson lattice route would settle canonical Sigma(2,3,6n+1) if we can construct a closed definite manifold from an arbitrary Stein homology ball plus cap; current gap is universal cap/control of intersection lattice."

## Prompt Quality Bar

A good problem prompt should include:

- a single target statement,
- source scope: what papers/results may be used,
- output type: proof, obstruction map, counterexample search, classification table, or reduction,
- success criteria,
- refusal criteria,
- relation to the parent conjecture.

If the prompt says "understand this area" or "try these many things," the run will spend tokens constructing context but verification will struggle to decide success. Use the campaign layer for breadth; use single-target files for proof runs.

## Claim Maps

After a decomposition run finishes, Recurrence generates a claim map with:

```bash
.venv/bin/python tools/build_claim_map.py runs/<run-name> --memory-dir memory
```

The map is derived from the harsh detailed verifier report. Each lemma/proposition node receives:

- `YES`: verifier certified the claim,
- `NO`: verifier rejected the claim,
- `UNCERTAIN`: verifier could not certify the claim.

Generated files:

```text
runs/<run-name>/claim_map/claim_map.md
runs/<run-name>/claim_map/claims.json
memory/claims/<run-name>/index.md
memory/claims/<run-name>/<STEP>.md
```

Use these maps to decide what to run next. A proof with all `YES` nodes is a local achievement; a proof with `NO` or `UNCERTAIN` nodes should become a new problem file focused on the first failed lemma.

## Global Map

Combine all run maps into one vault-level map:

```bash
.venv/bin/python tools/build_global_map.py --runs-root runs --memory-dir memory
```

This writes:

```text
memory/global_claim_map.md
```

The global map has:

- one summary row per run,
- a Mermaid graph containing all run claim nodes,
- a frontier section listing every `NO` or `UNCERTAIN` claim,
- recent memory items for next problems, conjecture frontiers, and dead ends.

Future pipeline runs call this after generating the local claim map.
