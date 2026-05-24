# Recurrence

Recurrence is the primary mathematics research agent in this folder.

The difference is the added pre-proof recurrence layer. It has two modes.

In `explore` mode, before trying to prove a target directly, Recurrence explores the neighborhood of the open question the way a human mathematician often does:

- forms nearby positive conjectures,
- forms nearby negative conjectures and obstruction tests,
- checks special cases and sharpness,
- ranks which branches deserve proof-search budget,
- records which branches should be refused or paused.

In `attack` mode, Recurrence treats the input statement as a serious human conjecture. It does not merely wander. It enumerates proof methods, enumerates counterexample methods, tests edge cases, records exact verifier formats, and decides whether the next stage should pursue a proof route, verify a counterexample, attack a bottleneck, or ask for human clarification.

The name is a constraint, not just branding: every exploration has to return to the original conjecture. Side branches are useful only when they clarify what is proved, reduced, obstructed, or still unresolved for the central target.

The proof system then uses the existing pipeline strengths: literature survey, decomposition, proof writing, structural verification, detailed verification, and regulator-driven revision.

## Default Workflow

```text
problem/*.md or problem/*.tex
 -> literature survey
 -> recurrence mode: explore or attack
 -> recurrence map / attack report
 -> ranked approach queue
 -> decomposition proof plan
 -> proof generation
 -> structural verification
 -> detailed verification
 -> regulator: revise proof / revise plan / rewrite / stop
 -> proof effort summary
```

## New Recurrence Artifacts

When `recurrence.enabled: true` in `config.yaml`, the run writes:

- `recurrence/exploration_map.md`
- `recurrence/conjecture_ledger.json`
- `recurrence/approach_queue.md`
- `recurrence/no_output_decisions.md`
- `recurrence/approach_journal.md`
- `recurrence/conjecture_return_map.md`
- `recurrence/error_recurrence_exploration.md`

In `recurrence.mode: "attack"`, the run also writes:

- `recurrence/attack_report.md`
- `recurrence/method_matrix.md`
- `recurrence/counterexample_search.md`
- `recurrence/attack_decision.json`

The decomposer and prover are instructed to read the exploration map when it exists.

## Harness Notes

The broader AI-for-math operating model is documented in:

```text
docs/ai_math_agent_harness.md
```

That file is the reusable harness for future agents: best-of-N over approaches, generator/checker separation, citation audit, strategic no-output, and the recurrence exploration contract.

## Campaigns

Run one serious mathematical question per problem file. Do not put eight targets in one file and expect the verifier to know which one is the deliverable.

Single question:

```bash
./run_recurrence.sh problem/FirstTry-gompf.md runs/FirstTry-gompf config.yaml
```

Many question files:

```bash
./run_campaign.sh --problem-dir problem --glob "*.md" --output-root runs --config config.yaml --extract-memory
```

The campaign runner skips outputs that already look complete unless `--force` is passed. Each run should leave a proof, proof summary, recurrence notes, token usage, and optionally extracted memory.

## Memory / Obsidian

The folder `memory/` is intentionally plain Markdown plus JSONL. It can be opened as an Obsidian vault. Use it as a map of clusters:

- achievements,
- failed branches,
- unresolved cores,
- next problem files,
- search-control decisions.

Do not use it as a scrapbook. A useful note must say what changes about the conjecture after this run.

## Claim Maps

After each decomposition run, Recurrence can turn the verifier report into a lemma/proposition map:

```bash
.venv/bin/python tools/build_claim_map.py runs/<run-name> --memory-dir memory
```

For future pipeline runs this sidecar is called automatically after the proof effort summary. Each claim receives a harsh Boolean verdict:

- `YES`: the verifier certified the claim,
- `NO`: the verifier rejected the claim,
- `UNCERTAIN`: the verifier could not certify it.

The output lives in both the run directory and the Obsidian vault:

```text
runs/<run-name>/claim_map/
memory/claims/<run-name>/
```
