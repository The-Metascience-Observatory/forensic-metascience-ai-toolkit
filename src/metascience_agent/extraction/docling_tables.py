"""Tables out of a PDF, using a layout model rather than ruling lines.

WHY THIS EXISTS, MEASURED 2026-08-13 against XML ground truth on the seven
papers in this repository that ship BOTH the publisher's JATS XML and its PDF.
The XML marks up `<table>/<row>/<cell>` explicitly, so it is not an estimate of
what the tables contain -- it IS what they contain:

    tool                  precision  recall
    pdfplumber (previous)   88.3%     60.7%
    marker                  87.0%     90.0%
    docling                 92.0%     95.9%

Docling wins on BOTH axes, so there was no trade to make. Its table model is
TableFormer, a transformer trained on table images; pdfplumber looks for ruled
lines and, on a paper that prints its tables without them, finds nothing at all
-- 0.0% recall on two of the seven, and no error, because a table it cannot rule
is simply not a table to it.

A neutral academic benchmark (arXiv 2511.16134, 15 methods over four
scientific-PDF datasets) reaches the same ranking from a different direction:
Docling F1 0.96-0.99, the pdfplumber/Camelot/PyMuPDF family 0.09-0.41.

ROUTING AND ENSEMBLES WERE MEASURED AND REJECTED. Picking the best tool per
paper scores 96.2% against Docling's 95.8% (+0.4). Running all three and keeping
the union scores 96.4% (+0.6) AND COSTS PRECISION, because the union inherits
every tool's false values -- Marker alone contributes 281 numbers absent from
ground truth against Docling's 175. A plausible wrong number is the worst output
this system produces, so that trade runs the wrong way.

SPEED IS NOT A SELECTION CRITERION. Greg, 2026-08-13: "the speed of the
extraction is pretty inconsequential compared to the gains on extraction
quality." Extraction runs once per paper, is cached below by content hash, and
is trivial beside the model spend it feeds.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import os
import re
from pathlib import Path
from typing import Any

#: Extraction is expensive and its result is small, so it is cached beside the
#: paper, keyed by the CONTENT of the file rather than its name -- a supplement
#: that is re-fetched under a different name must not be re-extracted, and a
#: file that is edited in place must not serve a stale cache.
CACHE_DIRNAME = ".extraction_cache"

#: What a FRESHLY WRITTEN entry is stamped with. Bumped to 6 at the
#: stacked-headers merge (2026-08-21): TWO branches had independently stamped
#: "5" with different contents -- one 5 meant ligature/entity normalization at
#: cache-write, the other meant stacked-header cell labels -- so a 5 on disk
#: does not say which fix it carries and BOTH flavors are refused as stale
#: below. Older schemas are still SERVED AS-IS where safe -- see the read
#: path in `extract_pdf_tables` -- so a schema-4 entry keeps its `ef fi cacy`
#: splits until someone re-extracts with `--force`.
CACHE_SCHEMA = 7

#: This environment has no Python development headers, so `torch.compile`'s
#: inductor backend cannot build its C++ extension and Docling dies with
#: `CppCompileError: Python.h: No such file or directory`. Disabling dynamo
#: costs some speed and no accuracy, and speed is not a criterion here.
#: Set in the process rather than documented in a README nobody reads.
_TORCH_ENV = {"TORCHDYNAMO_DISABLE": "1", "TORCH_COMPILE_DISABLE": "1"}


def available() -> tuple[bool, str]:
    """`(installed, why_not)`. The reason travels, so nothing is silent."""
    try:
        import docling  # noqa: F401
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _cache_path(path: Path) -> Path:
    return path.parent / CACHE_DIRNAME / f"{path.stem}.{_digest(path)}.tables.json"


def _execution_identity(execution):
    from .document_compute import model_manifest
    from .document_compute import workload_signature
    return dict(backend_schema=1,execution=execution.identity(),models=model_manifest(),
                implementation=workload_signature('document'))


def _variant_path(cache, path, identity):
    from .document_compute import digest
    return cache.parent/'execution'/digest([_digest(path),identity])/cache.name


#: LIGATURE SPLITS, the shape MEASURED in the live cache entry for
#: 10.1073--pnas.1211286109 (extractor 2.119.0, 75 sites in `text`): docling
#: renders a word containing a ligature glyph (fi fl ff ffi ffl) as three
#: space-separated fragments -- `signi fi cantly`, `de fi cit`, `con fl ict` --
#: and, when the ligature opens the word, as a stray prefix on an intact
#: neighbour: `many fi elds`, `These fi ndings`. The token is ALWAYS lowercase
#: (ligature glyphs have no uppercase form), always single-spaced, and the
#: suffix always continues in lowercase, which is what this pattern requires.
#: `Sci Fi movie` therefore never matches.
_LIG_SPLIT = re.compile(r"(?<=[A-Za-z]) (ffi|ffl|ff|fl|fi) (?=[a-z])")

#: The vocabulary that licenses a rejoin. Two spellings of the same site --
#: `signi fi cant` and `many fi elds` -- need OPPOSITE repairs (join both
#: spaces vs. keep the word break), and nothing in the string itself
#: distinguishes them: only knowing that `significant` is a word and
#: `manyfields` is not. So the repair is lexical and CLOSED: a site whose
#: neither reading is in this set is LEFT ALONE -- corrupt text we keep is the
#: status quo, corrupt text we manufacture is new. Curated 2026-08-21 from
#: every distinct site in the measured entry plus common scientific ff/fi/fl
#: vocabulary; all-lowercase, matched case-insensitively.
_LIG_WORDS = frozenset("""
acidification affect affected affecting affects affiliated affiliation
affiliations affinities affinity affirm affirmed afflicted affliction afford
afforded amplification amplified artificial artificially beneficial
beneficiary benefit benefited benefits buffer buffered buffers caffeine
calcification certificate certificates certification certified clarification
clarified clarify classification classifications classified classifier
classifiers classify classifying coefficient coefficients coffee confidence
confident confidential confidentiality confidently configuration
configurations configure configured configures confine confined confinement
confines confirm confirmation confirmed confirming confirms conflate
conflated conflict conflicted conflicting conflicts confluence confluent
cutoff cutoffs debriefed debriefing deficiencies deficiency deficient deficit
deficits define defined defines defining definite definitely definition
definitions deflate deflated deflect deflected deflection difference
differences different differential differentially differentiate
differentiated differentiation differently difficult difficulties difficulty
diffraction diffuse diffused diffusion effectively effectiveness efficacious
efficacy efficiencies efficiency efficient efficiently effluent efflux effort
efforts fiber fibers fibre fibres fibrosis fidelity field fields fifteen
fifth fifty figure figures filament filaments file files fill filled filling
fills filter filtered filtering filters final finally finance financial
financially finding findings fine finite first firstly fit fitness fits
fitted fitting five fix fixation fixed flanking flask flasks flat flexibility
flexible flight floor flora flow flows fluctuation fluctuations fluid fluids
fluorescence fluorescent fluoride flux fulfil fulfill fulfilled fulfilling
fulfills identifiable identification identified identifier identifiers
identifies identify identifying immunofluorescence immunofluorescent infinite
inflamed inflammation inflammatory inflate inflated inflating inflation
inflexibility inflexible inflict inflicted inflow influence influenced
influences influencing influential influx insignificance insignificant
insufficient insufficiently justification justified leaflet leaflets
magnification magnified microflora misclassification misclassified
modification modifications modified modify modifying nonsignificance
nonsignificant notification notifications offer offered offering offers
office officer officers offices official officials offline offset offsets
offspring ossification outflow overflow paraffin prespecified proficiency
proficient profile profiles profiling purification purified qualification
qualifications qualified qualifies qualify qualifying quantifiable
quantification quantified quantify quantifying ramification ramifications
reclassification reclassified redefine redefined redefining refill refilled
refills refine refined refinement refining reflect reflected reflecting
reflection reflections reflective reflects reflex reflexes reflux scaffold
scaffolds scientific scientifically shuffle shuffled shuffling significance
significant significantly signifies signify simplification simplified
specific specifically specification specifications specificities specificity
specifics specified specifies specify specifying stratification stratified
stratify stratifying suffer suffered suffering sufficiency sufficient
sufficiently suffix superficial superficially tradeoff tradeoffs traffic
trafficking unfiltered unidentified unjustified unmodified unqualified
unspecified unverified verifiable verification verified verify verifying
falsification falsified
benefiting briefly classifies defies dissatisfied fibrillation filler fillers
finalize finalized find finds fish satisfied satisfies selfish staffing
""".split())

#: The tie-break for sites where BOTH readings are words -- `in fi nite` is
#: `infinite` and also, in a statistics paper, honestly `in finite samples`.
#: When the fragment left of the ligature is one of these closed-class words
#: the site is genuinely ambiguous and is left alone; when it is a non-word
#: fragment (`bene`, `ful`, `de`), leaving it dangling is no reading at all,
#: so the full join wins (`benefit`, `fulfilling`, `definite`).
_AMBIGUOUS_LEFT = frozenset("""
a about above after again against all also an and any are as at be been
before being below between both but by can could did do does done down
during each few for from further had has have he her here his how i if in
into is it its many may might more most much must my no nor not of off on
once only or other others our out over own per same she should so some such
than that the their then there these they this those through to too under
until up very via was we were what when where which while who whom why will
with within without would you your
""".split())


def _heal_ligatures(text: str) -> str:
    """Rejoin docling's ligature splits; leave anything unrecognized alone."""
    drop: list[int] = []  # indices of spaces to delete
    for m in _LIG_SPLIT.finditer(text):
        tok = m.group(1)
        i = m.start()   # the space before the ligature token
        j = i
        while j and text[j - 1].isascii() and text[j - 1].isalpha():
            j -= 1
        left = text[j:i]
        k = m.end()     # first letter after the space that follows the token
        e = k
        while e < len(text) and text[e].isascii() and text[e].isalpha():
            e += 1
        right = text[k:e]
        whole_is_word = (left + tok + right).lower() in _LIG_WORDS
        tail_is_word = (tok + right).lower() in _LIG_WORDS
        if whole_is_word and tail_is_word:
            if left.lower() in _AMBIGUOUS_LEFT:
                continue
            tail_is_word = False
        if whole_is_word:
            drop.extend((i, k - 1))
        elif tail_is_word:
            drop.append(k - 1)
    if not drop:
        return text
    chars = list(text)
    for idx in sorted(drop, reverse=True):
        del chars[idx]
    return "".join(chars)


