"""The model may name a format; it may not write the parser.

GREG, 2026-08-11, after seeing a table where every cell failed to parse:

    "I worry that using regex to decompose cells containing two types of values
     might be too brittle. Now, correct me if I'm wrong, i would like the agent
     to be able to understand the raw table contents well enough to develop
     it's own custom regex for the purpose of creating a complete table. For
     example, what if this table from the Gino paper used curly brackets
     instead of parentheses to surround the standard deviation?"

The brittleness is real and the measurement confirms it: `5.38 {1.17}` was
`non_numeric`, and so was every other convention not on the hardcoded list.

The proposed cure is refused, and the refusal is the design. A model-written
regex is a model-written statistic: whatever it captures becomes the mean we
run GRIM against, and the failure mode is not a crash but a plausible number
that no downstream layer can recognise as invented. So the model declares a
format from a CLOSED VOCABULARY -- two enum choices -- and code in this
repository does every character of the matching.
"""
import pytest

from forensic_metascience_ai_toolkit.tools import cellformat as CF
from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells


class TestGregsQuestion:
    """Curly brackets, exactly as asked."""

    def test_the_brace_cell_is_unreadable_without_a_declaration(self):
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cell
        assert parse_cell("5.38 {1.17}").kind == "non_numeric"

    def test_and_reads_correctly_with_one(self):
        c = CF.parse_cell_as("5.38 {1.17}", "mean_sd:brace")
        assert c.kind == "mean_sd"
        assert c.value == 5.38 and c.sd == 1.17

    def test_the_printed_precision_survives_the_declaration(self):
        """Every granularity test sizes its rounding interval off this. A
        declared parse that dropped it would hand GRIMMER a tenfold-too-narrow
        interval and manufacture impossibilities out of correct numbers."""
        c = CF.parse_cell_as("5.38 {1.17}", "mean_sd:brace")
        assert c.decimals_value == 2 and c.decimals_sd == 2

    def test_supporting_a_new_convention_is_a_vocabulary_entry(self):
        """The point of the pairing x delimiter split. Not one of these needed
        a new code path; they are the same parser over a different constant."""
        for text, delim in [("5.38 (1.17)", "paren"), ("5.38 [1.17]", "bracket"),
                            ("5.38 {1.17}", "brace"), ("5.38 <1.17>", "angle"),
                            ("5.38 ± 1.17", "plusminus"), ("5.38, 1.17", "comma"),
                            ("5.38; 1.17", "semicolon"), ("5.38 / 1.17", "slash")]:
            c = CF.parse_cell_as(text, f"mean_sd:{delim}")
            assert c.kind == "mean_sd", f"{text} under mean_sd:{delim}"
            assert c.value == 5.38 and c.sd == 1.17


class TestTheVocabularyIsClosed:
    def test_an_unknown_delimiter_is_refused_and_the_menu_is_named(self):
        with pytest.raises(ValueError) as e:
            CF.parse_format("mean_sd:curly")
        assert "curly" in str(e.value) and "brace" in str(e.value)

    def test_an_unknown_pairing_is_refused(self):
        with pytest.raises(ValueError) as e:
            CF.parse_format("mean_ci:paren")
        assert "mean_sd" in str(e.value)

    def test_a_bare_word_is_not_a_format(self):
        with pytest.raises(ValueError) as e:
            CF.parse_format("mean_sd")
        assert "<pairing>:<delimiter>" in str(e.value)

    def test_apply_format_returns_the_error_rather_than_raising(self):
        """The tool layer must be able to hand the model back the vocabulary.
        An exception here would surface as a tool crash, which reads as 'the
        table is unreadable' rather than 'you named a format that fits'."""
        r = CF.apply_format([{"raw": "1 (2)"}], "mean_sd:curly")
        assert r["applied"] is False
        assert "brace" in r["error"]
        assert r["vocabulary"]["n_formats"] == len(CF.PAIRINGS) * len(CF.DELIMITERS)

    def test_a_bare_space_is_NOT_a_delimiter(self):
        """Measured reason: the corpus cells a space delimiter would consume are
        `'7 : 18 4 : 8'` -- two columns welded by the extractor. Reading those
        as a mean and an SD converts OUR defect into the paper's number."""
        assert "space" not in CF.DELIMITERS
        assert "colon" not in CF.DELIMITERS


