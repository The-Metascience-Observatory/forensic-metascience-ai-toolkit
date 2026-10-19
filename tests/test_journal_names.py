"""Journal-name normalization: known mappings map, unknowns pass through."""
from forensic_metascience_ai_toolkit.journal_names import mapping_counts, normalize, normalize_key


def test_vendored_data_actually_loaded():
    """The known-positive probe: an empty or missing vendored file must fail
    HERE, loudly, not ship a normalizer that silently never normalizes
    (LESSONS #4). Counted 2026-08-21: 33,354 abbreviations, 26 variants."""
    counts = mapping_counts()
    assert counts["abbreviations"] > 10_000
    assert counts["variant_forms"] >= 20


# -- three real mappings from the vendored data -------------------------------

def test_abbreviation_expansion_dev_sci():
    assert normalize("Dev. Sci") == "Developmental Science"


def test_abbreviation_expansion_j_pers_soc_psychol():
    assert normalize("J Pers Soc Psychol") \
        == "Journal of Personality and Social Psychology"


def test_variant_form_plos_one():
    assert normalize("PLOS ONE") == "PLOS One"


def test_variant_form_cognition_and_emotion():
    assert normalize("Cognition and Emotion") == "Cognition & Emotion"


# -- passthrough: unknown is returned, never nulled ---------------------------

def test_unknown_journal_passes_through_unchanged():
    name = "Journal of Entirely Imaginary Results"
    out = normalize(name)
    assert out == name
    assert out is not None and out != ""


def test_blank_and_nonstring_input_are_returned_as_given():
    assert normalize("") == ""
    assert normalize("   ") == "   "
    assert normalize(None) is None  # type: ignore[arg-type]


# -- lookup is case- and period-insensitive -----------------------------------

def test_lookup_ignores_case_and_periods():
    assert normalize("PSYCHOL. SCI.") == "Psychological Science"
    assert normalize("psychol sci") == "Psychological Science"


def test_normalize_key_folds_case_periods_whitespace():
    assert normalize_key("Dev.  Sci.") == "dev sci"


# -- the two ported guards, each against the case that defined it -------------

def test_qualifier_expansion_is_refused():
    """NLM maps 'AIDS' -> 'AIDS (London, England)' and 'BMJ' -> 'BMJ
    (Clinical research ed.)'; the input is already the canonical name and
    must not grow a location qualifier."""
    assert normalize("AIDS") == "AIDS"
    assert normalize("BMJ") == "BMJ"


def test_truncated_word_completion_still_expands():
    """'Death Stud' -> 'Death Studies': the word continues (no separator
    after the key), so this is a real abbreviation, not a qualifier."""
    assert normalize("Death Stud") == "Death Studies"


def test_a_canonical_full_name_is_never_reexpanded():
    """Idempotence: a name that is already a mapping VALUE passes through,
    even though its normalized form is a valid lookup key shape."""
    assert normalize("Developmental Science") == "Developmental Science"
    assert normalize("Psychological Science") == "Psychological Science"


# -- HTML entity fix ----------------------------------------------------------

def test_html_entity_amp_is_fixed():
    assert normalize("Accounting &amp; Finance") == "Accounting & Finance"


def test_normalize_is_idempotent_on_its_own_output():
    for name in ("Dev. Sci", "PLOS ONE", "Accounting &amp; Finance",
                 "Journal of Entirely Imaginary Results"):
        once = normalize(name)
        assert normalize(once) == once