def _normalize_extracted(s: str) -> str:
    """The cache-write fold: entity unescape + ligature rejoin, NOTHING else.

    Applied to `text`, to each `pages[].text`, and to table cells (which get
    exactly this fold and stay byte-faithful otherwise). Docling's markdown
    export emits raw entities -- `P &lt; 0.01`, `Smith &amp; Jones` -- which
    would hide a comparison from statcheck exactly the way pdfplumber's
    `(cid:1)` glyphs did. Deliberately NOT the pdf4llm normalizer this repo
    recorded as what-not-to-do: no `±`→`+-`, no Greek→ASCII -- those rewrite
    what the authors printed; this only undoes docling's own encoding of it.
    """
    if not s:
        return s
    if "&" in s:
        s = _html.unescape(s)
    if " f" in s:
        s = _heal_ligatures(s)
    return s


_CONVERTER: Any = None
_CONVERTER_EXECUTION = None


def _converter(execution=None):
    global _CONVERTER, _CONVERTER_EXECUTION
    from .document_compute import resolve
    execution = execution or resolve('document')
    session_key = (_execution_identity(execution), os.environ.get('METASCIENCE_INFERENCE_THREADS','4'))
    if _CONVERTER is None or _CONVERTER_EXECUTION != session_key:
        for k, v in _TORCH_ENV.items():
            os.environ.setdefault(k, v)
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions
        options = PdfPipelineOptions()
        options.accelerator_options = AcceleratorOptions(device=execution.device,
            num_threads=int(os.environ.get('METASCIENCE_INFERENCE_THREADS', '4')))
        from .document_compute import ocr_options
        options.ocr_options = ocr_options(execution.device)
        if execution.device.startswith('cuda'):
            import onnxruntime as ort
            if hasattr(ort, 'preload_dlls'):
                ort.preload_dlls()
        _CONVERTER = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        _CONVERTER_EXECUTION = session_key
    return _CONVERTER


