# Stage 0: Acquisition

> **ARCHIVED 2026-10-16.** Steps 2-3 (adopt docling; route PDFs through its cache) shipped. The dossier, the strategist and the 'Stage 0' agent were never built, and the sweep/editorial pipeline it assumes was deleted in v1.27.0. Kept as the provenance of the docling decision.

**Status:** specification, not built. Written 2026-08-13.
**Author:** drafted by Claude at Greg's direction; every number here is measured
and dated, and the measurement command is named so it can be rerun.

---

## 1. The problem, stated as a measurement

Nobody owns the completeness of the INPUT.

The pipeline has a stage that sweeps a paper (1) and a stage that edits the
result (2). Both are judged on FINDINGS. Neither is judged on whether the paper
it read was the whole paper -- so when the supplement is missing, the incentive
is to start checking anyway, and nothing in the output distinguishes "this paper
is clean" from "we read a third of it".

Four measurements from 2026-08-13, each found independently, all the same defect:

| what | measured |
|---|---|
| corpus papers with no publisher XML | **308 of 315 (97.8%)** |
| numeric recall from PDF vs XML ground truth | **60.4%** with the current extractor, range 0.0-99.8% |
| checkable items living in supplements, in papers that have one | **90.4%** |
| `extract_supplement` calls in the entire archive | **12** |

The last row is the one that matters. The capability exists and works; it was
reachable only if the model elected to use it, and across every archived run it
elected to 12 times. The two papers holding 13,064 of the archive's 26,592
supplement items received none.

And the failures are SILENT, which is what makes them expensive. On a PDF-only
paper `prepass.paper_tables` returns zero tables and records no problem, so the
completeness manifest reports **0 table items** for a paper that has tables --
`10.1007--s00702-004-0248-2` has 8 findings located in tables against a manifest
saying it has none. A file we passed over is indistinguishable from a file that
does not exist.

---

## 2. Why a guiding intelligence, and not better heuristics

Greg, 2026-08-13: "I don't think the python tools are ever going to be
flexible/comprehensive/discriminating enough to extract the correct information
absent a guiding intelligence."

The evidence for this is embarrassing and it is ours. Five deterministic
heuristics were written or defended IN A SINGLE SESSION, every one of them at
the discriminating step, every one measured failing:

| heuristic | what it was for | measured |
|---|---|---|
| `_SI_HINTS` | is this file the supplement? | missed 5 of 9 publisher conventions, silently |
| letter-count in `computed` | is a method recorded? | passed 18 of the 18 cases it existed to catch |
| `, and` / `;` in a title | are these two defects? | ~50% false positives |
| 90-character title cap | is this heading scannable? | condemned 52.6% of well-formed titles |
| `_looks_like_supplement` | does this document hold tables? | written and deleted before shipping |

All five are the same error: a SYNTACTIC PROXY for a SEMANTIC PROPERTY. A model
reading the directory would have said "`EAT-58-1072-s001.docx` is obviously the
supplement to a paper in *Int J Eat Disord*" with no rule existing at all.

**The strongest evidence is the benchmark run to dispute the claim.** Marker was
installed to test whether better tooling closes the PDF gap. It does -- and
Marker is a VISION MODEL, not a smarter pdfplumber rule:

```
paper                           truth  plumb  marker  plumb%  marker%  secs
10.1001--jamanetworkopen.2023.37    524    325     424   62.0%    80.9%    28
10.1001--jamanetworkopen.2023.51    391      9     391    2.3%   100.0%    13
10.1002--ajcp.70049                 156      0     141    0.0%    90.4%   114
10.1002--eat.24415  (Romano)        169     88      75   52.1%    44.4%   214
10.1038--s41537-025-00576-3         847    845     847   99.8%   100.0%    33
10.3389--fnins.2023.1186751          32     28      28   87.5%    87.5%     9
10.3390--healthcare11101497          24      0      24    0.0%   100.0%   682
                                                  OVERALL 60.4%    90.1%
```
(`scratchpad/bench_pdf_tables.py`, recall over distinct numeric literals in
table rows only, so neither extractor is credited for numbers sitting in prose.)

