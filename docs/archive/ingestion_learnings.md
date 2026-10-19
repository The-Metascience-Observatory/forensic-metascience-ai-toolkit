# Ingestion learnings — the preserved inventory

> **ARCHIVED 2026-10-16.** Dated 2026-08-21; file:line references are as of that date (the docling cache schema is now 7, and `fetchpdf-verify` is wired into preflight).

**Status:** approved 2026-08-21 as part of the overhaul plan (Part D).
**Provenance:** compiled 2026-08-21 from a full exploration of
`/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/pdf4llm` (retired from the
paper workflow by that plan) and this repo's extraction stack. File:line
references are to those repos as of that date. pdf4llm itself stays on disk
as a standalone tool; **these lessons must survive its retirement** — several
generalize to any conversion pipeline this project runs.

**The retirement decision in one line:** the agent already converts every
paper PDF internally (docling → `.extraction_cache/`, content-hash keyed,
pre-spend), pdf4llm's markdown output is forensically *worse* than that cache
(its normalizer rewrites `±`→`+-`, `≤`→`<=`, Greek→ASCII; pipe tables cannot
express column spans), and pdf4llm is AGPL against this repo's MIT. Workflow:
DOI list → fetchpdf → `metascience batch`; `body.md` is legacy.

## Generalizable design rules (restated as normative for this repo)

1. **Never let a fallback clobber a document that has tables.** pdf4llm's OCR
   fallback had no table support; every swap site needed a
   `_has_table_structure()` guard, plus a minimum-gain threshold
   (`ocr_score > quality_score + 0.1`) because a bare-improvement test
   swapped good docling documents for text dumps. (pipeline.py:116-137,
   1400-1417; CLAUDE.md:185-187)
2. **Quality gates must be mode-aware.** Docling emits no structured refs and
   one body section, so a naive rubric scored a *perfect* docling doc 0.56 —
   below the 0.6 OCR threshold — and **every docling document was silently
   replaced and its tables dropped**. Renormalize criteria per extraction
   mode. (validation.py:107-126)
3. **Provenance must be updated at every document swap** or provenance.json
   describes an extractor that produced none of the output.
   (pipeline.py:1431-1442; CLAUDE.md:188-191)
4. **Prefer writing nothing over writing something false** (abstract
   detection: reject candidates with publisher boilerplate, `@`, <2
   sentences). (pipeline.py:140-184)
5. **Provenance lives in the filename** for converted artifacts
   (`_from_xml.md` / `_from_html.md` / `_from_pdf_…`): a consumer that globs
   a directory reads nothing else, and publisher JATS and a reconstructed
   PDF do not deserve equal trust. PDF is the lowest-fidelity tier — numeric
   corruption is possible and undetectable. (pdf4llm/naming.py:17-36)
6. **Tables in markdown conversions are inline HTML, never pipes** —
   markdown has no span mechanism; a `colspan=2` header collapses and every
   value to its right shifts a column. Uniformly HTML, even span-free ones.
   Captions and `<table-wrap-foot>` stay ATTACHED to their table.
   (fetchpdf/retrieval/to_markdown.py:3-23, 176-182)
7. **Figures are recorded, never inlined** — a record whose key outcome
   lives in a forest plot should *look* incomplete. (to_markdown.py:25-28)
8. **Integrity metadata must be read back, not only written.** A corpus held
   30 git-lfs pointer stubs where supplements should have been; every oid
   matched the manifest, and nothing noticed. `fetchpdf-verify` exists for
   this and (until Part D wires it) is called by nothing.
   (fetchpdf/retrieval/verify.py)