def extract_pdf_tables(path: str | Path, use_cache: bool = True,
                       allow_extract: bool = True) -> dict:
    """`{"tables": [...], "error": str|None, "cached": bool, "notes": [...]}`.

    Tables come back in the SAME SHAPE `jats.py` and `supplements_read.py`
    produce, by routing through the same `_finish` builder. Two cell shapes for
    one concept is how a downstream consumer handles one and silently drops the
    other.

    `allow_extract=False` READS THE CACHE AND NEVER RUNS THE MODEL, and that is
    the setting every cheap enumeration should use. Wiring extraction directly
    into `prepass.paper_tables` -- an ordinary "list this paper's tables" call --
    made a routine function block for minutes: the suite went from 260 s to
    596 s, and a completeness test that passes alone failed in the parallel run,
    because xdist workers were racing to extract the same PDF into the same
    cache file. Extraction is a heavyweight, explicit STEP; enumeration is not
    the place for it.

    An error is REPORTED, never swallowed into an empty list: "we could not read
    this PDF" and "this PDF has no tables" are opposite facts, and the extractor
    this replaces returned the same value for both.
    """
    p = Path(path)
    notes: list[str] = []
    if not p.is_file():
        return {"tables": [], "error": f"no such file: {p}", "cached": False,
                "notes": notes}

    # `use_cache=False` MUST STILL WRITE. It did not, and the consequence was
    # silent: `--force` re-extracted, printed a healthy result, and persisted
    # nothing, so the next reader got the stale cache or none at all. Found
    # 2026-08-13 when `--force` re-extraction repeatedly failed to add the new
    # `text` field. Reading and writing are separate decisions and are now
    # separate variables.
    cache = _cache_path(p)
    if use_cache and cache.is_file():
        try:
            # SERVED AS-IS, INCLUDING OLDER SCHEMAS. A schema-3 entry still
            # carries the text and the tables, which is what nearly every
            # caller wants, so invalidating it wholesale to obtain the per-page
            # split added in schema 4 makes every cheap read pay for a field it
            # does not use. The first cut did exactly that and pushed the test
            # suite past ten minutes -- the same regression recorded in this
            # function's own docstring, where wiring extraction into an
            # ordinary enumeration took it from 260 s to 596 s.
            #
            # The caller that DOES need `pages` -- `extract_text_with_tables`
            # -- checks for it and re-extracts on its own account. Paying that
            # cost belongs with the caller that asked for the field.
            saved=json.loads(cache.read_text(encoding="utf-8"))
            if not allow_extract or not saved.get('execution_identity'):
                return {**saved,"cached":True,"notes":notes}
            from .document_compute import resolve
            selected = resolve('document')
            identities = [_execution_identity(selected)]
            if selected.device != 'cpu':
                # A paper converted on the CPU while another held the GPU
                # slot (`compute.document.gpu_slot`) is not converted again:
                # the CPU extraction is the reference, and its record names
                # the backend that produced it.
                from .document_compute import cpu_overflow
                identities.append(_execution_identity(cpu_overflow(selected)))
            for identity in identities:
                if saved['execution_identity']==identity:
                    return {**saved,"cached":True,"notes":notes}
                variant=_variant_path(cache,p,identity)
                if variant.is_file():
                    found=json.loads(variant.read_text())
                    if found.get('execution_identity')==identity:
                        return {**found,"cached":True,"notes":notes}
            notes.append('Selected extraction backend changed; creating its separate cache variant')
        except Exception as exc:  # noqa: BLE001
            # A corrupt cache is RE-EXTRACTED, never served -- but the fact is
            # recorded, because a cache that silently fails to load turns a
            # 40 s step into a 40 s step forever and nobody learns why.
            notes.append(f"cache at {cache.name} unreadable "
                         f"({type(exc).__name__}), re-extracting")

    if not allow_extract:
        return {"tables": [], "cached": False, "notes": notes,
                "error": f"{p.name} has not been table-extracted yet, and this "
                         "caller does not run the extractor. Run "
                         "`metascience extract-tables` on the paper directory. "
                         "THIS IS NOT A PAPER WITHOUT TABLES."}

    ok, why = available()
    if not ok:
        return {"tables": [], "cached": False, "notes": notes,
                "error": f"docling is not installed ({why}), so this PDF's "
                         "tables were not read. OUR gap: the paper may well "
                         "have tables."}

    from .document_compute import resolve
    from .document_compute import in_worker, run
    try:
        execution = resolve('document')
        if execution.device != 'cpu' and not in_worker():
            # One conversion holds the GPU; any other running at the same
            # moment takes the CPU now instead of queueing (Dan, 2026-10-01).
            from .document_compute import cpu_overflow, gpu_slot
            with gpu_slot() as held:
                if held:
                    payload = run('document', {'path': str(p)}, execution=execution, timeout=600)
                    return {**payload['result'], 'compute': payload['compute']}
            execution = cpu_overflow(execution)
        from .document_compute import verify_converter, admission
        with admission():
            # The overflow converter is built for the CPU explicitly; the
            # ordinary path keeps `_converter()`'s own resolution.
            converter = (_converter(execution) if execution.reason == 'gpu_busy_cpu_overflow'
                         else _converter())
            doc = converter.convert(str(p)).document
            # Production DocumentConverter owns initialized_pipelines; pure
            # normalization tests use small duck-typed converters.
            provider_record = verify_converter(converter, execution.device) if hasattr(converter, 'initialized_pipelines') else None
    except Exception as exc:  # noqa: BLE001
        return {"tables": [], "cached": False, "notes": notes,
                "error": f"docling could not read {p.name}: "
                         f"{type(exc).__name__}: {exc}"}

    from .supplements_read import _finish

    # THE BODY TEXT TOO, not only the tables. Greg, 2026-08-13: "I would expect
    # that docling would be better at PDF-to-markdown extraction across the
    # board, not just with tables." He was right and the gap is enormous.
    #
    # MEASURED on Ophir 2009 (PNAS), a paper whose statistics are reported
    # inline rather than in tables: pdfplumber renders the operators as glyph
    # references -- `t(28)(cid:1)(cid:5)3.33` -- and our own debris filter then
    # strips them, so the model receives `t(28)3.33` with the comparator and
    # THE MINUS SIGN gone. Docling returns `t (28) = -3.33`. statcheck finds 0
    # statistics in the first and 26 (with 2 inconsistencies) in the second.
    #
    # A dropped negative is the worst extraction failure this project has --
    # a reported -5.50 reaching a checker as +5.50 -- so this is not a
    # refinement, it is the difference between a check and a fabrication.
    try:
        text = doc.export_to_markdown()
    except Exception as exc:  # noqa: BLE001
        text = ""
        notes.append(f"markdown export failed ({type(exc).__name__}), tables only")
    # The fold runs at CACHE-WRITE time, so every later read -- statcheck, quote
    # verification, the sweep -- sees `efficacy` and `P < 0.01`, not
    # `ef fi cacy` and `P &lt; 0.01`. Cache schema 5.
    text = _normalize_extracted(text)

    # PER-PAGE TEXT, so nothing needs pdfplumber to answer "what is on page 4?".
    #
    # GREG, 2026-08-16: pdfplumber "should never run *anywhere*". The one thing
    # `extract_text_with_tables` offered that the docling cache did not was a
    # `pages[]` breakdown with page-range slicing, and that was the whole reason
    # the pdfplumber path survived there. Docling carries the same information:
    # every text item's `prov[0].page_no` names its page.
    #
    # Built here rather than derived later because the provenance lives on the
    # in-memory document and is gone once the cache is written.
    pages: list[dict] = []
    try:
        by_page: dict[int, list[str]] = {}
        for item, _lvl in doc.iterate_items():
            prov = getattr(item, "prov", None) or []
            body = getattr(item, "text", None)
            if not prov or not body:
                continue
            page_no = getattr(prov[0], "page_no", None)
            if page_no is None:
                continue
            by_page.setdefault(int(page_no), []).append(str(body))
        n_pages = len(getattr(doc, "pages", {}) or {}) or (max(by_page) if by_page else 0)
        pages = [
            {"page_num": n,
             "text": _normalize_extracted("\n".join(by_page.get(n, [])))}
            for n in range(1, int(n_pages) + 1)
        ]
    except Exception as exc:  # noqa: BLE001
        # Recorded, not swallowed: a caller that asked for a page range and got
        # nothing must be able to tell "the page is blank" from "we could not
        # work out which page anything was on".
        notes.append(f"per-page split failed ({type(exc).__name__}: {exc})")

    tables: list[dict] = []
    routes: dict[str, int] = {}
    stacked = 0
    for i, t in enumerate(doc.tables, start=1):
        grid, route, header_rows = _grid_of(t, doc)
        routes[route] = routes.get(route, 0) + 1
        if not grid:
            continue
        # Cells get the SAME fold as the text and nothing more: byte-faithful
        # otherwise (no unit stripping, no unicode folding -- see the pdf4llm
        # lesson recorded in docs/archive/ingestion_learnings.md).
        grid = [[_normalize_extracted(c) for c in row] for row in grid]
        if header_rows > 1:
            stacked += 1
        label, caption = _label_and_caption(t, i, doc)
        tables.append(_finish(grid, i, label, caption, "", p.name,
                              provenance=None, page=_page_of(t),
                              header_rows=header_rows))
    if stacked:
        # SAID OUT LOUD, because a stacked header is where this reader used to
        # be silently wrong and a reader comparing two runs needs to see which
        # tables changed shape.
        notes.append(f"{stacked} of {len(doc.tables)} tables have a header more "
                     "than one row deep, read from docling's column_header flags")
    # WHICH API ROUTE WORKED, recorded because Docling's table API has moved
    # across releases. A silent switch to the markdown fallback is a quality
    # regression that would otherwise show up only as a worse score months later.
    notes.append("grid routes: " + ", ".join(f"{k}={v}" for k, v in routes.items()))

    # WHO PRODUCED THIS, stamped because the cache is PORTABLE. Greg,
    # 2026-08-13: "suppose I have a better computer... Could I do the docling
    # work there and give you the results?" Yes -- the cache is keyed on the
    # file's CONTENT hash and holds no absolute paths, so it transfers between
    # machines and is readable with docling not installed at all (verified by
    # blocking the import).
    #
    # But a result produced elsewhere is only trustworthy if it says what
    # produced it. A different docling version can extract differently, and an
    # unversioned cache would let that difference arrive silently -- indistin-
    # guishable from the paper having changed. So the version travels with the
    # payload, exactly as `run_meta.git_sha` travels with a review.
    try:
        from importlib.metadata import version as _v
        _dl_version = _v("docling")
    except Exception:  # noqa: BLE001
        _dl_version = "unknown"

    # THE BIBLIOGRAPHY, SEPARATED AT EXTRACTION. Greg, 2026-08-16: "extract the
    # references separately. That way this kind of mistake won't happen." The
    # mistake was the statistics-register floor enumerating reference lists --
    # 7.5% of floor items corpus-wide, 80% for one paper, including DOIs read as
    # sample fractions. `text` stays WHOLE, because it is the haystack every
    # quote is verified against and a quote citing a reference must still be
    # locatable; what changes is that the boundary is now recorded rather than
    # re-derived by each consumer that happens to remember to.
    from .. import references as _refs
    _split = _refs.split(text)
    out = {"tables": tables, "text": text, "error": None,
           "n_tables": len(tables), "n_text_chars": len(text),
           "pages": pages, "num_pages": len(pages),
           "references": _split["references"],
           "n_reference_chars": len(_split["references"]),
           "references_boundary": _split["boundary"],
           "references_found_by": _split["how"],
           "source_format": "pdf", "extractor": "docling",
           "extractor_version": _dl_version,
           "execution": execution.record(),
           "execution_identity": _execution_identity(execution),
           "execution_providers": provider_record,
           "cache_schema": CACHE_SCHEMA, "notes": notes}
    if True:  # always persist; see the note on read/write separation above
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            # Written via a temp file and renamed, because two processes
            # extracting the same paper at once left a half-written cache that
            # the other one read back as corrupt. Rename is atomic on POSIX.
            # The discriminator moved from `os.getpid()` into `atomicio`, which
            # adds a uuid: `batch --workers N` runs papers concurrently inside
            # ONE process, and there a PID distinguishes nothing.
            from ..atomicio import atomic_write_text
            # Preserve the exact numerical variant separately; the compatibility
            # path remains the selected extraction for historical read-only use.
            variant = _variant_path(cache,p,out['execution_identity'])
            variant.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(variant, json.dumps(out))
            atomic_write_text(cache, json.dumps(out))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"cache not written ({type(exc).__name__}: {exc}); "
                         "extraction will repeat next run")
    return {**out, "cached": False}