**Intelligence fixes the catastrophic cases.** Three papers where the current
path recovers essentially nothing -- 2.3%, 0.0%, 0.0% -- become 100%, 90.4% and
100%. That is the whole argument for §2 in one column.

**A claim in the first draft of this spec was wrong, and the correction
matters.** It said that because Marker loses on Romano, "even the choice of
extractor is a per-paper judgement, and no fixed rule makes it". Computing the
oracle -- pick the better extractor for each paper, knowing the answer in
advance -- gives **90.7% against Marker's 90.1%. Routing is worth 0.6
percentage points**, and Marker loses on exactly one paper of seven. So the
aggregate case for per-paper routing is weak, not strong, and I had reached for
the conclusion that suited the argument.

What survives the correction is narrower and still real: a single extractor has
a per-paper failure mode that the aggregate hides. On Romano, using Marker
alone loses 13 of 169 numbers, and which 13 is not knowable without the XML we
would not have. That is an argument for MEASURING per paper and reporting the
uncertainty -- which is §4 -- rather than for building a router.

**Timing is recorded and is NOT a decision input.** Marker ranges 9 s to 682 s
per paper on CPU; Docling did that same 682 s paper in 43 s. I led with the
speedup, and Greg corrected the framing on 2026-08-13: "the speed of the
extraction is pretty inconsequential compared to the gains on extraction
quality."

That is right, and it is not merely a matter of emphasis. A run costs ~$12 and
minutes of model time; 682 s once per paper, cached per file hash, is noise
against it. Ten points of recall is numbers that are permanently invisible to
every check downstream. **Extractors are therefore chosen on recall alone.**

It also has a design consequence that outranks the choice of extractor. If time
is nearly free, the ceiling is not the best single tool but the UNION of what
all of them see -- run pdfplumber, Marker and Docling, keep every value any of
them recovered, and the reader is shown what was recoverable rather than what
one tool happened to catch. The benchmark now scores that union alongside the
individual tools, and it is the number this section should be read against.

The union has a cost the individual tools do not: a value only one extractor
sees is a value with weaker provenance, and disagreement between extractors is
itself information the dossier should carry (§5) rather than silently resolve.

### What survives from the "deterministic" position

Not the deterministic/intelligent split. A different one: **DECIDE versus
RECORD.**

- Intelligence DECIDES: what this paper contains, what is missing, which
  extractor to believe, when to stop, when to refuse.
- Code RECORDS: every decision, with its evidence, in a form that reruns
  identically and that a reader can audit.

This is the rule already adopted for arithmetic on 2026-08-13 -- the model may
do work no registered tool covers, but it may not do it invisibly. Stage 0
applies the same rule one layer earlier.

---

## 3. Scope

**Stage 0 owns:** everything from "here is a DOI or a directory" to "here is a
dossier the sweep can consume", and the honest accounting of what it could not
get.

**Stage 0 must never:** run a forensic check, assign a severity, or form an
opinion about the paper's correctness. It reports what the paper CONTAINS, never
whether the paper is RIGHT. Keeping that boundary is what keeps the audit clean:
if acquisition can also accuse, a reader cannot tell an extraction artefact from
a finding.

**One hard interface rule.** The dossier is stage 1's ONLY input. Not its
preferred input -- its only one. This repository's signature defect is the
feature that is built, tested and consumed by nothing (`grace.py` shipped with
12 tests and zero callers; `completeness` written into every run and rendered
nowhere). A stage 0 that stage 1 can bypass will be bypassed.

---

## 4. THE DENOMINATOR IS THE PRIMARY DELIVERABLE

Greg, 2026-08-13: "something you've been able to do is actually quantify the
extent of the missing info (i.e. the denominator). Even if no extraction tool is
perfect, that quantification alone would be highly informative to the reader of
a report."