class TestADeclarationIsTestedNotObeyed:
    """The cardinal rule reaches this module as: a wrong declaration must not
    be able to manufacture an accusation."""

    def test_a_percentage_column_declared_as_mean_sd_still_parses(self):
        """Honest about the limit: `142 (71.0)` genuinely fits both readings and
        the numbers cannot choose. This is why the declaration is a READING
        task for the model and why `n_overrides_automatic` exists."""
        c = CF.parse_cell_as("142 (71.0)", "mean_sd:paren")
        assert c.kind == "mean_sd"

    def test_but_an_n_percent_declaration_that_cannot_be_true_is_refused(self):
        c = CF.parse_cell_as("4.2 (150.0)", "n_percent:paren")
        assert c.kind == "non_numeric"
        assert "150" in c.warning and "refused" in c.warning.lower()

    def test_a_non_integer_count_is_refused(self):
        c = CF.parse_cell_as("4.2 (15.0)", "n_percent:paren")
        assert c.kind == "non_numeric"
        assert "integer" in c.warning

    def test_a_negative_dispersion_is_refused(self):
        c = CF.parse_cell_as("5.38 (-1.17)", "mean_sd:paren")
        assert c.kind == "non_numeric"
        assert "negative" in c.warning

    def test_an_inverted_interval_is_refused(self):
        c = CF.parse_cell_as("1.42 (1.87-1.08)", "estimate_ci:paren")
        assert c.kind == "non_numeric"
        assert "inverted" in c.warning

    def test_an_estimate_outside_its_own_interval_is_refused(self):
        c = CF.parse_cell_as("9.9 (1.08-1.87)", "estimate_ci:paren")
        assert c.kind == "non_numeric"
        assert "outside" in c.warning

    def test_a_skewed_median_declared_as_an_estimate_with_a_CI_is_refused(self):
        """The exact false positive `check_estimate_ci` produced on ordinary
        length-of-stay data. A declaration must not be able to re-open it."""
        c = CF.parse_cell_as("5 (3-15)", "estimate_ci:paren")
        assert c.kind == "non_numeric"
        assert "midpoint" in c.warning

    def test_the_same_cell_IS_accepted_as_a_median_with_its_range(self):
        c = CF.parse_cell_as("5 (3-15)", "median_range:paren")
        assert c.kind == "median_range"
        assert c.low == 3 and c.high == 15


class TestAPartialFitIsNotAFormat:
    def test_a_declaration_fitting_half_a_column_is_refused_wholesale(self):
        cells = [{"raw": r} for r in
                 ["5.38 (1.17)", "4.20 (0.98)", "not a number", "also text"]]
        r = CF.apply_format(cells, "mean_sd:paren")
        assert r["applied"] is False
        assert r["fit_rate"] == 0.5
        assert r["cells"] == []          # nothing handed downstream
        assert r["misfits"]              # but the evidence is returned

    def test_a_column_with_one_dash_is_still_applied(self):
        """MIN_FIT is 0.8, not 1.0, precisely so one `-` cannot reject a correct
        declaration over the cells around it."""
        cells = [{"raw": r} for r in
                 ["5.38 (1.17)", "4.20 (0.98)", "3.11 (1.02)", "6.02 (0.77)", "-"]]
        r = CF.apply_format(cells, "mean_sd:paren")
        assert r["applied"] is True
        assert r["n_fit"] == 4 and r["fit_rate"] == 0.8

    def test_it_reports_what_the_declaration_actually_bought(self):
        """A declaration that recovers cells already readable is worth nothing,
        and the output has to say so rather than counting them as a win."""
        cells = [{"raw": r} for r in ["5.38 {1.17}", "4.20 {0.98}"]]
        r = CF.apply_format(cells, "mean_sd:brace")
        assert r["n_recovered"] == 2 and r["n_already_readable"] == 0

    def test_and_warns_when_it_contradicts_the_papers_own_headers(self):
        cells = [{"raw": "142 (71.0)", "col_label": "n (%)"},
                 {"raw": "38 (19.0)", "col_label": "n (%)"}]
        r = CF.apply_format(cells, "mean_sd:paren")
        assert r["n_overrides_automatic"] == 2
        assert any("headers" in w for w in r["warnings"])


class TestFootnoteMarkersDoNotChangeTheFormat:
    def test_the_gino_significance_subscript_survives_a_declaration(self):
        """`celltypes` learned this twice. Re-learning it one module over would
        put the same bug back: in the Gino SI every one of 153 mean (SD) cells
        carries a trailing subscript."""
        c = CF.parse_cell_as("2.37 (0.92)a", "mean_sd:paren")
        assert c.kind == "mean_sd"
        assert c.value == 2.37 and c.sd == 0.92
        assert c.markers == ["a"]

    def test_a_marker_alone_does_not_rescue_an_unreadable_cell(self):
        assert CF.parse_cell_as("n/a*", "mean_sd:paren").kind == "non_numeric"


