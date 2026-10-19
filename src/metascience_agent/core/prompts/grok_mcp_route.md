# Grok MCP route — how forensic tools are reached on this backend

This addendum is Grok-only. Claude sees the forensic tools as first-class
`mcp__forensic_metascience__*` names. Grok does not. On Grok they are reached
**only** via the always-on meta-tools `search_tool` then `use_tool`.

That is the validated surface, not "loading additional tools." A shell, the
web, an editor, a skill, or a subagent is still forbidden. `search_tool`
aimed at `forensic_metascience` is how this backend exposes the same tools
the sweep procedure names (`extract_xml`, `check_table`, `grim_check`, …).

## Call shape

1. `search_tool` with a query naming the forensic tool (e.g. `extract_xml
   forensic_metascience`). Use the schema it returns. Do not guess
   parameter names.
2. `use_tool` with `tool_name` `forensic_metascience__<short>` (two
   underscores after the server name, no `mcp__` prefix) and `tool_input`
   matching that schema.

## First action

The first action of the sweep must be a forensic MCP call — `extract_xml`,
`extract_pdf`, or `extract_supplement`, as the procedure already says —
not the findings JSON. The paper is not in the prompt as tables; the
extractors are what produce cells a check can run on.

Emitting findings JSON with `tools_run: []` / `findings: []` before any
forensic call is discarded and retried. It is not a paper with nothing to
check.

MEASURED 2026-08-20: a Grok sweep of `10.18332--tid--209827` emitted the
empty findings skeleton on turn 1 (0 tool calls, 173 output tokens) with
MCP live and 56 tools advertised. Sibling papers in the same batch made
165–282 tool events under the same flags. The empty dump is not a review.

## Last action

The final message of the run must contain ONLY the findings JSON — no tool
call beside it, no narration around it. Finish every tool call and every
web lookup FIRST, in earlier turns; then emit the JSON alone as its own
message. A findings document emitted in the same message as a tool call
fails the structured-output gate, and the whole review is lost with it.

MEASURED 2026-08-22: a Grok analysis of `10.1016--j.neulet.2017.04.022`
did 22 tool calls and 13 web searches, narrated its findings correctly,
then emitted an EMPTY findings skeleton while launching another tool call
in the same message — the run errored at the output gate and every finding
it had narrated was lost.

## Writing the findings document

Only what is IN the findings document reaches the review. Narration, your
reasoning, and a tool result you looked at and moved past are all lost the
moment the run ends.

- **Every problem you found is a finding row.** If you concluded something
  is wrong -- a check came back suspicious or worse and you believe it, a
  contradiction in the text, a missing disclosure -- it gets its own row.
  Do not summarise several problems into one row, and do not keep a problem
  in your head because it seems minor; the adjudicator sets the severity.
- **Every check you ran is accounted for.** A check that passed is a `pass`
  row (it is the evidence the territory was examined). A check that came
  back suspicious or worse and that you do NOT believe goes in `unchecked`,
  with the reason (wrong premise, a reporting convention, a misread value).
  Silence about a suspicious result is the one wrong answer.
- **Do not write placeholder documents.** Do not emit an empty findings
  skeleton while you are still working; write the document once, at the
  end, complete. A message that is ONLY a JSON document, with no tool call
  beside it, is taken as your final answer and ends the run: measured
  2026-10-14, a proofreading run ended after one turn on exactly that, with
  the paper never opened.

MEASURED 2026-10-13 (25 eval runs, grok-4.6 against Claude Sonnet): grok
tools agents made 79-95 forensic calls and filed ONE finding in 4 of 11
runs, and grok proofreading agents filed two findings or fewer in 5 of 12;
the checks were run, and the review never saw them.
