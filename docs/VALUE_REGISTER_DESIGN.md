# The value register

> **Status (2026-10-16): built and live.** Every parallel-pipeline review calls
> `agent.build_value_register` from `parallel.write_parallel_outputs` (through
> a two-key shim mapping the tools agent and the proofreading agent onto the
> old stage slots; the adjudicator's spot re-checks are not joined). It calls
> `values.build_from_paper` and writes `value_register.json` beside the review,
> or `value_register.error.txt` naming the failure. The offline viewer
> (`bundle.py`) carries it in a Values tab, `metascience register-view` draws it
> on the paper (`register_view.py`), and `metascience repair-register` rebuilds
> it for an existing review. `scaffold/` also consumes `values`
> (`scaffold/interpret.py`), but the scaffold is not wired into the analysis
> pipeline. The design below is the 2026-08-18 plan; where it and the code
> disagree, the code wins.

Greg, 2026-08-18:

> in addition to the statistical anatomy, we should also have a list of ALL
> values/statistics reported in the paper. And obviously the model would
> represent how they are related (e.g. an SD belonging with a mean), and when
> the same value is used across checks. [...] It must be paired with the
> statistical anatomy though.

and, on what it is for:

> I have a vision where the user can hover their cursor over a value and see the
> network of related values, and all the associated checks for values of that
> type.

## The state of play: five corners, no edges

Every input this needs already exists. None of them are joined.

| Piece | Module | Carries | Missing |
|---|---|---|---|
| Mechanical enumeration of reported statistics | `completeness._body_items`, `_supplement_items` | `id`, `where`, `offset`, `kind`, `raw`, `context` | no value identity; one span may hold several values |
| The model's own list | `register` rows | `quote`, `values`, `source`, `checkable{tools, reason}` | `values` is an untyped blob; no per-value id; no roles |
| Typed table cells | `celltypes.ParsedCell` | `kind`, `value`, `sd`, `count`, `denominator`, `percent`, `decimals_*`, `markers` | ids are positional and not stable across extractions |
| The variables | `anatomy.Variable` | family, NOIR, discreteness, bounds, units, `n_items`, `derivation` | nothing points AT a variable from a value |
| What ran | dispatch check records | `check_id`, `tool`, `variable_id`, `inputs`, `severity`, `n_provenance`, `variable` | inputs are loose scalars; no link back to the value that supplied them |

So a mean and its SD are already captured together *inside one table cell*, and
already captured *apart* in prose — `_body_items` emits one item per regex
match, so `M = 4.20 (SD = 0.21)` in running text becomes two unrelated rows with
nothing saying they belong to each other.

The register is the join. It is not a sixth enumeration.

## What a value is

The unit is a **value**, not a row and not a finding.

```json
{
  "id": "val:body:14233:mean",
  "role": "mean",
  "printed": "4.20",
  "value": 4.2,
  "decimals": 2,
  "anchor": {"where": "body", "offset": 14233, "end": 14237},
  "group": "grp:body:14233",
  "variable_id": "v3"
}
```

`role` is the load-bearing field, and it is a closed vocabulary because every
consumer keys off it: `mean`, `sd`, `se`, `median`, `iqr_low`, `iqr_high`,
`count`, `denominator`, `percentage`, `estimate`, `ci_low`, `ci_high`, `n`,
`df`, `statistic`, `p`, `effect_size`.

`anchor` is what makes the hover UI possible and costs nothing new: prose items
already carry `offset`, and table cells already carry `(table, row, col)`. Two
anchor shapes, both already produced:

```json
{"where": "body",  "offset": 14233, "end": 14237}
{"where": "table", "table": "t1", "row": 4, "col": 2}
```

## What a group is

A group is the set of values that were **printed together and mean one thing** —
the relationship Greg asked for, represented by co-membership rather than by a
web of pairwise edges.

```json
{
  "id": "grp:t1:r4:c2",
  "kind": "mean_sd",
  "variable_id": "v3",
  "quote": "4.20 (0.21)",
  "anchor": {"where": "table", "table": "t1", "row": 4, "col": 2},
  "values": ["val:t1:r4:c2:mean", "val:t1:r4:c2:sd"],
  "applicable_tools": ["grim_check", "grimmer_check", "sprite_reconstruct"],
  "checks": ["r4.grim_check", "r4.grimmer_check"],
  "not_run": [{"tool": "sprite_reconstruct", "reason": "..."}]
}
```

`kind` is `celltypes`' existing vocabulary, unchanged — `mean_sd`, `n_percent`,
`count_denominator_percent`, `estimate_ci`, and the prose kinds from
`BODY_PATTERNS`.

`applicable_tools` is **derived, not authored**: it is `DISPATCH[(kind,
data_type)]` where `data_type` comes from the bound variable. That is exactly
Greg's "all the associated checks for values of that type", and it already
exists as a lookup table — the register only has to record what the lookup said.
The difference between `applicable_tools` and `checks` is the coverage number
the census currently computes, now stated per value instead of per corpus.

## The three edges that are new

1. **value → variable** (`variable_id`). The same edge the tool gate now
   enforces at call time, one layer up. A group carries it; its values inherit
   it.

2. **value → value across groups** (`same_value`). Greg's "when the same value
   is used across checks". Computed, not authored: two values with the same
   printed literal and the same role, in the same paper. This is what makes
   deduplication possible — and dedup has to happen at the VALUE layer, because
   the same n = 93 legitimately appears in twenty groups and is one fact.

3. **group → check** (`checks`). Written by the dispatcher when a check runs,
   so a reader can go from a printed number to every verdict that consumed it.

## Why this is worth building

Three things it fixes that are open today.

**The coverage log becomes per value.** `census` currently reports
`n_consumable / n_routable / n_runnable / blocked_on_declaration /
blocked_on_input` as corpus-level counts. With a register those become
properties of individual values, so "why was this number never checked" has an
answer at the point a reader is looking.

**Dedup.** Repeated identical checks are observable in the archive — two
byte-identical `grim_percentage` findings, same inputs, same location, in one
run. The precise rate is being measured separately. Value identity is the only
level at which dedup is correct, because identical inputs from *different*
printed values are two real checks and identical inputs from the *same* value
are one.

**Batch dispatch becomes the default.** Once the register exists, the model's
job is to assemble it; the checking is a deterministic pass over it. That is
what `check_table` already does for one table, generalised to the paper. It
removes N tool-call round-trips and, with them, N chances to restate a number
differently from the anatomy — which is the failure the tool-boundary gate now
catches after the fact.

## What this does NOT change

The register does not become the denominator. `completeness`' regex floor stays
exactly where it is and keeps its job:

> THE FINDER SHOULD BE THE MODEL. THE DENOMINATOR MUST BE INDEPENDENT OF THE
> FINDER. -- `register.py`

A model that both enumerates and checks reports full coverage of whatever it
happened to notice. The register is the finder; the regex floor is the tripwire
that says what the finder missed. Making the register the denominator would
rebuild the exact defect that module was written to prevent.

## Build order

1. `values.py` — the value/group records, ids, and the derivation of
   `applicable_tools` from `DISPATCH`. Pure functions over existing outputs; no
   model involvement, no new extraction.
2. Build the register from what already runs: `celltypes.parse_cells` for
   tables, `completeness._body_items` for prose. Both already produce everything
   but the ids and the roles.
3. `same_value` edges and dedup.
4. Dispatcher writes `checks` back onto groups.
5. The hover UI over the markdown and the table JSON. Inline in the PDF is
   secondary and should stay secondary — the anchors support it either way.

## First corpus measurement (2026-08-19)

The first measurement of the built register on a heterogeneous corpus, with
both the prose and table rails working (the full measurement notes were
removed from the repository on 2026-10-19 and remain in git history):
58 Zotero papers gave 5,049 groups and 5,899 values, 61% from tables and 39%
from prose. By class: 48.8% descriptive, 32.8% unknown, 17.4% inferential, 1.1%
design. Of 34,916 numerals, about half were judged (`share_judged` 0.507). That
is not a coverage figure; the unknown share mostly reflects runs that declared
no variables.

## Open questions for Greg

- **Prose relationships are the hard half.** A table cell already binds mean and
  SD; prose does not. Grouping `M = 4.20 (SD = 0.21)` needs either a wider
  pattern than `BODY_PATTERNS` uses, or the model to do the grouping. Given
  `register.py`'s own argument — that recognising a reported statistic is what
  the model is good at and a regex is a poor enumerator — the model should
  group, with the regex floor still checking that nothing was dropped.
- **Where the register lives.** A separate `register.json` artefact, or a
  section of the existing anatomy artefact? It has to be joinable to both the
  anatomy and the check records, and it is large. *ANSWERED: a separate
  artefact, `value_register.json`, written beside each review (see the status
  note at the top).*


## Next objectives

**DERIVING AN INPUT THAT UNBLOCKS A CHECK** (agreed 2026-08-18, to follow the
traversal A/B). Missing `n` blocks 312 cells across 11 archived runs -- 100% of
the missing-input class -- so deriving it is the largest coverage lever
available. One derivation already exists and is the template:
`dispatch._section_denominators` recovers `n` by summing a section's exhaustive
counts, and ships with three guards -- it is VERIFIED (accepted only if it
reproduces every percentage that section prints), CAPPED
(`_DERIVED_N_CEILING`), and RECORDED (`n_provenance.derived`).

Candidates: `SD = SE√n` and its inverse; `n` from `df` given the design; a
count from percentage x n; a missing group `n` from the total minus the others.

WHAT MAKES ONE SAFE IS NOT THE ALGEBRA. It is the direction of error when the
derivation's premise is wrong, and that is a property of the (derivation,
check) PAIR. One wrong `n` makes `check_count_percent` accuse an honest paper
-- the computed percentage diverges from the printed one -- while making GRIM
more permissive, since granularity is 1/n and a larger n admits more means. So
each pair needs its own direction analysis, and pairs that err toward accusing
must be refused. The flawed-paper simulator (Greg's §3c) is the instrument:
generate papers with known-correct numbers, derive the missing inputs, and
count how often a derivation manufactures a finding that is not there.

SEQUENCED AFTER THE A/B deliberately. The A/B measures whether register-first
ordering is faster and more complete with the derivation rules HELD FIXED;
adding derivations changes what is checkable at all, which moves the coverage
denominator and makes the comparison unattributable.

## Extraction settings, checked 2026-08-18

Greg asked whether the Zotero sweep might have used a docling configuration
missing flags that matter. It did not, and the check is recorded so nobody
repeats it.

Both corpora go through `extraction/docling_tables.py`, which builds a bare
`DocumentConverter()` -- no options passed -- so both get docling's defaults,
identical extractor (`docling`), version (`2.119.0`) and cache schema (4).
Those defaults are already the settings worth having:

    do_ocr                            True
    do_table_structure                True
    table_structure_options.mode      accurate      (not FAST)
    table_structure_options.do_cell_matching  True

So the low judged-share on the Zotero corpus was not caused by a degraded
docling configuration.

**CORRECTED 2026-08-19, and the original sentence was the house error.** It
read: "the 22%-judged figure on the Zotero corpus is a property of a
heterogeneous literature, not of a degraded extraction." The first half does not
follow from the second, and it charged OUR gap to the papers -- which is the one
inference this repository exists to refuse.

Measured after the defects found since, `share_judged` on that corpus is
**0.5070**, not 0.22. Three of our own faults were in the 22%:

  - `completeness._read_body` returned ZERO characters for all 217 papers,
    because `_article_pdf` demanded a DECLARED article and these directories
    hold a bare `paper.pdf`. The prose half of every manifest was empty.
  - Font-glyph damage was refusing values and, worse, mis-reading them: a
    `p < 0.05` arriving as a p of ZERO, an effect of `-0.85` arriving positive.
  - Citation years in multi-year and lettered citations were unclassified, and
    front matter was not separated at all.

The heterogeneity is real -- 6.2% of those papers have no recognisable section
heading, and several are not research papers at all -- but it was never
established as the cause of that number, and it was not.

The rule the original sentence broke: a low coverage figure is OURS until
measured otherwise. Ruling out one cause is not evidence for another.

The check also settled what the serialised table rows in body text ARE. The
cached `text` is `doc.export_to_markdown()`, and docling's markdown export
renders tables as pipe rows by design -- so every table appears twice, once
structured in `tables` and once as markdown in `text`. `numerals`' `table_cell`
class is therefore not repairing damage; it is attributing a value that exists
in two representations of one document, which is why routing it to the table
pass rather than the prose floor is correct.

OPEN, AND NOT INVESTIGATED: the sweep log carries repeated `RapidOCR returned
empty result!` warnings. OCR is enabled and returning nothing on some pages,
which is either a correct "this image holds no text" or a silently failing OCR
path. Given this repository's history with degraded results that do not
announce themselves, the two should be told apart.

## Three classes of value, and the one the register does not hold

Greg, 2026-08-18:

> statistics presented in a paper (both the prose as well as the tables) are
> purely descriptive, and not part of any inferential test (e.g. mean age of
> participants). [...] they seem distinct enough to handle in a different way.

He is right that they are distinct, and the split was already in the code
without a name. Every key in `dispatch.DISPATCH` is a descriptive form --
`mean_sd`, `mean_se`, `n_percent`, `count_denominator_percent`, `estimate_ci` --
and `statcheck` appears ZERO times in that module; the inferential checks reach
a paper by the prose rail instead. Two rails already existed. `values.role_class`
names the seam: `descriptive`, `inferential`, `design`, `unknown`.

One correction to the framing, and it is load-bearing. CLASSIFY BY WHAT THE
VALUE IS, NOT BY WHETHER IT WAS TESTED. Whether a mean age was tested for
baseline balance is a fact about the paper's analysis, not about the number, and
the "was it tested" rule misfiles precisely the values `csf` and
`table1_dispersion` exist to consume -- those work ON the p-values attached to
baseline descriptive comparisons.

Descriptives are also not the lesser class. The whole granularity family --
GRIM, GRIMMER, SPRITE, DEBIT -- is defined only on them, and an impossible
descriptive is the stronger finding: it says the numbers could not have come
from any dataset, rather than that one derivation slipped.

### MEASURED, and this is the gap

Class distribution over 1,010 values from the first 25 cerebrolysin papers that
build a register, with no anatomy supplied:

    unknown        465   46.0%
    descriptive    378   37.4%
    inferential    167   16.5%
    design           0    0.0%

Two readings, both worth acting on.

**46% unknown is Greg's ordering constraint, measured.** He required the
classification surface to come after the statistical anatomy, "since otherwise
the model would need to derive the variable characteristics of the printed
values in a vacuum". Undeclared, nearly half the values cannot be classed at
all -- an undeclared `4.20 (0.21)` is `ambiguous` to the parser and its values
are honestly `unknown`. The anatomy is what converts that residue into means and
SDs. The number says how much of the register depends on it.

**`design` is 0, and that is a real hole, not an empty category.** `_CELL_ROLES`
emits no `n` and no `df` from any cell kind, and `denominator` only from the
rare `12/30 (40.0)` form. Yet `n` is the value that GATES `grim_check`,
`grimmer_check`, `sprite_reconstruct`, `debit_check` and `check_count_percent`,
and it is 100% of `census.blocked_on_input`. It reaches the dispatcher by being
parsed out of a COLUMN HEADER (`Placebo (n ¼ 68)`) and passed as an argument --
so the single most consequential number on the page is never indexed as a value.

Scale, measured over the 305-paper corpus: 180 papers (59.0%) print an `n = ...`
somewhere, 1,651 occurrences in all, and 61 papers (20.0%) print one inside a
markdown table row.

Two consequences, both on the register's stated purpose:

- The hover UI shows a mean, shows that GRIM ran on it, and has NO NODE for the
  n that made the check possible. The "network of related values" is missing its
  hub.
- "Why did this check not run" cannot be answered by pointing at an absent
  value, because that value was never a candidate. The coverage log can say
  `blocked_on_input: n` but cannot show the reader where the n should have been.

FIX: index header- and label-borne `n` as a `design` value with its own table
anchor, and have the dispatcher's `n_provenance` name that value's id rather
than restating a bare integer. That closes the loop from a check back to every
value it consumed, which is what the register is for.

### CORRECTION to the class distribution above (same day)

The 46/37/16/0 split is a PROSE-RAIL measurement and was labelled as though it
covered tables. It does not. Re-measured with the two rails separated, over the
same 25 papers and 1,010 values:

    prose   986 values  (97.6%)   unknown 441 · descriptive 378 · inferential 167
    table    24 values  ( 2.4%)   unknown  24

Why: `prepass.paper_tables` reports, for essentially every paper in this corpus,
`<paper>.pdf has not been table-extracted yet, and this caller does not run
extraction`. Measured across all 309 directories, 306 (99.0%) yield zero table
cells to an offline caller, against 7,048 markdown pipe rows in the same
corpus's `body.md` files (22.8 per paper). The tables are there; the extraction
step that turns them into cells had not been run for the harness I measured
with.

THE CODE DID THE RIGHT THING AND THAT IS WHY THIS WAS FINDABLE. Every one of
those papers rode a `problems` entry saying extraction had not run, rather than
returning an empty list -- the exact discipline `_article_pdf_tables` documents
("'We could not read this PDF' and 'this paper has no tables' are opposite
facts"). The guard turned a silent zero into a legible one. I still misread it
once, by taking a corpus-wide zero at face value.

So two claims must be separated, because only one of them is measured:

- REAL, AND VERIFIABLE BY READING THE CODE: `_CELL_ROLES` maps no `n` and no
  `df` from any cell kind, so a group size printed in a header was never a value
  even when the table WAS extracted. `design_values_from_cells` fixes that, and
  on the one corpus paper that does yield cells it produces exactly one design
  value -- `Placebo (n ¼ 68)`, governing 10 cells, linked from 6 groups.
- NOT MEASURED, AND NOT TO BE QUOTED: any corpus-wide rate for design values or
  for the table rail generally. That needs `metascience extract-tables` run over
  the corpus first. The `design = 0.0%` figure above is over-determined -- the
  missing role map AND an unextracted corpus both force it to zero, and the
  measurement cannot separate them.

One extraction defect worth keeping, found while checking the above by eye: on
`10.1007--s00702-004-0248-2` the second table's column header is truncated to
`'Placebo (n'` -- the `¼ 68)` is gone. A header ending in a dangling `(n` is
strong evidence that a design value was destroyed in extraction, and it is
currently indistinguishable from a table that simply never printed its n. It is
1 label in 309 papers, so it is not urgent; it is recorded because the failure
shape -- a lost value that looks like an absent one -- is the one this
repository keeps paying for.

### And a qualification on THAT correction

The dark table rail above is a property of the offline measurement harness, not
of the pipeline. A real run calls `extract-tables` before checking; my
`build_from_paper` loop does not, which is exactly what the `problems` entry
says ("this caller does not run extraction").

Checked against the archived runs, deduplicated by content hash because bundle
copies duplicate `findings.json` byte-identically (14 files -> 7 unique, the 2x
this repository has measured before): of 146 findings across 7 papers, **74
(51%) are located in a table**. The table rail works in production.

What this means for the register, stated plainly so no one has to re-derive it:

- The table half of the register is UNMEASURED, not broken. Measuring it needs
  `metascience extract-tables` over the corpus first -- roughly 309 papers of
  docling, hours of compute, so it is a decision rather than a step.
- Every corpus-wide register number recorded above covers PROSE ONLY and should
  be read that way.
- `design_values_from_cells` is verified on the one corpus paper that yields
  cells offline, and by unit tests. Its corpus-wide effect is exactly the thing
  the extraction run would tell us.

## Two challenges from Greg, 2026-08-18, both run rather than argued

### 1. "Worth running one of the Zotero papers with the optimized parameters"

Run, not reasoned. `fmt-zotero-stress/2766RYXQ/paper.pdf` converted twice: once
through a bare `DocumentConverter()` (the cached extraction) and once with the
four options set EXPLICITLY -- `do_ocr=True`, `do_table_structure=True`,
`table_structure_options.mode=ACCURATE`, `do_cell_matching=True`.

    explicit-optimal   119.5s   text 70,642 chars   7 tables
    cached (bare)               text 70,642 chars   7 tables
    IDENTICAL: True

Byte-identical markdown. The defaults ARE the optimized parameters, now measured
on a paper instead of read off a config. The earlier reasoning stands, but it
stood on the wrong kind of evidence until this run.

TWO OPERATIONAL FACTS THE RUN EXPOSED, both of which matter more than the null
result:

- **Live docling currently CRASHES on this machine.** The layout model goes
  through `torch.compile`, TorchInductor shells out to `g++`, and `Python.h` is
  absent because python3-dev is not installed -- so `predict_layout` raises and
  the conversion dies. Every cached extraction predates this. Anything that
  re-extracts must set `TORCHDYNAMO_DISABLE=1` (verified: that is exactly what
  turned the crash above into the clean run) or the machine needs python3-dev.
  *DONE IN CODE: `extraction/docling_tables.py` sets `TORCHDYNAMO_DISABLE=1`
  and `TORCH_COMPILE_DISABLE=1` (`_TORCH_ENV`, via `os.environ.setdefault`)
  before building the converter, so an explicit setting still wins.*
  This is the kind of failure this repo cares about: without the env var, a
  re-extraction sweep does not silently degrade, but it does stop dead, and a
  sweep that catches the exception per-paper WOULD render it as "this paper has
  no tables".
- **~120 s per paper.** Re-extracting the 309-paper cerebrolysin corpus is
  therefore ~10 hours of CPU, which is why running it is a decision and not a
  step.

### 2. "Have you been doing the automated replacement of conversion artifacts?"

Yes -- and not where I first went looking, which is why the check was worth
making.

`extraction.jats.repair_extraction_damage` has exactly ONE call site, the
`body.md` branch of `paper_text`. Table cells, table labels and the docling
`cached_text` path never see it. That looked like a hole, and it is not, because
the decoding that matters happens at the point of MATCHING instead:

- `completeness` decodes operator entities character-for-character before
  running `BODY_PATTERNS`, and slices `raw` from the SOURCE, so a pattern
  needing a literal `<` still fires on `p &lt; .05` while every offset stays
  valid against the original text. Verified on a real string: raw
  `"F (1,78) = 5.558; P &lt; 0.05"` yields both an `nhst` item and a `p_value`
  item, identical in count and position to the repaired spelling.
- `quotes` does the same through `_fold_operators` and `html.unescape`.

MEASURED over the 211 cached Zotero extractions, and the split is the point:

    artifact       in TABLES  papers      in TEXT  papers
    &lt;                   0       0         1655     118
    &gt;                   0       0          406      83
    &amp;                  0       0         4557     143
    named entities         0       0         6618     184
    vulgar 1/4 (¼)         0       0           75       7

Entities live in the prose and NOT in the structured tables -- zero occurrences
of any of them across every table in 211 papers. So the table path, which has no
repair, also has nothing to repair; and the prose path, which has the entities,
decodes them where it counts.

Confirmed empirically rather than assumed: `_body_items` over 120 Zotero papers
finds 6,566 statistics on raw text and 6,565 on repaired text. A repair that
changed nothing is the correct outcome here, not a failed repair.

ONE THING CORRECTED WHILE CHECKING: `repair_extraction_damage` is NOT
length-preserving -- every one of 120 papers changed length, up to 1,337
characters on `3753NELC`. That is not a defect, because its callers take offsets
against the string it RETURNS. But it is a different contract from
`completeness`' padded, length-preserving entity decode, and the two must not be
described interchangeably. They were, in an earlier note.

## Sections, and why the first version of them was dangerous

Greg, 2026-08-18:

> the better approach for the front matter and the citation section (and other
> sections I cannot think of at this moment) is to identify those sections and
> don't include them in the analysis of the extractable values.

Right, and it replaces a rule per shape of noise -- a citation-year rule, an
affiliation-superscript rule -- each covering only what it was written for. The
half he names is the one that matters: the sections nobody has thought of yet.

`sections.map_sections` labels every span ANALYTIC, FRONT_MATTER or BACK_MATTER.
The floor is untouched: `numerals.index` stays exhaustive and sections only
CLASSIFY, so a grant id in the acknowledgements is judged rather than dropped
and `share_judged` rises instead of the denominator falling.

### The first version ate real results

Classing everything before the first analytic heading as front matter is the
obvious rule and it is wrong, because A PAPER'S TITLE IS ITSELF A HEADING and
the section under it holds the abstract. Measured over 40 corpus papers, that
rule put **36 numerals already typed `statistic`** inside an excluded span:

    "reduced A-beta burden by 43% in the young group and by 27% in the older"
    "death of 60% of the animals"
    "0.8% carbon monoxide"

Front matter is now ONLY the identity block before the first heading, plus
headings recognised as publisher furniture (`accepted manuscript`, 111 of 119
corpus papers; `article in press`, 17). After narrowing, across the same 40
papers: 18,376 analytic, 16 front matter, 72 back matter -- and the three
remaining `statistic` rows in excluded spans are a grant number (`3.3/51 from
AKP`) and an ethics approval (`CUN-26-114/2022`). Those are correctly excluded,
and they are evidence the FLOOR mislabelled them rather than that the map is
wrong. Zero real statistics lost.

THE TRADE IS ONE-SIDED AND THE RULE FOLLOWS IT. A surplus number costs the model
one glance at something it will call noise. A dropped percentage costs a check
that would have run, and nothing downstream can tell that it is missing. Surplus
is visible; absence is not.

### Missing headings are real, and cost nothing

Greg, 2026-08-19: "some of the docling extractions lack the clear headers you'd
want in a markdown file."

Measured on the 211 cached Zotero extractions, the heterogeneous corpus:

    at least one recognised heading    198   93.8%
    headings, none recognised           13    6.2%
    no headings at all                   0    0.0%

Inspecting all 13: most are not research papers -- a CNN health piece ("story
highlights"), a Financial Times column, an APA news item, a rationality
checklist -- plus one severely OCR-damaged scan whose headings read
`~]sul~n evidence for the p`. For every one of them the map yields analytic
spans and excludes nothing, which is the designed behaviour: every unrecognised
heading is ANALYTIC, and a paper with no headings gets no front matter at all.