def _grid_of(table: Any, doc: Any) -> tuple[list[list[str]], str, int]:
    """`(grid, which_route_worked, header_rows)` from a Docling table.

    Docling's table API has moved across releases -- `export_to_dataframe` took
    a doc argument, then did not; `data.grid` exists on some versions and not
    others. Each route is tried and the first that yields a grid wins, and WHICH
    ONE WON IS RETURNED, because a hard-coded call that works today becomes a
    silent zero on the next upgrade, and a silent zero here is indistinguishable
    from a paper with no tables.

    `header_rows` IS READ FROM DOCLING, NOT GUESSED. Every `TableCell` carries a
    `column_header` flag and this function used to discard it, keeping only
    `.text` -- so `_finish` fell back to its one-row default on every PDF table
    in the corpus. On a stacked header that is not a cosmetic loss: the row
    below the spanning row holds the only labels the columns have. Docling's own
    markdown for `10.1166--jnn.2011.5114` renders
    `Control | Control | Control | Heat stress | ...` above
    `Saline n | Cu n | Ag n | ...`, so the one-row reading gives the saline,
    copper and silver columns the SAME label, and a mean taken from one with an
    `n` taken from another is a pair the paper never printed. See
    `jats._header_depth` for the measured cost.

    Only the `data.grid` route can answer -- the dataframe and markdown
    fallbacks have already flattened the header away -- so those return 1, which
    is what they meant before and is now said rather than assumed.
    """
    failures: list[str] = []

    rows = getattr(getattr(table, "data", None), "grid", None)
    if rows:
        # LEADING ROWS WHOSE EVERY NON-EMPTY CELL IS FLAGGED A COLUMN HEADER.
        # `all(...)` over every cell was tried first and returned 1 on a table
        # docling had plainly marked two rows deep: a stacked header's top-left
        # corner is an EMPTY stub, and docling does not flag an empty cell. One
        # unflagged blank was enough to discard the whole answer. Requiring at
        # least one flagged cell keeps the rule from promoting a row of blanks.
        #
        # Floored at 1 below: docling flags nothing on some tables, and treating
        # the first row as the header is the PDF path's long-standing
        # convention, not something to drop silently here.
        from .jats import _reads_as_measurements

        header_rows = 0
        for row in rows:
            texts = [(getattr(c, "text", "") or "").strip() for c in row]
            flags = [bool(getattr(c, "column_header", False)) for c in row]
            filled = [f for t, f in zip(texts, flags) if t]
            if not (filled and all(filled)):
                break
            # THE SAME BRAKE THE HTML READER USES, applied to docling's answer
            # rather than instead of it. A flag is a claim about layout and this
            # is a claim about content; where they disagree the content wins,
            # because a header row leaves the body and a measurement that leaves
            # the body stops existing for every check. The extractor must not be
            # able to delete a value by mislabelling its row.
            if header_rows and _reads_as_measurements(texts):
                break
            header_rows += 1
        return ([[getattr(c, "text", "") or "" for c in row] for row in rows],
                "data.grid", max(1, header_rows))

    for name, call in (("dataframe(doc)", lambda: table.export_to_dataframe(doc)),
                       ("dataframe()", lambda: table.export_to_dataframe()),
                       ("markdown(doc)", lambda: table.export_to_markdown(doc)),
                       ("markdown()", lambda: table.export_to_markdown())):
        try:
            got = call()
        except Exception as exc:  # noqa: BLE001
            # RECORDED, not discarded. Every route failing is how this function
            # returns an empty grid, and an empty grid is indistinguishable from
            # a table with no content unless the reasons travel.
            failures.append(f"{name}: {type(exc).__name__}")
            continue
        if name.startswith("markdown"):
            return _grid_from_markdown(got), name, 1
        return ([[("" if v is None else str(v)) for v in row]
                 for row in [list(got.columns)] + got.values.tolist()], name, 1)

    return [], "none (" + "; ".join(failures) + ")", 1


