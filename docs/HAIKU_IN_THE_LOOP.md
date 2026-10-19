# Is Haiku doing work in the pipeline, and could it be wrong?

Greg, 2026-08-18: "the opus agent orchestrating each stage of the pipeline is
capable of invoking the Haiku model in order to perform certain checks, or
extract information in some manner... my concern here is that the Haiku model
that is dispatched to perform a task might do a poor job and supply incorrect
information to the pipeline."

The question is prompted by `models_resolved` in `run_meta.json` listing
`claude-haiku-4-5-20251001` alongside the requested model on every run.

**Short answer: Haiku is invoked and billed on every run, but nothing it
produces enters the pipeline's data path.** The concern is well-formed and, on
the evidence available, not realised. One scenario that would change that is
named at the end, and it should be watched rather than assumed away.

## What was measured

Across **40 archived stage transcripts**:

| | stage 1 | stage 2 |
|---|---|---|
| Haiku input tokens | ~800-1,700 | ~15,000-36,000 |
| Haiku **output** tokens | 16-32 | 16-32 |
| Haiku cost | $0.0009-$0.0018 | $0.016-$0.041 |
| share of stage cost | 0.01-0.05% | 0.8-1.3% |

**Haiku's output never exceeded 32 tokens in any run.** That is the single most
informative number here: 32 tokens is a sentence. It is not enough to carry an
extracted table, a recomputed statistic, a finding, or a tool argument.

## Four independent checks, all negative

1. **Our code never asks for it.** `grep -ri haiku src/` returns exactly one
   hit, and it is a comment in `bundle.py` about this very phenomenon. No
   pipeline stage, tool or prompt requests Haiku.

2. **It appears in no content-bearing event.** Across both stages of a
   representative run, **0 of 156 assistant messages** name it. The findings,
   the tool calls and the report are all produced by the main model.

3. **It appears in exactly one place: the final `result` event**, which is the
   session's aggregate billing rollup keyed by model. That is a record of who
   was billed, not of who produced content.

4. **No context compaction occurred.** The only `compact` strings in the
   transcripts are entries in the CLI's list of available slash-commands. There
   were no compaction or summarisation events.

## The best-supported explanation

The stage-1/stage-2 asymmetry is the clue. Stage 1 has ~120 assistant messages
and feeds Haiku ~1,000 tokens; stage 2 has ~36 and feeds it ~30,000. So the
input does not scale with conversation length -- it scales with the size of the
OPENING message, and stage 2's opening prompt contains the whole stage-1 output.

That is consistent with the CLI invoking Haiku once, on the opening message, for
a short housekeeping answer -- a session title or similar. It is an inference
from the token profile, not something the transcripts state outright.

## The limit of this evidence, stated plainly

What is established: nothing Haiku wrote reaches the archived message stream
that becomes findings, and our code never dispatches it.

What is NOT established: what the CLI sends it, or what the CLI does with the
answer. Those happen inside the CLI and are not in our artefacts.

**The one scenario that would matter is context compaction.** If Haiku were used
to summarise a long conversation, that summary WOULD re-enter the main model's
context, and a poor summary could degrade what the analysis sees -- which is
exactly the failure Greg described. It did not happen in any of the 40 runs
examined, but those are runs that fit in context. A longer paper, or a stage that
runs hot, is where to look.

Cheap standing check, if it is ever wanted: assert that Haiku's output-token
count stays trivially small, and fail loudly if a run ever shows Haiku producing
hundreds of tokens. That is the signature that would distinguish a housekeeping
call from a summarisation that reached the model.

## Status (2026-10-16)

- The conclusion stands as of the evidence above; nothing since has shown a
  secondary model writing content that reaches the analysis.
- The measurements were taken on the serial pipeline. "Stage 1" and "stage 2"
  are its sweep and editorial stages, which were deleted in v1.27.0; the
  current pipeline runs two analysts and an adjudicator. The stage-1/stage-2
  token asymmetry above is evidence about that pipeline, and has not been
  re-measured on the current one.
- The standing check was built: `tripwire._no_secondary_model_wrote_content`,
  reading the per-model output tokens that `agent.py` records in
  `run_meta.model_usage`. It is reached only through `tripwire.check_run`, and
  neither `check_run` nor `check_report` has a production caller. The CLI
  (`analyze --tripwire`) calls only `tripwire.check_preflight`, before any
  spend. So the check exists and is tested (`tests/test_tripwire.py`) but does
  not run on real analyses.
- `grep -ri haiku src/` now returns two files, `bundle.py` and `tripwire.py`,
  both explanatory; still no code requests Haiku.