This reframes the stage. Stage 0's job is not "get everything" -- it will not --
it is **to know and state exactly what it did not get.** A report that says "we
checked 122 statistics" is a claim about our effort. A report that says "this
paper's evidence comprises an estimated 741 reportable quantities; we obtained
514; we could extract 400; 122 were checkable; here are the 227 we could not
reach and whose limit each one was" is an instrument reading. Only the second
can be trusted, and only the second gets better in a way anyone can see.

### The custody chain, and where the losses are attributable

Every drop between tiers has a different owner, and conflating them is how our
failure gets recorded as the paper's property:

| tier | what it counts | who owns a loss here |
|---|---|---|
| T0 **implied** | quantities the paper's own text implies exist ("Table S3 reports...", "data at OSF...", n comparisons across k arms) | the paper, if it never reported them |
| T1 **published** | what the publisher actually distributes: article, SI files, deposited data | the publisher / the licence |
| T2 **obtained** | what we hold on disk | our fetcher, or a paywall -- and these are different facts |
| T3 **extracted** | what came out of those files as structure | our extractors |
| T4 **checkable** | what a check can consume as reported | the paper's reporting (a mean with no n) |
| T5 **checked** | what actually ran | stage 1 |

This is the Sankey the flow census already draws for the checking half. Stage 0
extends it left, into the half where the losses are currently invisible: today
the pipeline's denominator starts at T3 and everything lost before it is
unrepresented.

### The case that arrived by accident: cell repair

Greg, 2026-08-13, on watching Docling's output get inspected: "what you just
observed is a perfect use case for that other agent, since it could see the
problems you just identified, and split that concatenated column into two
distinct columns."

This is the strongest argument in this document for stage 0, and it is evidence
rather than reasoning. Adopting Docling (§2) and then LOOKING AT ITS CELLS
rather than its score turned up:

    row_label "Sample size Sample size"    -- the phrase repeated
    raw       "100 100"                    -- the value repeated
    raw       "1050 EUR 93 1050 EUR"       -- repeated AND merged with the
                                              neighbouring column's 93

A reader with the column headers in front of them sees instantly that the 93
belongs to the Standard Treatment column and that the phrase is doubled. NO RULE
DISTINGUISHES THAT FROM A LEGITIMATE VALUE -- "1050 EUR 93" could be a genuine
cell in another paper -- so this is precisely the discriminating judgement §2
says a heuristic cannot make, arriving as a concrete task rather than a
principle.

**And it is invisible to the benchmark that chose the extractor.** That paper
scores 100% recall, because recall is measured over DISTINCT NUMERIC LITERALS
and "100 100" contains "100". Every metric in §2 is blind to duplication, to
cross-column merges, and to a value landing in the wrong row. Cell-level ground
truth (deliverable 1b) is therefore not a refinement; it is the measurement that
would have caught this, and it should be built before any claim is made about
extraction QUALITY as opposed to extraction COVERAGE.

**T0 is the novel and valuable tier**, and it is only reachable by reading the
paper. "The paper cites eTable 3 and we have no SI" is a fact no file-system
walk can produce, and it is exactly the fact a reader most needs. It is also
where a model is strongest and a heuristic is weakest.

### The rule that keeps the denominator honest

Every tier count carries `measured` or `estimated`, and an estimate carries its
method. **A tier we could not measure reports `null`, never `0`.** Absence read
as evidence is entry 1 of `LESSONS.md`, and this stage is where the temptation
is worst: an empty directory and an unfetchable supplement produce the same
silence.

---

## 5. The dossier

One JSON artefact per paper, plus the normalised files. Sketch, not final
schema:

```jsonc
{
  "paper_id": "10.1002--eat.24415",
  "inputs": [                       // every file, its role, and WHO SAID SO
    {"name": "10.1002--eat.24415.xml", "role": "article",
     "declared_by": "doi_stem", "extractor": "jats", "confidence": "exact"},
    {"name": "EAT-58-1072-s001.docx", "role": "supplement",
     "declared_by": "article", "extractor": "docx", "confidence": "exact"}
  ],
  "content": {
    "tables": [ /* normalised: label, source file, cells, extractor, per-table confidence */ ],
    "prose_statistics": [ /* located quantities with their spans */ ],
    "figures": [ /* including "values exist only as pixels here" */ ]
  },
  "denominator": {
    "implied":   {"n": 741, "basis": "estimated", "method": "…"},
    "published": {"n": null, "basis": "unmeasured", "why": "…"},
    "obtained":  {"n": 514, "basis": "measured"},
    "extracted": {"n": 400, "basis": "measured"},
    "gaps": [
      {"what": "eTable 3", "tier": "obtained", "owner": "licence",
       "evidence": "EuropePMC: 'not open access'", "recoverable_by": "library proxy"}
    ]
  },
  "decisions": [                    // THE LEDGER -- see §6
    {"decision": "used marker over pdfplumber for Table 2",
     "why": "pdfplumber returned 1 row for a 14-row table",
     "evidence": {"plumb_rows": 1, "marker_rows": 14}}
  ],
  "verdict": "complete" | "partial" | "refused",
  "note": "one paragraph a human reads first"
}
```

Stage 1's prompt then opens with the dossier's `verdict` and `denominator`, so a
sweep over a partial paper KNOWS it is one.

---

## 6. What the strategist may and may not do

**May decide:**
- which files are the article, supplements, data, or irrelevant
- which extractor to trust per file, and per table where they disagree
- what the paper implies exists but does not contain (tier T0)
- what to go and fetch, and in what order
- whether acquisition is complete enough to proceed, or must refuse

**May not:**
- assert content that no extractor produced. It routes and labels; it never
  supplies a value. Every number in the dossier traces to an extractor that ran,
  exactly as every number in a finding traces to a tool that ran.
- run any forensic check, or characterise the paper's quality
- silently drop a file. An undeclared or unreadable file is a REPORTED state.
  This is already enforced in `supplements.classify_inputs` and stage 0 inherits it.

**Every decision is written to `decisions[]` with its evidence.** The test is
the one Greg set for arithmetic: it must be impossible for the agent to make a
choice that affects the output and for that choice not to be recorded.

---

## 7. The eval comes FIRST

**Do not build the agent first.** We would be replacing five heuristics I can
prove are bad with one judgement nobody can measure, which is a worse position
even if the judgement is better.

**Deliverable 1: the acquisition eval.** Seven papers in this repo ship BOTH the
publisher's JATS XML and the PDF. The XML is not an estimate of what the tables
contain -- it IS what they contain. So for those seven, acquisition has a ground
truth, and any agent's recovery is measurable rather than trusted.

`scratchpad/bench_pdf_tables.py` is the prototype; it needs to move into
`eval/`, gain the supplement and prose tiers, and report per-tier recall.

Its limits, stated up front so they are not discovered later:
- **n = 7**, and all seven are open-access papers that HAVE an XML, which is
  exactly the population least likely to be hard. This is a floor on difficulty,
  not a representative sample.
- it measures numeric recall, not whether a value landed in the right cell. A
  number recovered into the wrong row is worse than one lost, and this eval
  scores them the same. Cell-level accuracy is deliverable 1b.

**Deliverable 2 is ANSWERED. Adopt Docling. Do not build an ensemble.**

Greg, 2026-08-13: "search the web for other (free) PDF extraction tools that can
handle tables. For all I know, some might be better than Marker." He was right
to stop me -- I had made Marker the default after testing exactly one
alternative. The neutral academic benchmark (arXiv 2511.16134, 15 methods over
four scientific-PDF datasets) puts DOCLING top at F1 0.96-0.99 and the
pdfplumber/Camelot/PyMuPDF family at 0.09-0.41. Measured here on our own ground
truth, that prediction holds exactly:

| tool | precision | recall |
|---|---|---|
| pdfplumber (current) | 88.3% | 60.7% |
| marker | 87.0% | 90.0% |
| **docling** | **92.0%** | **95.9%** |

**Docling wins on BOTH axes, so there is no trade to make.** Recall goes from
60.4% to 95.8% -- 35 points, and the single largest improvement available to
this pipeline from any change described in this document.

And the combination strategies are both dead, for a reason worth recording:

- ROUTING (pick the best tool per paper): oracle 96.2% vs Docling 95.8%. +0.4.
- UNION (run all three, keep everything): 96.4% vs 95.8%. +0.6 recall -- AND IT
  COSTS PRECISION, because the union inherits every tool's false values. Marker
  alone contributes 281 numbers absent from ground truth against Docling's 175.
  A plausible wrong number is the worst output this system produces, so trading
  precision for 0.6 points of recall is the wrong direction.

I proposed routing, measured it, dropped it; then proposed the union, measured
it, and it is worse. Twice I reached for an architecture when the answer was
"use the better component". Recorded here because the pattern is more useful
than either result.

WHAT THE PROVENANCE NUMBERS SHOWED, since they were the argument for an
ensemble: of 2,087 ground-truth values, 57.0% are recovered by all three tools,
36.1% by exactly two, 3.3% by exactly one (59 of those 69 Docling-only), and
3.5% by none. Cross-tool agreement is therefore a real confidence signal -- but
it is not worth a second extractor's false values to obtain, and Docling alone
already recovers 95.9% of what is there.

**Deliverable 3:** the agent, scored against 1 and 2.

---

## 8. How stage 0 is scored

It gets its own scorecard, or we cannot tell a good acquisition from a lucky one:

- per-tier recall against ground truth where it exists
- **refusal rate, and refusal precision** -- how often it says "incomplete", and
  how often it is right. A stage that never refuses is not being careful, it is
  being quiet.
- decision-ledger completeness: every routing choice recorded, checkable by the
  same audit that checks findings
- cost and wall-clock per paper

A regression in any of these fails the run, exactly as the suite fails.

---

## 9. Cost, honestly

A third LLM stage per paper, on top of a ~$12 two-stage run. Reasons to think it
is not a third of the cost again:

- most of its turns are cheap: reading a directory listing, a fetch record, an
  extractor's summary
- it should REDUCE stage 1 cost, because stage 1 currently spends turns
  discovering its inputs
- it runs once per paper and its dossier is cacheable across re-runs, where
  today every re-run re-discovers everything

To be measured on the first three papers, not assumed.

---

## 10. How this fails

Named now so they can be designed against:

1. **It becomes another unread artefact.** Mitigated by the hard interface rule
   (§3): the dossier is stage 1's only input.
2. **It papers over gaps with a plausible dossier.** The worst failure available
   -- a confident, complete-looking package of a paper we barely read. Mitigated
   by §6 (may not assert content) and §8 (refusal precision is scored).
3. **The denominator becomes a number nobody can defend.** T0 is an estimate. If
   it is published without its method and its basis, it is the "56.5%" problem
   from the MO site audit, reproduced by us.
4. ~~**It slows the loop.**~~ DOWNGRADED 2026-08-13. Extraction runs to 682 s
   per paper, but it is once per paper, cacheable per file hash, and trivial
   beside a ~$12 model run. Deciding an extractor on speed would trade recall
   for a cost nobody is paying. Cache it and stop thinking about it.
5. **Scope creep into checking.** The boundary in §3 is load-bearing; the moment
   stage 0 forms an opinion about the paper, its errors become accusations.

---

## 11. Build order

1. eval harness into `eval/`, per-tier, on the 7 ground-truth papers
2. ADOPT DOCLING as the extractor, cached per file hash. Measured 92.0%
   precision / 95.9% recall against 88.3% / 60.7% for the current path. Routing
   (+0.4) and the union (+0.6 recall, worse precision) were both measured and
   both dropped -- one good component beat both architectures.
3. `prepass` reads PDFs, not only XML -- so the manifest stops reporting 0 table
   items in silence on 97.8% of papers. **This is worth doing regardless of
   whether stage 0 is built**, and is the single highest-value fix outstanding.
4. the dossier schema, written and rendered before an agent fills it
5. the strategist, scored against 1-2
6. stage 1's prompt rewritten to consume the dossier and to open with its
   verdict

Steps 1-3 are useful on their own and none requires the agent to exist. That is
deliberate: if the spec is wrong, we find out having built three things worth
keeping.
