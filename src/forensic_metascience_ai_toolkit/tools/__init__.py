"""Forensic metascience analysis tools."""

# GRIM tests
from .grim import (
    grim_test,
    grim_test_percentage,
    grim_sweep,
    reconstruct_2x2,
)

# T-test recalculation
from .ttest import (
    recalc_independent_t,
    recalc_within_subjects_t,
)

# ANOVA recalculation
from .anova import (
    recalc_one_way_anova,
    recalc_f_to_p,
)

# Effect size recovered from an F and its degrees of freedom
from .effect_size_from_f import (
    effect_size_from_f,
)

# Chi-squared test
from .chi_squared import (
    recalc_chi_squared,
)

# SD checks (including GRIMMER)
from .sd_checks import (
    check_sd_range,
    grimmer_test,
)

# Summation checks
from .summation import (
    check_summation,
)

# Participant-flow (CONSORT) arithmetic
from .flow import (
    check_flow_arithmetic,
)

# Ratio checks
from .ratio import (
    check_ratio,
)

# Regression checks
from .regression import (
    check_regression,
)

# SPRITE reconstruction
from .sprite import (
    sprite_reconstruct,
)

# STALT check
from .stalt import (
    stalt_check,
)

# CSF test
from .csf import (
    csf_test,
)

# DEBIT (binary mean/SD consistency)
from .debit import (
    debit_test,
    debit_test_batch,
)

# SD/SE confusion check
from .se_sd import (
    check_sd_or_se,
)

# Heuristic flags
from .heuristics import (
    flag_round_n,
    flag_uninformative_stat,
)

# RIVETS (hand-calculation detector)
from .rivets import (
    rivets_independent_t,
    rivets_anova,
)

# Continuous → categorical proportion plausibility
from .continuous_to_categorical import (
    check_proportion_from_normal,
)

# Bayesian Table 1 dispersion
from .table1_dispersion import (
    table1_dispersion,
)

# Variance dispersion across groups (are the SDs too similar?)
from .variance_dispersion import (
    check_variance_dispersion,
)

# Table ingestion + duplication detection
from .tableparse import (
    parse_cell,
    parse_table,
    reconcile_tables,
)
from .duplication import (
    detect_duplication,
)
# The raw-data detector is its own package, rooted at copy_paste_detector/src.
# Without that root on sys.path, the bare project folder at the repo root
# imports as an EMPTY namespace package and the stock error reads "cannot
# import name ... (unknown location)", which names nothing a reader can act on.
try:
    from copy_paste_detector import detect_raw_duplication
except ImportError as _exc:
    raise ImportError(
        "copy_paste_detector is not importable. The package lives in "
        "copy_paste_detector/src, NOT under src/: re-run `pip install -e .` "
        "(an editable install made before 2026-09-08 lists only src/), or put "
        "copy_paste_detector/src on PYTHONPATH. With the real root missing, the "
        "bare copy_paste_detector/ project folder at the repo root shadows the "
        "package as an empty namespace, which is why this reads 'unknown location'."
    ) from _exc
# `analyze_paper_images` lives in `image_forensics/image_analysis.py`, which
# imports `.quarantine` and `.severity` from THIS package. An eager import here
# is a cycle whenever the detector is imported first -- which is exactly what
# the image-track child process does -- and it failed with "partially
# initialized module" on the first real run after the move (2026-09-01). The
# name stays exported, resolved on first access (PEP 562).
from .tortured_phrases import (
    detect_tortured_phrases,
)

# GRIM-U (rank-sum p-value granularity)
from .grimu import (
    grimu_check,
    grimu_coexistence,
)

# R wrappers (optional, requires R installation)
from .r_wrappers import (
    r_sprite,
    r_grim,
    r_statcheck,
    python_statcheck,
    python_statcheck_text,
    run_r_code,
)

__all__ = [
    # GRIM
    "grim_test",
    "grim_test_percentage",
    "grim_sweep",
    "reconstruct_2x2",
    # T-tests
    "recalc_independent_t",
    "recalc_within_subjects_t",
    # ANOVA
    "recalc_one_way_anova",
    "recalc_f_to_p",
    "effect_size_from_f",
    "paired_d_interval",
    # Chi-squared
    "recalc_chi_squared",
    # SD checks
    "check_sd_range",
    "grimmer_test",
    # Summation
    "check_summation",
    # Participant flow
    "check_flow_arithmetic",
    # Ratio
    "check_ratio",
    # Regression
    "check_regression",
    # SPRITE
    "sprite_reconstruct",
    # STALT
    "stalt_check",
    # CSF
    "csf_test",
    # DEBIT
    "debit_test",
    "debit_test_batch",
    # SD/SE confusion
    "check_sd_or_se",
    # Heuristics
    "flag_round_n",
    "flag_uninformative_stat",
    # RIVETS
    "rivets_independent_t",
    "rivets_anova",
    # Continuous → categorical
    "check_proportion_from_normal",
    # Bayesian Table 1 dispersion
    "table1_dispersion",
    # Variance dispersion across groups
    "check_variance_dispersion",
    # Table ingestion + duplication
    "parse_cell",
    "parse_table",
    "reconcile_tables",
    "detect_duplication",
    "detect_raw_duplication",
    "analyze_paper_images",
    "detect_tortured_phrases",
    # GRIM-U
    "grimu_check",
    "grimu_coexistence",
    # R wrappers
    "r_sprite",
    "r_grim",
    "r_statcheck",
    "python_statcheck",
    "python_statcheck_text",
    "run_r_code",
]


def __getattr__(name: str):
    if name == "analyze_paper_images":
        from ..image_plugin import load
        return load("image_forensics.image_analysis").analyze_paper_images
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
