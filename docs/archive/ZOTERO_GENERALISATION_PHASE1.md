# Zotero generalisation pass, Phase 1

> **ARCHIVED 2026-10-16.** Interim (141 of 250 documents) and never closed; superseded within a day by the 211/217-paper figures in docs/VALUE_REGISTER_DESIGN.md. pdfplumber was not removed.

> Written 2026-08-18 and not revised since; status IN PROGRESS as of that date. Corpus paths in it predate the move under `test_pdfs/`.

**Status: IN PROGRESS.** 141 of 250 documents at the time of writing
(2026-08-18, ~05:45). The sweep is resumable and the numbers below will move;
every figure carries its denominator so a later reader can tell which ones did.

Task #168. The corpora this toolkit was built against are narrow --
`high_value_pdfs_to_run_on` is 97 recent biomedical and psychology papers almost
all with publisher XML, `cerebrolysin_papers` is one drug literature, and
`eval/ground_truth` is 78 curated cases. All were produced this century by
publishers with modern typesetting. Greg's Zotero library is 7,099 PDFs across
six decades and hundreds of venues, and it is the nearest thing to a real
population we have.

## How the sample was drawn

Deliberately, not randomly. A random draw from a neuroscience library returns
150 near-identical neuroscience papers, so the sample crosses **venue family**
with **era**, both flat rather than proportional:

| family | n | | era | n |
|---|---|---|---|---|
| other | 33 | | 2010s | 49 |
| unknown (no journal recorded) | 30 | | pre-2010 | 38 |
| clinical | 24 | | post-2020 | 38 |
| bench biology | 22 | | unknown | 16 |
| flagship multidisciplinary | 18 | | | |
| mega-journal | 14 | | | |

Documents are copied to an ext4 scratch tree before extraction, because the
cache is written beside the PDF and Zotero's storage is synced by the desktop
client. A measurement run must not leave artefacts in the library it measures.

## Extraction is robust

**137 of 141 extracted cleanly. Four honest refusals. One crash.**

Total extraction time 4.8 h; median 60 s, p90 245 s, max 2,199 s.

That is the headline non-finding, and it is worth stating plainly: docling
handles a six-decade, multi-publisher sample without falling over. The defects
below are almost all about what the toolkit SAYS when extraction is partial, not
about extraction failing.

## The bug list

### 1. The harness itself was inert (fixed, #174)

Found before the sweep launched, and the reason to check an instrument before
trusting a night to it. Both readers went cache-only when pdfplumber was
removed; `probe()` never ran docling, so every uncached document returned an
empty result that EXPLAINED ITSELF, which the classifier scored as
`honest_refusal` -- a pass. `silent_empty`, the one number the harness exists to
drive to zero, was 0 by construction. A 250-paper run would have reported a
perfect score while measuring nothing.

### 2. `extract_text` cannot say why it came back empty (#177, closed by declining)

It returns a bare `str`. When it cannot read a file it returns `""` and puts the
explanation in a `UserWarning` on stderr, invisible to any programmatic caller.
Its sibling `extract_text_with_tables` returns a dict with `error` and
`unreadable` and gets this right.

The call-site survey found the API change was not worth making -- nine of ten
`paper_text` callers already fail closed. But the one that did not was live, and
had two defects of its own (see 3). A ratchet now pins the call-site set so the
NEXT caller has to state how it handles an unreadable paper.

### 3. `preregistration` reported a paper as preregistered when it said it was not (fixed)

The worst find of the sweep, and it was reached by following #177 rather than by
looking for it. `_PREREG_TERMS` matches `pre-?regist\w+`, which fires on the word
inside a NEGATED sentence -- and a paper can only deny preregistration by using
the word. Because `terms` was tested before `explicit_none`, the
`explicitly_not_preregistered` branch was unreachable in exactly the case it
names. Measured: three of four denial phrasings returned `preregistered`.

Direction matters: this made papers look BETTER than they are, so it is a false
exoneration rather than a false accusation and the cardinal rule is not engaged.
It is still a statement contradicting the paper's own words.

The same function returned `not_mentioned` for empty text -- a claim about the
paper manufactured from our failure to read it. Now `unknown_no_text`.

### 4. Figures: 10 silent empties and 1 crash

`figures` is the least reliable path in the sweep: 107 ok, 23 honest refusals,
**10 silent_empty**, 1 crash. A silent empty here is the defect class the
harness was built to count -- nothing came back and nothing said so.

The crash is a corrupt file, and the message is correct:
`FileDataError: Failed to open file ... as type pdf` on a Kanazawa University
document. Worth keeping as a fixture.

### 5. Table recall: 1 paper, not the 5 first reported

The screen flags a paper whose prose says "Table N" while zero tables were
extracted -- the only form of zero worth opening by hand, since a genuinely
tableless paper and a recall failure are otherwise indistinguishable.

