"""The passage a check's numbers came from, attached to the finding that cites them.

Greg's standing requirement: every number a check cites must be traceable to a
verbatim quote of the source text it came from, SURFACED IN THE FINDINGS so a
reader can see the number in its original context without opening the PDF.

The quote lived on the CALL and the accusation lives on the FINDING, and
nothing joined them. `sourcing.annotate` does, reusing the join
`severity_reconcile` already uses to answer the same question for a different
field ("which validated call produced this finding?").

THE FAILURE THESE TESTS EXIST TO PREVENT is not a missing quote. It is a WRONG
one: "here is the text your number came from", pointing at a different row. A
quote is the thing a reader trusts INSTEAD of checking, so a mis-attached
passage is more corrosive than most bugs, and it is the house failure pattern
exactly -- our join error published in the grammar of a claim about the paper.
Hence the unanimity rule, and hence most of what follows.
"""

from metascience_agent import sourcing


def call(tool, quote=None, verified=None, locator=None, source=None,
         validated=True, **args):
    entry = {"tool_short": tool, "validated": validated, "input": dict(args)}
    if quote is not None:
        entry["input"]["source_quote"] = quote
    if locator is not None:
        entry["input"]["source_locator"] = locator
    if verified is not None:
        entry["source_quote_verified"] = verified
    if source is not None:
        entry["source_quote_source"] = source
    return entry


def finding(technique="grim", **inputs):
    return {"id": "f1", "technique": technique, "inputs": dict(inputs)}


def annotate(findings, ledger):
    result = {"findings": {"findings": findings}}
    sourcing.annotate(result, ledger)
    return findings


class TestTheFindingCarriesThePassageItsNumbersCameFrom:
    def test_a_single_matching_call_attaches(self):
        led = [call("grim_check", quote="Mean age was 48.9 years (n = 142)",
                    verified="verbatim", source="the paper's text",
                    locator="Table 1, Age row", mean=48.9, n=142)]
        got = annotate([finding(mean=48.9, n=142)], led)[0]["source"]
        assert got["source_quote"] == "Mean age was 48.9 years (n = 142)"
        assert got["source_locator"] == "Table 1, Age row"
        assert got["source_quote_verified"] == "verbatim"

    def test_the_technique_family_still_joins_to_the_member_tool(self):
        """The model writes the FAMILY (`grim`) and the ledger records the
        member (`grim_percentage`). A one-to-one table matched nothing at all
        on the first real run; this reuses the corrected mapping."""
        led = [call("grim_percentage", quote="71.0% of participants",
                    verified="verbatim", percent=71.0, n=142)]
        assert annotate([finding("grim", percent=71.0, n=142)], led)[0]["source"]

    def test_a_finding_whose_inputs_are_prose_still_joins_when_the_tool_agreed(self):
        """Most findings' `inputs` are written for a human and carry nothing
        equality-joinable. If every call of the tool read the same passage,
        that passage is this finding's whichever call produced it."""
        led = [call("grim_check", quote="Mean age was 48.9 years",
                    verified="verbatim", mean=48.9, n=142),
               call("grim_check", quote="Mean age was 48.9 years",
                    verified="verbatim", mean=48.9, n=30)]
        got = annotate([{"id": "f", "technique": "grim",
                         "inputs": {"n": "not stated anywhere in the paper"}}], led)
        assert got[0]["source"]["source_quote"] == "Mean age was 48.9 years"

    def test_the_richest_record_wins_among_identical_passages(self):
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim", mean=48.9),
               call("grim_check", quote="Mean 48.9", verified="verbatim",
                    source="a table", locator="Table 2", mean=48.9)]
        got = annotate([finding(mean=48.9)], led)[0]["source"]
        assert got["source_locator"] == "Table 2" and got["source_quote_source"] == "a table"


class TestItRefusesRatherThanAttachTheWrongPassage:
    def test_two_calls_quoting_DIFFERENT_passages_attach_nothing(self):
        """The core safety rule. Both calls match the finding's scalars; we
        cannot say which row the model meant, and guessing would put one row's
        evidence under another row's accusation."""
        led = [call("grim_check", quote="Age: mean 48.9", verified="verbatim", n=142),
               call("grim_check", quote="BMI: mean 27.4", verified="verbatim", n=142)]
        assert "source" not in annotate([finding(n=142)], led)[0]

    def test_a_call_of_a_different_tool_is_not_borrowed(self):
        led = [call("recalc_independent_t", quote="t(58) = 3.87", verified="verbatim",
                    mean1=10.0)]
        assert "source" not in annotate([finding("grim", mean1=10.0)], led)[0]

    def test_an_unvalidated_call_contributes_nothing(self):
        """An unvalidated call is the model running its own code. Its account of
        where a number came from is not a tool's account."""
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim",
                    validated=False, mean=48.9)]
        assert "source" not in annotate([finding(mean=48.9)], led)[0]

    def test_a_finding_the_model_pre_stamped_is_stripped_before_we_decide(self):
        """The one place a forged provenance could enter looking native. The
        party being checked does not certify itself -- the same rule that
        governs `quote_verified` and `reproduction_valid`."""
        pre = {"id": "f", "technique": "grim", "inputs": {"mean": 1.0},
               "source": {"source_quote": "a passage nobody supplied"}}
        assert "source" not in annotate([pre], [])[0]

    def test_scalars_that_do_not_match_do_not_join(self):
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim", mean=48.9, n=142)]
        assert "source" not in annotate([finding(mean=48.9, n=30)], led)[0]

    def test_a_manual_finding_never_joins(self):
        """`technique: manual` means the model read it off the paper itself. It
        has no producing call, and inventing one would be the worst kind of
        laundering: hand-read text presented as tool-sourced."""
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim", mean=48.9)]
        assert "source" not in annotate([finding("manual", mean=48.9)], led)[0]