class TestTheProseNumericSplit:
    """Without it the alarm fires on every table in the corpus and means
    nothing: 2,533 corpus cells are `non_numeric` and only 421 are ours."""

    def test_a_row_label_is_not_a_failed_value(self):
        assert not CF.is_numeric_shaped(CF.shape_of("Stage 1 hypertension at age 12 y"))
        assert not CF.is_numeric_shaped(CF.shape_of("Ethnic group (ref = Han)"))

    def test_a_value_we_could_not_read_is(self):
        assert CF.is_numeric_shaped(CF.shape_of("5.38 {1.17}"))
        assert CF.is_numeric_shaped(CF.shape_of("<0.001"))
        assert CF.is_numeric_shaped(CF.shape_of("2.37 (0.92)a"))

    def test_a_cell_with_no_digits_at_all_is_prose(self):
        assert not CF.is_numeric_shaped(CF.shape_of("NA"))

    def test_the_shape_erases_content_but_keeps_punctuation(self):
        assert CF.shape_of("5.38 (1.17)") == CF.shape_of("142.99 (7.10)")
        assert CF.shape_of("5.38 (1.17)") != CF.shape_of("5.38 [1.17]")


class TestTheLoudSignal:
    def test_a_block_of_identically_failing_cells_is_ONE_finding(self):
        cells = [{"raw": f"{i}.38 {{1.17}}"} for i in range(20)]
        r = CF.describe_unparsed(cells)
        assert r["n_unread_numeric_shaped"] == 20
        assert len(r["warnings"]) == 1
        assert "20 cell(s)" in r["warnings"][0]
        assert "mean_sd:brace" in r["warnings"][0]

    def test_the_warning_does_not_crash_on_the_brace_shape(self):
        """The shape string is built from the cell's own punctuation, so a
        braced cell puts a literal `{` in it. Any `.format`/`%` template in the
        warning path raises on exactly the cells this module exists to read --
        which is how this was caught."""
        r = CF.describe_unparsed([{"raw": "5.38 {1.17}"}] * 8)
        assert "{" in r["clusters"][0]["shape"]
        assert r["warnings"] and "9.9 {9.9}" in r["warnings"][0]

    def test_prose_clusters_get_no_format_suggestions(self):
        """Suggesting a mean/SD reading for a row label would be the module
        inviting the misdeclaration its guards exist to refuse."""
        r = CF.describe_unparsed([{"raw": f"Obesity at age {i} y"} for i in range(12)])
        assert r["n_unread_numeric_shaped"] == 0
        assert r["clusters"][0]["candidate_formats"] == []
        assert r["warnings"] == []

    def test_it_says_so_when_nothing_in_the_vocabulary_fits(self):
        """Saying "no format parses these" is the honest answer; inventing one
        would not be.

        THE EXAMPLE CHANGED, AND THE CHANGE IS THE POINT. This test used to use
        `<0.001`, called here "the corpus's single largest unread numeric
        shape". It is read now: `celltypes` parses a censored cell to its BOUND
        with the operator beside it, and `NEVER_DISPATCH` stops any tool
        consuming it. So the shape left the unread class by being handled, which
        is the only way a shape should leave it.

        `1 (<1%)` replaces it because it is still genuinely unread and is not
        invented: a 196-paper cell survey found 45 such cells across two
        papers' safety tables. A composite whose second component is itself
        censored fits no pairing in the vocabulary.
        """
        r = CF.describe_unparsed([{"raw": "1 (<1%)"}] * 10)
        assert r["n_unread_numeric_shaped"] == 10
        assert r["clusters"][0]["candidate_formats"] == []
        assert "No format in the vocabulary" in r["warnings"][0]

    def test_a_censored_cell_is_no_longer_in_the_unread_class(self):
        """The shape this test used to be about. It is parsed, so it is not
        unparsed -- and `describe_unparsed` only ever sees what failed."""
        r = CF.describe_unparsed([{"raw": "<0.001"}] * 10)
        assert r["n_unread_numeric_shaped"] == 0


class TestParseCellsCarriesTheDiagnosis:
    """Computed inside `parse_cells`, not offered as a tool that can be
    declined: the two worst bugs in `celltypes` were both a whole table failing
    one way at a time, and both survived as long as the failure was per-cell."""

    def test_every_parse_cells_result_carries_it(self):
        r = parse_cells([{"raw": "5.38 (1.17)", "col_label": "Mean (SD)"}])
        assert "unparsed" in r
        assert r["unparsed"]["n_unread"] == 0

    def test_an_unhandled_convention_reaches_the_top_level_warnings(self):
        r = parse_cells([{"raw": "5.38 {1.17}"}] * 12)
        assert r["coverage"] == 0.0
        assert any("unhandled convention" in w for w in r["warnings"])
        assert any("mean_sd:brace" in w for w in r["warnings"])

    def test_a_table_of_row_labels_raises_no_alarm(self):
        r = parse_cells([{"raw": "Age group"}, {"raw": "Sex"}, {"raw": "BMI"}])
        assert r["unparsed"]["n_unread"] == 3
        assert r["unparsed"]["n_unread_numeric_shaped"] == 0
        assert not any("unhandled convention" in w for w in r["warnings"])