It flagged five. **Opening all five by hand, four are FALSE POSITIVES.** Every
"Table N" in them is a *Supplementary* Table N, which lives in a separate file
this run never saw and says nothing about the article's own tables. Finan et al.
2015 (Nat Med) cited eight of them, has no main-text table at all, and zero
extracted was exactly right.

| paper | raw hits | main-text hits |
|---|---|---|
| Finan 2015, Nat Med | 8 | 0 |
| Shen 2006, Nature | 2 | 0 |
| Longden 2017 | 2 | 0 |
| Mishra 2016, Nature Publishing Group | 1 | 0 |
| **Domingue 2024** | **1** | **1** |

So the real figure is **1 of 141**, and the screen has been fixed to exclude
supplement references. This correction is left visible rather than silently
applied: the first number appeared in this document, and a screen that counts
supplementary tables as evidence of missing main-text tables would have sent
somebody to open four papers that were fine.

## Numbers, with the corrections they needed

### Character corruption: 3.5% of papers corrupt DIGITS

| | n | share |
|---|---|---|
| flagged not-clean | 12 | 8.5% |
| of those, **corrupting digits** | **5** | **3.5%** |
| no text at all (fail-closed, correctly not "clean") | 4 | 2.8% |

**Only digit corruption can manufacture a finding.** A mangled operator
(`p , .01` for `p < .01`) misreads a symbol; a mangled digit reaches a check as
a number the paper never printed. The digit patterns seen are `equals as digit
5` (`p 5 0.05` for `p = 0.05`) and `operator lost before a decimal`.

**TWO CORRECTIONS TO EARLIER FIGURES IN THIS SAME RUN**, both worth recording
because they show how the number moved:

- At n=41 I reported **4.9%**. At n=141 it is **3.5%**. The first was a
  small-sample figure and should not have been quoted as firmly as it was.
- The 3-of-141 count was itself wrong when first computed. `glyph_corrupts_digits`
  was added to the harness MID-RUN, so 52 of the 141 records predate the field;
  counting its absence as False gave 3/141. Recomputing those 52 from cache
  found 2 more. The corrected figure is 5 of 141.

Corruption is **not** an old-PDF problem. The worst document in the first 41 was
Hall et al. **2014** in Nature, with 61 occurrences.

### Cell duplication: 1.38% upper bound, concentrated per-document

13,252 cells across 80 papers: 183 duplicated (136 text, 47 numeric), and **156
of them in ONE document** -- Rodas et al. 2024, Psychonomic Bulletin & Review.

This kills #152's hypothesis that duplication is one publisher's PDFs. The
corpus's worst case was MDPI; this sample's is Springer. Two samples, two
publishers, each dominated by a single paper. What generalises is the
CONCENTRATION, not the imprint, so a publisher-targeted repair would have fixed
the first sample and done nothing for the second.

The figure is an upper bound and cannot be made clean: four detector designs
each shrank under inspection (`14 : 14` is a ratio; `1 1` is undecidable between
one doubled cell and two adjacent equal ones; `NR NR` is plausibly two columns
both reading "not reported"). Docling normalises every grid to a rectangle --
ZERO ragged rows across 17 table sets -- so a merged cell leaves no structural
trace and the question cannot be settled from the extraction at all.

### Field applicability: `check_effect_plausibility` reaches 1 journal in 44

Its five surviving benchmarks are social/cognitive psychology, education,
medicine_rct and psychotherapy. The sample is Nature, Science, PNAS, JAMA, J
Neurochemistry, Molecular and Cellular Proteomics, Physiological Reviews.
Exactly one journal maps cleanly (Psychonomic Bulletin & Review). A few clinical
titles could use `medicine_rct`, but only if the study is actually randomised,
which a journal name cannot establish -- so the honest range is 2-11%.

"The tool rarely fires" and "the tool cannot apply to our literature" need
different fixes, and this is firmly the second. Recorded as #178, with an
explicit warning NOT to invent benchmarks for the missing fields: #167 closed
because a benchmark built from a misread correlation over-flagged by a factor of
two.

## Method notes worth keeping

- **`EXTRACT_TIMEOUT_SEC` bounds nothing.** One document ran 2,199 s against a
  900 s budget without interruption: `_budget` raises from a SIGALRM handler,
  and Python delivers signals between bytecode instructions while docling sits
  in torch/onnx C code. A real wall-clock bound needs a killable subprocess.
- **The sweep OOM-died once**, at record 52, while two paid model runs competed
  for memory. Nothing in the log; no traceback. It resumed with nothing lost
  because output streams per document, which is the only reason four hours
  survived.
- **A near-miss on the glyph recompute**: pointing `scan_paper` at the original
  Zotero path rather than the scratch workdir found no cache, returned clean for
  everything, and would have had me record 0% digit corruption.

## Still to do

- Finish the sweep (109 documents remaining).
- `_body_items` against an independent pattern sweep, hunting extraction
  conventions 5-7.
- Phase 2: the statistics register on ~15 papers spanning the conventions found.
- Open Domingue 2024, the one surviving recall suspect, and the 10 figure
  silent-empties by hand.