def _grid_from_markdown(md: str) -> list[list[str]]:
    """Last resort. A markdown pipe table back into a grid."""
    grid = []
    for line in (md or "").splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # the |---|---| separator row carries no data
        if all(set(c) <= set("-: ") and c for c in cells):
            continue
        grid.append(cells)
    return grid


#: The printed label at the head of a caption: "Table 2", "TABLE 3.",
#: "Supplementary Table S1", "eTable 4".
_CAPTION_LABEL = re.compile(
    r"^\s*((?:supplementary\s+|suppl\.?\s+|e)?(?:table|tab\.)\s*[a-z]?\d+[a-z]?)\b[.:]?",
    re.I)


def _label_and_caption(table: Any, i: int, doc: Any) -> tuple[str, str]:
    """`(label, caption)` from the table's RESOLVED caption.

    A docling caption is a reference into `doc.texts`, not text: `_label_of`
    stringified it, so every captioned table was labelled `cref='#/texts/49'`
    and carried no caption at all (found 2026-10-18 on the GRIM ground truth,
    where no table of Shaaban 2012 could be named "Table 2"). Older caches keep
    the old labels until re-extracted; nothing reads the page text to guess,
    because page order and prose mentions ("Table 2 explores ...") make that
    guess wrong on real papers."""
    text = ""
    try:
        text = str(table.caption_text(doc) or "").strip()
    except Exception:  # noqa: BLE001 -- an older docling without caption_text
        text = ""
    if text:
        m = _CAPTION_LABEL.match(text)
        label = " ".join(m.group(1).split()) if m else text[:120]
        return label, text
    return _label_of(table, i), ""