class TestAnUnlocatedPassageIsCarriedButNotPromoted:
    def test_the_verdict_travels_with_the_quote(self):
        """`stitched`/`unverified` are carried so the renderers can decline to
        make the "as printed" promise. Dropping them here would leave the
        viewer unable to tell a located quote from an unlocated one."""
        led = [call("grim_check", quote="a sentence nobody can find",
                    verified="unverified", mean=48.9)]
        got = annotate([finding(mean=48.9)], led)[0]["source"]
        assert got["source_quote_verified"] == "unverified"

    def test_an_unadjudicated_quote_carries_no_verdict_at_all(self):
        """When the paper could not be read, `verify_ledger` stamps nothing.
        The finding must then make no claim either way rather than defaulting
        to a promise."""
        led = [call("grim_check", quote="Mean 48.9", mean=48.9)]
        got = annotate([finding(mean=48.9)], led)[0]["source"]
        assert "source_quote_verified" not in got


class TestCoverageIsCounted:
    def test_the_run_records_how_many_findings_were_traced(self):
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim", mean=48.9)]
        result = {"findings": {"findings": [finding(mean=48.9), finding(mean=1.0)]}}
        sourcing.annotate(result, led)
        assert result["run_meta"]["sourcing"] == {
            "findings": 2, "joinable": 2, "traced_to_a_passage": 1}

    def test_an_empty_ledger_is_not_an_error(self):
        result = {"findings": {"findings": [finding(mean=48.9)]}}
        sourcing.annotate(result, None)
        assert result["run_meta"]["sourcing"]["traced_to_a_passage"] == 0

    def test_a_malformed_result_is_left_alone(self):
        assert sourcing.annotate({}, []) == {}
        assert sourcing.annotate({"findings": "not a dict"}, []) is not None


class TestAToolTakingListsCanStillBeJoined:
    """MEASURED: this one bug held the join at 27% of joinable findings instead
    of 44%. `check_summation`, `detect_duplication` and `multiplicity_report`
    pass LISTS; `_scalars` drops lists, so the call contributes no comparable
    scalars, and requiring the finding's numbers to appear in it ruled the call
    out every single time -- including when it was the only call of that tool."""

    def test_a_list_argument_call_joins_a_finding_that_names_numbers(self):
        # The real shape, taken from the archive: `check_summation_batch` is
        # called with a single `rows` list and no scalar arguments at all.
        led = [{"tool_short": "check_summation_batch", "validated": True,
                "source_quote_verified": "verbatim",
                "input": {"rows": [{"values": [10, 20, 30], "total": 61}],
                          "source_quote": "Totals: 10 + 20 + 30 = 61"}}]
        got = annotate([finding("check_summation", expected_sum=60, tolerance=0)], led)
        assert got[0]["source"]["source_quote"] == "Totals: 10 + 20 + 30 = 61"

    def test_it_still_refuses_when_two_such_calls_disagree(self):
        """The relaxation must not outrun the guard: with nothing to
        discriminate on, two list-argument calls quoting different passages are
        exactly the case where a guess would attach the wrong table."""
        led = [{"tool_short": "check_summation_batch", "validated": True,
                "input": {"rows": [{"values": [1, 2]}], "source_quote": "Table 2 totals"}},
               {"tool_short": "check_summation_batch", "validated": True,
                "input": {"rows": [{"values": [3, 4]}], "source_quote": "Table 3 totals"}}]
        assert "source" not in annotate([finding("check_summation", expected_sum=60)], led)[0]

    def test_a_call_WITH_scalars_is_still_held_to_them(self):
        """The relaxation applies only to calls that have no scalars at all. A
        call whose numbers are present and different must still not match."""
        led = [{"tool_short": "grim_check", "validated": True,
                "input": {"mean": 4.2, "n": 15, "source_quote": "a different row"}}]
        assert "source" not in annotate([finding("grim", mean=5.08, n=15)], led)[0]


