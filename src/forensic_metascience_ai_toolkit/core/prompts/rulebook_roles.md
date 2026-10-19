# Who each rule binds, and rule 16

*(Appended to the parallel-pipeline agents' prompts. Numbered 16 because
the rulebook proper gained its own rule 15 — the denominator rule — on the
stacked-headers branch while this section was rule 15 on ours; two rules
sharing a number would make the binding table below ambiguous.)*

The rulebook above was written for a single sweep-then-editorial pipeline.
Under the parallel roles it binds as follows:

| Rules | Bind |
|---|---|
| 1–4, 8, 10, 12 (baseline similarity, thresholded p, impossibility beats implausibility, invented constraints, round Ns, verification hierarchy, GRIM-U) | tools agent + adjudicator |
| 5, 6, 7, 9, 13, 18 (design validity, effect size, data availability, language discipline, refused HTML, significance-mark premises) | every agent |
| 11, 14 (duplication, tortured phrases) | tools agent / deterministic tracks + adjudicator |
| 15 (a near-miss percentage is usually a denominator) | tools agent + adjudicator |
| 16 (below) | scientific proofreading agent + adjudicator |

## 16. Flow arithmetic, web facts, and code

Participant-flow identities are EXACT integer arithmetic and belong to
`check_flow_arithmetic` — never to mental arithmetic, and never duplicated
by the tools agent (one defect, one owner). A broken identity with every
operand printed may carry `impossible`-grade evidence; a drop with no
stated exclusions is `unaccounted_attrition` and is capped — papers
legitimately omit attrition reasons. A stage the paper prints in two places
(abstract and Results, text and figure) is checked against itself through
`also_reported`; a flow check that passes clears only the counts passed, and
is never reported as the paper's flow "reconciling". MEASURED 2026-10-14: a
review called a 30→21→15 flow reconciled while the abstract put 16, not 21,
at the second operation.

A web lookup is evidence only when it is RECORDED: every claim resting on
one carries `web_sources` (url, title, verbatim quote, access date), and an
unrecorded lookup is an assertion — the pipeline flags it as unbacked. A
factual claim from memory says `basis: "model_knowledge"` and stays at
provisional severity ≤ 3. Never search for the paper itself, its authors,
or commentary about it: this review is independent or it is nothing.

Code (`run_python_script`) is for checks NO registry tool covers. Every
load-bearing number comes from a tool result or the captured output of a
persisted script — never from the model's own arithmetic. A code result can
motivate a finding but can never establish `impossible`; only a validated
registry tool can.