def _label_of(table: Any, i: int) -> str:
    for attr in ("captions", "caption"):
        try:
            cap = getattr(table, attr, None)
            if isinstance(cap, (list, tuple)) and cap:
                text = getattr(cap[0], "text", None) or str(cap[0])
            else:
                text = getattr(cap, "text", None) or (cap and str(cap))
            if text and str(text).strip():
                return str(text).strip()[:120]
        except Exception:  # noqa: BLE001
            continue
    return f"Table {i}"


def _page_of(table: Any) -> int | None:
    """The page a table sits on, or None. ABSENCE IS NOT PAGE 0.

    Written with checks rather than a swallowed exception: `except: return None`
    reports "no page" identically for a table that has none and for a Docling
    release that renamed the field, and the second is a defect we would want to
    hear about.
    """
    prov = getattr(table, "prov", None) or []
    if not prov:
        return None
    page = getattr(prov[0], "page_no", None)
    return int(page) if isinstance(page, (int, float)) else None


def cache_status(path: str | Path) -> tuple[bool, str]:
    """`(usable, why_not)` -- is this file's cache good enough for EVERY reader?

    PRESENCE IS NOT USABILITY, and the gap is not hypothetical. MEASURED
    2026-08-17 over the 21 cache entries in this repository: 14 are schema 2,
    one is schema 3, four predate the schema field entirely, and only two are
    schema 4. `extract_text` is satisfied by all but the four (it needs `text`
    alone), but `extract_text_with_tables` -- which is the MCP tool `extract_pdf`,
    the sweep's primary way into a PDF -- requires the per-page split added in
    schema 4 and refuses without it. On `10.3349--ymj.2009.50.1.55`, a paper
    whose cache is present and whose PDF is perfectly readable, it returns
    `unreadable: True`, `num_pages: 0`, zero tables.

    So a pre-flight that asks only "is there a cache file" hands a paid run a
    document its main tool cannot open. This asks the question the readers
    actually ask, and NAMES what is missing, because "not extracted" and
    "extracted by a version that stored less" send an operator to different
    places -- the second needs `--force`.

    Reads the JSON rather than stat-ing it. That is a millisecond beside the
    content hash `_cache_path` already computed to get here, and it is the only
    way to tell a complete entry from a truncated one.
    """
    p = Path(path)
    if not p.is_file():
        return False, f"no such file: {p}"
    c = _cache_path(p)
    if not c.is_file():
        return False, "not extracted yet"
    try:
        data = json.loads(c.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return False, f"cache unreadable ({type(exc).__name__})"
    if not (data.get("text") or "").strip():
        return False, ("cached by a version that stored tables only, with no "
                       "body text")
    if not data.get("pages"):
        return False, (f"cached at schema {data.get('cache_schema', 'unstamped')}, "
                       "before per-page text existed, which `extract_pdf` needs")
    if int(data.get("cache_schema") or 0) < CACHE_SCHEMA:
        # REFUSED, not warned about, and the threshold is the CONSTANT: two
        # branches independently stamped "5" with different fixes (ligature
        # fold vs stacked headers), so an on-disk 5 cannot prove it carries
        # either -- both flavors re-extract. A schema-4 entry was built when every table
        # got a one-row header, so on a stacked header its cells carry the
        # SPANNING label instead of the column's own -- `Control` where the paper
        # printed `Control / Saline`, `Control / Cu`, `Control / Ag`. Nothing in
        # the payload marks which tables that hit, so it cannot be repaired on
        # read, and a wrong column label is how a mean gets paired with another
        # group's `n`. Re-extraction is minutes; that pairing is an accusation.
        return False, (f"cached at schema {data.get('cache_schema', 'unstamped')}, "
                       "before header depth was read from docling, so any table "
                       "with a stacked header carries the wrong column labels; "
                       "and, at schema < 7, before cells carried their physical "
                       "`col`, so no cell from this cache can be addressed by "
                       "position -- `col_label` is not an address when a header "
                       "repeats a span. Re-extract with --force")
    return True, ""


def cached_text(path: str | Path) -> tuple[str, str]:
    """`(text, why_not)` -- Docling's body text for this PDF, from cache ONLY.

    Returns `("", reason)` when the paper has not been extracted yet, so a
    caller can fall back and SAY that it did. Never runs the model: a cheap
    text read must not block for minutes, which is the same rule
    `prepass.paper_tables` follows for tables.
    """
    p = Path(path)
    if not p.is_file():
        return "", f"no such file: {p}"
    c = _cache_path(p)
    if not c.is_file():
        return "", (f"{p.name} has not been extracted; run `metascience "
                    "extract-tables` for the higher-fidelity text")
    try:
        data = json.loads(c.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return "", f"cache unreadable ({type(exc).__name__})"
    text = data.get("text") or ""
    if not text:
        return "", ("cached by an earlier version that stored tables only; "
                    "re-run `metascience extract-tables --force`")
    return text, ""


def _current_version() -> str:
    """The installed docling version, or a string SAYING why it is unknown.

    Not `"unknown"` on its own: a cache stamped by one machine and read on
    another differs for two very different reasons -- a genuine version skew,
    or docling simply not being installed on the reader -- and a bare
    "unknown" cannot tell a puzzled operator which.
    """
    try:
        from importlib.metadata import version as _v
        return _v("docling")
    except Exception as exc:  # noqa: BLE001
        return f"not-installed-here ({type(exc).__name__})"


def cache_report(paper_dir: str | Path) -> dict:
    """What extraction results this directory holds, and where they came from.

    For the transfer workflow: run `metascience extract-tables` on a fast
    machine, copy the `.extraction_cache` directories across, and this says
    what arrived. The content hash in each filename is the check -- a cache
    that does not match its PDF simply is not found, so a stale or mismatched
    transfer degrades to pdfplumber rather than serving the wrong paper's text.
    """
    base = Path(paper_dir)
    out = {"paper": base.name, "entries": [], "this_machine": _current_version()}
    d = base / CACHE_DIRNAME
    if not d.is_dir():
        out["note"] = "no extraction cache; run `metascience extract-tables`"
        return out
    for f in sorted(d.glob("*.tables.json")):
        try:
            x = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            out["entries"].append({"file": f.name, "error": str(exc)[:80]})
            continue
        out["entries"].append({
            "file": f.name,
            "n_tables": x.get("n_tables"),
            "n_text_chars": x.get("n_text_chars"),
            "extractor_version": x.get("extractor_version", "unstamped"),
            "matches_this_machine":
                x.get("extractor_version") == out["this_machine"],
        })
    return out
