# AI Math Agent Harness

This file turns the recent AI-for-math workflow discussion into operating rules for future agents in this repo. It is written for natural-language proof agents such as Recurrence, but the same structure can also guide Lean-first or hybrid systems.

## Public Lessons

Recent systems point to a common pattern:

- Generate several distinct approaches, not just several wordings of one approach.
- Separate proof generation from proof checking.
- Use web/literature search as a citation and hypothesis audit, not as decoration.
- Keep notes about intermediate failures and conjectures.
- Refuse to submit uncertain branches.
- Use human experts only after the machine pipeline has filtered the search space.

Relevant public references:

- OpenAI FirstProof submissions: https://openai.com/index/first-proof-submissions/
- OpenAI unit-distance result: https://openai.com/index/model-disproves-discrete-geometry-conjecture/
- Aletheia paper: https://arxiv.org/html/2602.10177
- Aletheia FirstProof paper: https://arxiv.org/html/2602.21201
- DeepMind Aletheia/Gemini Deep Think blog: https://deepmind.google/blog/accelerating-mathematical-and-scientific-discovery-with-gemini-deep-think/

The OpenAI unit-distance result is publicly described as coming from a general-purpose reasoning model, not a disclosed special-purpose unit-distance harness. The reusable harness lesson therefore comes more directly from FirstProof, Aletheia, and earlier QED-style systems.

## Core Loop

Use this as the default high-level loop:

```text
problem
 -> literature survey
 -> recurrence exploration
 -> return-to-conjecture map
 -> best-of-N approach queue
 -> decomposition plan
 -> proof generation
 -> structural verification
 -> detailed verification
 -> regulator decision
 -> revise proof / revise plan / rewrite / stop
```

The harness should preserve artifacts at every stage. A failed branch is useful if it explains why it failed.

## Best-Of-N Over Approaches

Best-of-N should mean different mathematical strategies, not just repeated sampling.

Recommended shape:

```text
Generate N idea seeds.
For each seed:
  produce one concrete route to the target,
  identify its hardest lemma,
  identify a likely obstruction,
  check references and hypotheses,
  decide whether it belongs in the approach queue.
Run proof generation only on the top branches.
```

Rank branches by:

- mathematical plausibility,
- checkability,
- novelty,
- amount of verified literature support,
- risk of changing the original problem,
- whether the key step can be isolated and attacked.

## Separate Generator And Checker

The proof writer and verifier should be separate roles even if they use the same underlying model.

Generator role:

- propose and write a complete proof,
- tackle key steps directly,
- tag nontrivial original arguments,
- state dependencies and citations.

Checker role:

- receive only the problem, candidate proof, decomposition, and source files,
- independently compare the proof against the original problem,
- verify citations and hypotheses,
- attack the key steps line by line,
- return `PASS`, `FIXABLE`, `FAIL`, or `UNCERTAIN`.

The checker should not be asked to be encouraging. It should be fair, technical, and adversarial.

## Reference Checking

Every external theorem used in a proof should have a record:

```text
claim_id:
claim:
source:
exact locator:
source checked: yes/no
hypotheses checked: yes/no
used in:
status: verified / mismatch / inaccessible / unclear
```

Common failure modes:

- the paper exists but the cited theorem says something slightly different,
- a theorem is used outside its hypotheses,
- a result is remembered from a related field but does not apply here,
- the proof cites "standard" machinery without naming the exact result.

If a reference cannot be verified, it should not be used in a final proof branch.

## Recurrence Modes

Recurrence is the pre-proof research stage. It now has two modes.

`explore` mode is the pre-proof wandering stage. It should create:

- positive directions: strengthenings, bridge lemmas, special cases, analogues;
- negative directions: obstructions, counterexamples, sharpness tests, false strengthenings;
- a conjecture ledger with evidence and status;
- a ranked approach queue for the decomposer;
- no-output decisions for branches that should not consume proof-search budget.

This stage intentionally behaves like a mathematician walking around the problem with a notebook. It should not rush to a proof. It should make the problem landscape more legible.

`attack` mode is for a human conjecture or statement that should be taken seriously. It should:

- lock the exact statement and its quantifiers;
- enumerate proof methods and their bottleneck lemmas;
- enumerate disproof methods and counterexample shapes;
- run cheap exact tests or searches where possible;
- record a method matrix and counterexample-search log;
- decide whether the next stage should prove the conjecture, verify a counterexample, attack a bottleneck, or ask for human input.

But it must recur to the target. Every serious branch should be classified by what it contributes to the original conjecture:

- direct progress,
- reduction,
- obstruction,
- finite evidence,
- side result,
- dead end.

If a branch cannot be tied back to the target, it should be marked as a side result or refused. Do not let the agent optimize for interestingness.

## Campaign Execution

Do not use one run for an entire research agenda. Use one problem file per target and a campaign runner to process the queue.

Recommended campaign loop:

```text
runbook
 -> split into single-target problem files
 -> run_campaign.sh
 -> per-run proof/summary/recurrence artifacts
 -> extract memory
 -> update cluster map
 -> choose next target from conjecture_return_map.md
```

The unit of verification is a single target. The unit of research planning is a cluster.

## Strategic No-Output

The agent should stop a branch when:

- the same fatal gap survives two revisions,
- the proof depends on an unverified theorem,
- the statement being proved is weaker or different from the target,
- the branch requires a likely false strengthening,
- independent verifiers disagree and no human review is available,
- the checker cannot explain why the main step is true.

For research math, `UNCERTAIN` means do not submit. It may remain in the notebook as a possible human-review item.

## Artifact Contract

Every run should aim to leave these files:

- `related_info/difficulty_evaluation.md`
- `related_info/related_work.md`
- `recurrence/exploration_map.md`
- `recurrence/conjecture_ledger.json`
- `recurrence/approach_queue.md`
- `recurrence/no_output_decisions.md`
- `recurrence/approach_journal.md`
- `recurrence/conjecture_return_map.md`
- `decomposition/attempt_*/revision_*/decomposition.yaml`
- `proof.md`
- structural and detailed verification reports
- `proof_effort_summary.md`
- `TOKEN_USAGE.md`

The value of the agent is not only whether it solved the problem. It is whether it left a reusable research trail.
