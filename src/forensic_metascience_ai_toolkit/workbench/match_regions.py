"""Queue filters over saved match geometry; no new detection or verdicts."""
from __future__ import annotations

import math

REGION_FIELDS = ('engine', 'matched_frac_a', 'matched_frac', 'inlier_box_a', 'inlier_box_b', 'rotation_deg', 'scale', 'flip')
REGION_MODES = ('partial_both', 'partial_one', 'large_both', 'unknown')
DEFAULT_MAX_PERCENT = 80


def max_region_percent(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_PERCENT
    return number if math.isfinite(number) and 1 <= number <= 99 else DEFAULT_MAX_PERCENT


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def region_coverage(item):
    """Fractions of the two *compared panels*, not of their parent figures.

    matched_frac is B; coverage_frac is the warped whole-frame overlap and
    cannot answer this question. The masked-NCC tier writes the smaller-panel
    overlap to BOTH fraction fields, so those are not two denominators. A
    clone inside one panel is also outside this two-image filter.
    """
    if len(item.get('panels') or []) != 2 or item.get('detector_kind') == 'intra_panel_clone':
        return None
    stats = item.get('region_measurements') or item.get('measurements') or {}
    if stats.get('engine') == 'masked_ncc':
        return None
    fractions = (stats.get('matched_frac_a'), stats.get('matched_frac'))
    if not all(_number(v) and 0 < v <= 1 for v in fractions):
        return None
    for side in ('a', 'b'):
        box = stats.get(f'inlier_box_{side}')
        if not isinstance(box, (list, tuple)) or len(box) != 4 or not all(_number(v) for v in box):
            return None
        if not (0 <= box[0] < box[2] and 0 <= box[1] < box[3]):
            return None
    return dict(a=fractions[0], b=fractions[1])


def region_kind(coverage, max_percent=DEFAULT_MAX_PERCENT):
    if coverage is None:
        return 'unknown'
    cutoff = max_region_percent(max_percent) / 100
    partial = sum(coverage[side] <= cutoff for side in ('a', 'b'))
    return ('large_both', 'partial_one', 'partial_both')[partial]


TRANSFORMATION_MODES = ('translation', 'rotation', 'resizing', 'reflection', 'combined', 'unknown')
#: A rotation counts only past this many degrees, either direction; a few degrees of tilt is registration noise.
ROTATION_MIN_DEGREES = 10
#: The queue's "any suspicious" filter: a measured rotation or reflection, alone or combined. Resizing alone is
#: routine rescaling, and `unknown` means the transformation was never measured.
SUSPICIOUS_TRANSFORMATIONS = ('rotation', 'reflection', 'combined')


def transformation_kind(item):
    stats = item.get('region_measurements') or item.get('measurements') or {}
    angle, scale, flip = stats.get('rotation_deg'), stats.get('scale'), stats.get('flip')
    if not _number(angle) or not _number(scale) or scale <= 0 or not isinstance(flip, bool):
        return 'unknown'
    changes = [name for name, present in (
        ('rotation', abs((angle + 180) % 360 - 180) > ROTATION_MIN_DEGREES),
        ('resizing', abs(scale - 1) > .02), ('reflection', flip)) if present]
    return 'combined' if len(changes) > 1 else changes[0] if changes else 'translation'


FIGURE_SPANS = ('different_figures', 'same_figure', 'different_papers', 'unknown')


def _figure_of(label):
    """One key per printed figure, or None when the label names none.

    `figure_key` is the package's canonical form: `Figure 3 (cont.)` and
    `Figure 3B` are Figure 3, `Figure S3` is not. Labels outside its grammar
    (`Extended Data 2:`, `Scheme 2.`, `Figure-5`, a bare `4`) keep their own
    spelling, normalised; a bare `Figure` names no particular figure.
    """
    from ..image_plugin import load
    figure_key = load("image_forensics.figure_context").figure_key
    if not label:
        return None
    text = ' '.join(str(label).split())
    key = figure_key(text) or figure_key(text.replace('-', ' ', 1))
    if key:
        return key
    text = text.rstrip(':.;, ').lower()
    return text if any(c.isdigit() for c in text) or text == 'graphical abstract' else None


def figure_span(item):
    """Whether an item's evidence comes from different figures of one paper.

    The detector's rule (`image_analysis._spans_figures`): the item spans
    figures when its placements name two DIFFERENT figures. Placements count,
    not only panels -- one image printed in Figure 1 and Figure 2 is a single
    panel whose item carries both labels. `same_figure` needs every panel
    labelled and one figure in all; one labelled panel beside an unlabelled
    one is `unknown`, because a missing label is a missing fact, not a match.
    Cross-paper items are `different_papers`: a separate question, and the
    `kind` filter already selects them.
    """
    panels = item.get('panels') or []
    papers = {p.get('paper_dir') for p in panels if p.get('paper_dir')}
    if item.get('kind') == 'cross' or len(papers) > 1:
        return 'different_papers'
    panel_keys = [_figure_of(p.get('figure_label')) for p in panels]
    known = {k for k in panel_keys if k}
    known |= {k for k in map(_figure_of, item.get('figure_labels') or ()) if k}
    if len(known) > 1:
        return 'different_figures'
    if len(known) == 1 and panel_keys and all(panel_keys):
        return 'same_figure'
    return 'unknown'