9. **A cold cache is not a scan; a missing package is not an unreadable
   paper.** Every extraction refusal carries a named reason
   (`pdf_not_extracted` ≠ `no_text_layer` ≠ `unreadable_format`); collapsing
   them writes a claim about the authors out of a fact about us.
   (supplements.py:676-686; LESSONS.md #1)

## pdf4llm inventory — docling operation

- Converter cached per (device, do_ocr, want_images, thread); converters are
  not thread-safe to share; `want_images`/`images_scale` must be in the cache
  key or an images-off converter silently yields zero figures.
  (pipeline.py:244-251, 524-538)
- OCR OFF on the primary docling pass (per-page Tesseract was the dominant
  cost); sparse output (< ~200 chars/page) triggers a transparent OCR retry,
  kept only if it recovers more text. (pipeline.py:253-256, 473-479, 605-621)
- Use `TesseractCliOcrOptions`, never default rapidocr (rapidocr assigns a
  PosixPath to an OmegaConf primitive → `UnsupportedValueType`).
  (pipeline.py:481-483)
- Force `AcceleratorDevice` explicitly — docling's probing crashes on
  incomplete-CUDA boxes (`libnvrtc-builtins.so not found`); and never set
  `CUDA_VISIBLE_DEVICES=""` to hide CUDA — once set, CUDA is permanently
  invisible to torch in-process. (pipeline.py:416-442, 483-485)
- GPU slot semaphore: 1 CUDA docling conversion at a time; explicit
  `--docling-gpu` blocks for the slot rather than silently downgrading.
  (pipeline.py:235-238, 407-436)
- Monkey-patch `PdfHyperlink.uri` → `Any`: malformed link URIs in academic
  PDFs kill docling's strict `AnyUrl` validation. (pipeline.py:214-228)
- `generate_page_images` must be on whenever `generate_picture_images` is —
  `get_image()` crops from the page raster and returns None without it;
  `.copy()` the crop so the raster can be GC'd. (pipeline.py:489-491, 575-576)
- Cache a hard docling import failure once per process (NumPy-2/TF ABI clash
  makes it unimportable forever); never cache a per-document error.
  (pipeline.py:769-790)
- ~8-9 GB/worker for parallel merge; `del` converter results promptly, keep
  only small crops. Silence docling/tesseract loggers above CRITICAL — their
  filters are unreliable. (pipeline.py:347-380, 594-595)

## pdf4llm inventory — tables, abstract, references

- Table-cell unicode normalization (`±`→`+-`, `–`→`-`, `α`→`alpha`, smart
  quotes→ASCII) — **recorded as what NOT to do here**: it is destructive for
  forensic use; this repo keeps cells byte-faithful. (extractors/tables.py:147-178)
- Table quality weights: header .3, cell population .3, column consistency
  .2, header/row alignment .2; merge dedupes by lowercased caption keeping
  the higher score; pdfplumber path rejects <2 rows and cannot extract
  captions. (tables.py:15-89, 255-277; fast.py:592-636)
- Abstract/body separation: keep `abstract_lines` separate from `body_lines`
  (the old accumulation dumped journal banner + affiliations into a 30 KB
  abstract.md AND duplicated it in body.md); scan 15 leading paragraphs
  (publisher banners occupy a dozen); explicit boilerplate marker list
  ("downloaded by", "registered office", "to cite this article", …).
  (pipeline.py:142-155, 160-163, 630-672)
- Title detection: font-size tiers over pages 1-2 with spatial clustering
  (spans within ~3× font size) so running headers don't join; line-break
  hyphens collapsed; DOI→Crossref confirmation. (fast.py:116-340)
- References: an over-long "reference" is un-split text — truncating it to
  200 chars produced run-on titles worse than no entry (`_MAX_REFERENCE_CHARS`);
  page footers repeat the paper's own DOI, never attribute it to a
  reference; pre-1995 papers scored by reference count, not DOI ratio.
  (ocr_fallback.py:27-33, 118-120, 292-307; validation.py:60-70)

## pdf4llm inventory — batch & environment

- Throttled sliding window of `workers*4` futures; `BatchResult.results`
  holds only failures in large batches; a GROBID JVM crash (OOM) aborts the
  whole batch — `_is_grobid_crash()` distinguishes it from ordinary 500s.
  (pipeline.py:110, 187-199, 2318; CLAUDE.md:93-95, 182-183)
- Create output folders lazily (render → mkdir → write) so crashes leave no
  phantom folders; checkpoint entries self-validate on load (all three
  outputs must exist). (pipeline.py:1362-1365, 1924-1926)
- GROBID environment traps (kept for the day structured references are
  wanted again): venv must have Pillow or JEP falls back to a system PIL →
  every processFulltextDocument 500s while /api/isalive returns 200; pin
  jep==4.2.2 (4.3.1 SIGSEGVs on Java 21), delft==0.3.4, Python 3.10;
  compose uses ports mapping, not network_mode:host; silent freeze =
  zombie JVM (`isalive` 200, fulltext hangs) → pkill -9. (pdf4llm/README.md:
  205-231, 454-491; CLAUDE.md:152-154)
- Reversible DOI↔slug codec (`doi_codec.py`): the old slug collapsed every
  non-word char to `--`, colliding `10.1023/a:123` with `10.1023/a/123`.
  Mapping `/`→`--`, `:`→`~`, punctuation→`~XX~` hex. Relevant to the Neon
  papers table's slug column.

## This repo's extraction stack — measurements that justify it

- Docling vs alternatives on numeric-cell ground truth: docling 92.0%
  precision / 95.9% recall; marker 87.0/90.0; pdfplumber 88.3/60.7. Routing
  (+0.4) and union (+0.6 recall, worse precision) both measured and
  REJECTED — the union inherits every tool's false values, and "a plausible
  wrong number is the worst output this system produces."
  (extraction/docling_tables.py:1-34)
- Body-text gap is larger than the table gap: pdfplumber renders
  `t(28) = -3.33` as `t(28)(cid:1)(cid:5)3.33`; statcheck finds 0 statistics
  in pdfplumber's Ophir 2009 vs 26 (2 inconsistent) in docling's.
  (docling_tables.py:173-186)
- `readable_body_chars` furniture subtraction: lines repeating on ≥60% of
  pages are furniture (digits normalized so page numbers collapse). All 10
  known scans in 291 PDFs score exactly 0.0 body chars/page; the sparsest
  readable document is 163.7 — zero is the threshold because there is no
  cutpoint to tune. (extraction/pdf.py:29-89)
- Cache discipline: `_grid_of` records WHICH docling API route produced a
  grid (the API moved across releases; a silent zero is indistinguishable
  from a paper with no tables); `use_cache=False` must still WRITE;
  tmp+rename atomic writes (two racing processes once produced a corrupt
  read-back); older schemas served as-is; `extractor_version` stamped
  because the cache is portable — and a real corpus held 14 schema-2 /
  1 schema-3 / 4 unstamped / 2 schema-4 entries side by side.
  (docling_tables.py:120-140, 240-286, 293-327, 375-414)
- References split at extraction (boundary recorded, text kept whole as the
  quote-verification haystack): the statistics-register floor was
  enumerating reference lists — 7.5% of floor items corpus-wide, 80% for one
  paper, DOIs read as sample fractions. (docling_tables.py:258-265)
- `_TORCH_ENV = {"TORCHDYNAMO_DISABLE": "1", "TORCH_COMPILE_DISABLE": "1"}`
  — machines without Python dev headers hit `CppCompileError: Python.h`.
  (docling_tables.py:50-55)
- Known open defects at retirement time (Part D items): docling ligature
  splits (`ef fi cacy`; 52 hits in one live cache entry) and raw `&amp;`
  entities — fixed at cache-write time by Part D's normalization pass
  (cache schema 5 at the time; now 6 — the stacked-headers merge found two
  branches had stamped 5 with different fixes, so 5 is refused as stale);
  the fitz-vs-pdfplumber recall gap on supplement
  citations (fitz 5.6× faster and strictly more complete on 12 measured
  PDFs). (extraction/jats.py:1817-1823)

## fetchpdf — the boundary this repo now owns

- `fetchpdf papers.csv -o out -w 4 --get-xml-or-html --to-markdown
  --download-data-artifacts --make-subfolder --provenance` produces the
  per-DOI layout this repo consumes; PDF-only records get NO markdown and
  fetchpdf's own batch summary names the gap ("these still need the PDF
  pipeline") — the gap is closed by this repo's extraction cache, not by a
  conversion step. (fetchpdf/retrieval/to_markdown.py:613-615, 651-654)
- Walk XML in document order (a table out of position loses the sentence
  with the units and the sample); unknown wrappers are descended, never
  dropped; a boilerplate stripper that removes almost nothing is reported
  as a failure; group by record before picking a source or
  `.fulltext.html` beats `.xml` purely by sort order.
  (to_markdown.py:110-115, 165-173, 266-275, 573-577)
