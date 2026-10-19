---
family: tracks
implementation:
- forensic_metascience_ai_toolkit.tools.tortured_phrases
- metascience_observatory_image_analysis.image_forensics.image_analysis
tools:
  analyze_paper_images:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Detects the same image panel presented more than once within a paper's embedded figures and supplements.
    assumptions:
    - 'Within-paper only: nothing is compared against other papers or any external index.'
    - Coverage is EMBEDDED RASTERS only. Vector-drawn charts, flattened page scans and anything the PDF does not carry as an image stream are invisible, so zero groups on a vector-figure paper is coverage absence, not cleanliness.
    - Byte-identity tiers (same xref, identical stream sha256) are the PDF's own assertion of sameness; perceptual tiers assume photographic texture and refuse low-texture panels (western blots wait on a separately calibrated channel).
    - Legitimate stated re-use exists — a representative micrograph re-shown and SAID to be re-shown is not duplication evidence; the stated_reuse guard and the caption scan cap or discount those cases.
    - 'QUARANTINED: delivered severity is indeterminate until the calibration sweep''s release criteria pass; the uncalibrated signal rides in severity_before_quarantine.'
    - 'Capped at `highly_suspicious`: duplication is improbable, never mathematically impossible.'
  detect_tortured_phrases:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Screens the paper's prose for paraphrase-tool and undisclosed-LLM fingerprints from a versioned dictionary.
    assumptions:
    - 'Coverage is the DICTIONARY''s: only listed fingerprints can fire, and the list skews CS/engineering/biomedical -- a null on an out-of-field or non-English paper is weak clearance.'
    - The extracted text is faithful to the paper. Matches that exist only across a line-break hyphenation are marked extraction_risk and cannot alone cross a severity threshold.
    - A fingerprint in the references section indicts the CITED paper, not this one; such matches are recorded but never counted.
    - A paper that DISCUSSES tortured phrases or LLMs legitimately quotes its specimens; the metadiscussion and LLM-topic guards context-flag those matches.
    - 'Severity keys on DISTINCT fingerprints (k), never occurrences: one phrase pasted twenty times is one substitution event.'
    - 'QUARANTINED: delivered severity is indeterminate until the calibration gates pass; the pre-registered grade rides in severity_before_quarantine.'
    - 'Capped at `highly_suspicious`: awkward language violates no mathematics.'
---
# `tracks` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## analyze_paper_images

<!-- description:analyze_paper_images -->
Detect duplicated IMAGE PANELS within one paper: the same raster presented more than once across its PDF, supplements and container media. Byte-identity tiers (same xref placed twice; identical stream sha256) plus perceptual tiers (64-bit pHash; SIFT/ORB + RANSAC for rotated/flipped/rescaled/cropped copies), with texture and text-glyph gates. QUARANTINED: delivered severity is always indeterminate with the uncalibrated signal in severity_before_quarantine — report it as an unvalidated signal for human side-by-side review, never as a finding of record, and never in a headline. Detects panel-level duplication ONLY: splices, contrast manipulation and vector figures are out of scope, so a clean result is not image clearance. Check n_panels and n_skipped before reading zero groups as clean — a vector-figure paper has no embedded rasters, which is coverage absence, not cleanliness. Severity caps at highly_suspicious: duplication is improbable, never impossible. Pass stated_reuse=true when the paper SAYS panels are re-shown (a stated representative image is not duplication evidence).
<!-- /description:analyze_paper_images -->

## detect_tortured_phrases

<!-- description:detect_tortured_phrases -->
Screen a paper's PROSE against a versioned fingerprint dictionary: tortured phrases ("counterfeit consciousness" for "artificial intelligence"), LLM boilerplate ("as an AI language model"), and tortured acronym expansions. Deterministic and local; a hit asserts only that the phrase APPEARS -- the inference to paraphrasing-tool or undisclosed-LLM use is probabilistic. Severity keys on k = DISTINCT fingerprints surviving the guards (references section, quotation, metadiscussion, high-ambiguity entries), never on repetitions. QUARANTINED: delivered severity is always indeterminate with the pre-registered grade in severity_before_quarantine -- report it as an unvalidated signal for human review of the quoted spans, never as a finding of record, and never in a headline. A null result is coverage-bounded (the dictionary lists KNOWN fingerprints, skewed CS/engineering/biomedical), so a clean result is not language clearance. Severity caps at highly_suspicious: awkward language violates no mathematics.
<!-- /description:detect_tortured_phrases -->
