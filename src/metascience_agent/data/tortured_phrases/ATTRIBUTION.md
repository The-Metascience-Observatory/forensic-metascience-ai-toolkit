# Fingerprint data — attribution and licensing

The fingerprint dictionary in this directory is derived from the following
sources. CC BY 4.0 requires attribution and a statement of modifications;
both are given here.

## Sources

1. **Cabanac, G., Labbé, C., & Magazinov, A. (2021).** *Tortured phrases: A
   dubious writing style emerging in science. Evidence of critical issues
   affecting established journals.* Supplementary materials.
   https://zenodo.org/records/5119079 — arXiv:2107.06751.
   License: **Creative Commons Attribution 4.0 International (CC BY 4.0)**.
   Source id in the TSVs: `cabanac2021`.

2. **Clausse, A., Badalova, A., Cabanac, G., & Mayr, P. (2025).** *Tortured
   Phrases from the Humanities and Social Sciences — A fingerprints dataset.*
   https://zenodo.org/records/14753785.
   License: **CC BY 4.0**. Source id: `clausse2025`.

3. **Problematic Paper Screener** fingerprint list (Cabanac, Labbé &
   Magazinov), hand-exported from the PPS interface.
   https://www.irit.fr/~Guillaume.Cabanac/problematic-paper-screener/
   Source id: `pps_live`.
   **License: TO BE VERIFIED AT EXPORT TIME.** The live list's terms are not
   assumed to match the Zenodo releases; until verified, rows carrying ONLY
   the `pps_live` source id must not be redistributed outside this repository.

4. Rows with source id `curated` (the LLM-boilerplate list and pre-ingestion
   seed rows) were written in this repository and carry its license.

## Modifications

Entries from all sources were normalized (whitespace, apostrophes, Unicode
NFKC), merged, deduplicated on (token sequence, family), and annotated with
this repository's metadata columns (`subclass`, `flags`, `ambiguity`, …) by
`examples/ingest_tortured_fingerprints.py` (deleted 2026-10-16 with examples/; recover it from git history). Ingestion statistics per source
are recorded in `manifest.json`. Entries retired by calibration are listed in
`blocklist.tsv` with reasons, not deleted.