class TestManualFindingsAreNotCountedAsMisses:
    def test_they_are_excluded_from_the_denominator(self):
        """A `manual` finding was read off the paper by the model; there is no
        producing call. Counting it as untraced would report a design fact as a
        coverage failure. MEASURED: 92 of 377 archived findings (24%)."""
        result = {"findings": {"findings": [
            finding("manual", mean=1.0), finding("grim", mean=48.9)]}}
        led = [call("grim_check", quote="Mean 48.9", verified="verbatim", mean=48.9)]
        sourcing.annotate(result, led)
        assert result["run_meta"]["sourcing"] == {
            "findings": 2, "joinable": 1, "traced_to_a_passage": 1}


class TestLocatorDisambiguation:
    """When the quotes disagree, ask where each call said it was looking.

    The join keyed only on `reported`/`inputs` numbers. A finding whose numbers
    are not a strict subset of its call's arguments -- differing by a
    `decimals_mean` or a `p_is_threshold` -- failed on a technicality while
    plainly describing the same table row, and every such finding lost its
    quote.

    MEASURED on 10.1007--s11064-023-03861-8: 8 rivets_independent_t calls, 8
    findings, 1 joined. Each finding names its row in prose ("Table 2,
    Respiration cycle/min, Nerve Lesion 4 wk...") and each call's own
    `source_locator` nearly repeats it. Across four archived runs the join went
    30/84 to 44/84 with zero cross-table attributions.
    """

    @staticmethod
    def _ledger(*locators):
        return [{"tool": "mcp__forensic_metascience__grim_check",
                 "tool_short": "grim_check", "validated": True,
                 "input": {"mean": 5.0 + i, "n": 30,
                           "source_quote": f"quote {i}",
                           "source_locator": loc}}
                for i, loc in enumerate(locators)]

    def _join(self, location, *locators, inputs=None):
        from metascience_agent import sourcing
        finding = {"technique": "grim_check", "location": location,
                   "inputs": inputs or {"unmatchable": 999999}}
        out = sourcing.annotate(
            {"findings": {"findings": [finding]}}, self._ledger(*locators))
        return (out["findings"]["findings"][0].get("source") or {})

    def test_a_unique_locator_match_is_used(self):
        s = self._join("Table 2, Respiration cycle/min, Nerve Lesion 4 wk",
                       "Table 2, Respiration cycle/min column: Nerve Lesion 4 wk",
                       "Table 3, Paw Withdrawal Latency column: NL + Al NPs")
        assert s.get("source_matched_by") == "locator"
        assert s.get("source_quote") == "quote 0"

    def test_a_tie_still_refuses(self):
        """Narrowing an ambiguous set is allowed; picking from equals is not."""
        s = self._join("Table 2, Respiration cycle/min",
                       "Table 2, Respiration cycle/min column: A",
                       "Table 2, Respiration cycle/min column: B")
        assert not s.get("source_quote")

    def test_single_digits_discriminate(self):
        """The regression that made the first version useless on the case it
        was written for: '4 wk' vs '10 wk' tie unless single digits count."""
        s = self._join("Table 2, Nerve Lesion 4 wk",
                       "Table 2, Nerve Lesion 4 wk column",
                       "Table 2, Nerve Lesion 10 wk column")
        assert s.get("source_quote") == "quote 0"

    def test_a_weak_overlap_is_not_a_match(self):
        """Two shared content words is the floor -- one is a coincidence."""
        s = self._join("Table 2, Respiration cycle/min",
                       "Figure 4, arterial pH trace")
        assert not s.get("source_quote")

    def test_a_finding_with_no_usable_location_refuses(self):
        assert not self._join("", "Table 2, something").get("source_quote")

    def test_boilerplate_alone_never_matches(self):
        """'Table' and 'column' appear in every locator and discriminate
        nothing, so they must not carry a match by themselves."""
        s = self._join("Table", "Table column", "Table row")
        assert not s.get("source_quote")

    def test_the_scalar_path_still_wins_when_it_works(self):
        """Locator matching is a FALLBACK. An exact scalar join must not be
        overridden by it, and must not be labelled as one."""
        from metascience_agent import sourcing
        led = [{"tool": "mcp__forensic_metascience__grim_check",
                "tool_short": "grim_check", "validated": True,
                "input": {"mean": 5.19, "n": 28, "source_quote": "M = 5.19 (n = 28)",
                          "source_locator": "Table 1"}}]
        out = sourcing.annotate({"findings": {"findings": [
            {"technique": "grim_check", "location": "Table 1",
             "inputs": {"mean": 5.19, "n": 28}}]}}, led)
        s = out["findings"]["findings"][0]["source"]
        assert s["source_quote"] == "M = 5.19 (n = 28)"
        assert s.get("source_matched_by") != "locator"
