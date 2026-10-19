"""A .docx supplement has span markup, and the reader was throwing it away.

`supplements_read._finish` defaults `header_rows` to 1 and its docstring
justified that for the .docx/.csv/.xlsx readers as "sources have no span
structure to read". That is true of .csv, and false of .docx: OOXML merges are
exactly what `python-docx` exposes, and the reader was ALREADY computing them
-- it blanks a merged cell's continuations so a single measurement is not
counted several times -- and then dropped the fact before `_finish` saw it.

What the one-row reading costs, on `EAT-58-1072-s001.docx` Table S.4:

    r0  Table S.4. Explanatory ...        <- caption, spans all 7 columns
    r1  '' | Within-Person | Between-Person   <- spans 3 each
    r2  '' | b (SE) | p | beta | b (SE) | p | beta

Depth 1 takes the CAPTION as the column labels, so six of seven columns are
reported as `(unlabelled column N)` and both `p` columns cease to exist. The
p-values under them then reach the register with role `unknown`, which is why
no p-value check can dispatch on them.
"""
import pathlib
import pytest

from metascience_agent.extraction import supplements_read as S

DOCX = pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/"
                    "EAT-58-1072-s001.docx")

pytestmark = pytest.mark.skipif(not DOCX.exists(),
                                reason="EAT supplement not in this checkout")


class TestTheSpanMarkupIsRead:
    def test_the_stacked_header_is_three_rows_deep(self):
        tables = S.extract_docx_tables(DOCX)["tables"]
        t4 = tables[3]
        assert t4["n_header_rows"] == 3, (
            "r0 spans 7 and r1 spans 3, so the columns are distinguished only "
            "by r2; a shallower reading loses them")

    def test_the_p_columns_exist(self):
        t4 = S.extract_docx_tables(DOCX)["tables"][3]
        heads = [str(h) for h in (t4.get("headers") or [])]
        assert sum(1 for h in heads if h.strip().endswith("p")) >= 2, (
            f"both p columns must be named, got {heads}")

    def test_no_column_is_labelled_by_the_caption(self):
        t4 = S.extract_docx_tables(DOCX)["tables"][3]
        heads = " ".join(str(h) for h in (t4.get("headers") or []))
        assert "Table S.4" not in heads, (
            "the caption is not a column label")

    def test_unlabelled_columns_are_gone_from_this_table(self):
        t4 = S.extract_docx_tables(DOCX)["tables"][3]
        heads = [str(h) for h in (t4.get("headers") or [])]
        unlabelled = [h for h in heads if "unlabelled column" in h]
        assert len(unlabelled) <= 1, (
            f"only the stub may be unnamed, got {unlabelled}")


class TestASpanningHeaderLabelReachesEveryColumnItCovers:
    """Blanking a merge is right for the BODY and wrong for the HEADER.

    `extract_docx_tables` blanks a merged cell's continuations so one
    measurement is not counted several times -- `jats._expand` calls that the
    anchor rule, and without it a `3.7 (0.30)` spanning four columns becomes
    four identical pairs and `detect_duplication` invents a finding.

    But `_expand` applies that rule to BODY cells only. Header rows repeat
    their text across every covered cell, because a composite column label
    REQUIRES it. The .docx reader implemented only the body half, so on
    Table S.4:

        row 1  '' | Within-Person |   |   | Between-Person |   |
        row 2  '' | b (SE) | p | beta | b (SE) | p | beta

    flattened to `Within-Person | b (SE)`, `p`, `beta`,
    `Between-Person | b (SE)`, `p`, `beta` -- TWO columns named `p` and two
    named `beta`, indistinguishable. That is the exact failure `_header_depth`
    exists to prevent: a value drawn from one and an n from another are
    indistinguishable afterwards, and a check on that pair calls an honest
    paper impossible.
    """

    def test_every_column_label_is_distinct(self):
        t = S.extract_docx_tables(DOCX)["tables"][3]
        heads = [h for h in (t.get("headers") or []) if str(h).strip()]
        assert len(heads) == len(set(heads)), (
            f"duplicate column labels: {heads}")

    def test_the_group_reaches_the_inner_columns(self):
        t = S.extract_docx_tables(DOCX)["tables"][3]
        heads = [str(h) for h in (t.get("headers") or [])]
        for want in ("Within-Person | p", "Between-Person | p",
                     "Within-Person | β", "Between-Person | β"):
            assert want in heads, f"{want!r} missing from {heads}"

    def test_the_innermost_level_still_names_the_role(self):
        """The p-column rule reads the level nearest the data; propagating an
        outer level must not break it."""
        from metascience_agent import values as V
        assert V.role_from_column("Within-Person | p", 0.03) == "p"


class TestTheDoubleFinishMustNotBeFixed:
    """Forwarding docling's header depth into the second `_finish` EATS DATA.

    `supplements_read.extract_pdf_tables` re-`_finish`es a grid that
    `docling_tables` has already finished, and takes the one-row default. That
    looks like a dropped field and I recorded it as one on 2026-08-20, calling
    it "the worst kind of bug to leave armed" and proposing that the field be
    forwarded.

    Measuring on 2026-08-21 showed both halves were wrong. `_finish` returns
    `data` as `[flattened_header] + body`, so the composite labels are already
    row 0 of the grid handed over and the second pass adopts them: labels and
    cells survive intact. Passing docling's depth instead makes the second pass
    consume rows of an ALREADY-FLATTENED grid as header, deleting a real
    measurement row per affected table.

    This test exists because the wrong advice was published in a commit message
    before it was checked, and a later reader acting on it would lose data
    silently.
    """

    def test_forwarding_the_depth_would_delete_a_body_row(self):
        grid = [
            ["Variable | Prenatal", "Comparison | Mean", "Nurse | Mean"],
            ["Birth weight", "3252", "3310"],
            ["Gestational age", "39.1", "39.4"],
        ]
        keep = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf")
        eaten = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf",
                          header_rows=2)
        assert keep["n_rows"] == 2
        assert eaten["n_rows"] == 1, (
            "forwarding a depth into an already-flattened grid consumes a "
            "measurement row -- this is why the double _finish stays")

    def test_the_composite_labels_survive_the_default(self):
        grid = [
            ["Variable | Prenatal", "Comparison | Mean", "Nurse | Mean"],
            ["Birth weight", "3252", "3310"],
        ]
        out = S._finish([r[:] for r in grid], 1, "T", "", "x", "pdf")
        assert out["headers"][1] == "Comparison | Mean", (
            "docling already flattened the header into row 0; nothing is lost")

    def test_the_warning_against_fixing_it_stays_written_down(self):
        import inspect
        src = inspect.getsource(S)
        assert "DO NOT" in src and "DESTROY DATA" in src, (
            "the correction must stay: the wrong advice is in a pushed commit")
