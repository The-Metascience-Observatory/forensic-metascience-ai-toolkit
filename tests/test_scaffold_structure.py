"""The frozen structural account: what it refuses, and what it costs to change.

Nothing here calls a model, and the first test proves it the hard way -- it
makes the pass runner raise, and asserts a run with a structure on disk still
finishes. That is the whole claim of the design (D43): given ONE structural
vocabulary the downstream passes are close to deterministic, so the paper is
decomposed once and every later pass SELECTS from that decomposition.

The six invariants, one class each:

1. a structure on disk means zero pass-1/2 calls;
2. a foreign id is nulled and counted, never accepted, and the text it was read
   as survives;
3. artifacts recording two different structures cannot be bound into one account;
4. a frozen version is never rewritten, and `--redecompose` writes n+1 with n
   still on disk;
5. a changed served document is reported as `stale_document` with both hashes,
   and nothing is re-decomposed or proceeds silently;
6. the structural adjudication gates: an addition needs a located quote, a
   removal is refused while values bind, and a kind the text decided is not
   overruled -- the disagreement is recorded as a conflict.
"""

from __future__ import annotations

import copy
import json

import pytest

from metascience_agent.scaffold import bind, document, passes, structure
from metascience_agent.scaffold.__main__ import main

from tests.test_scaffold import P1, P2, P3, TEXT, _doc

# --------------------------------------------------------------------------
# A paper on disk small enough to build a document from, and the passes' output
# for it, taken from the deterministic-half fixtures next door.
# --------------------------------------------------------------------------

XML = """<?xml version="1.0"?>
<article><front><article-meta>
<title-group><article-title>A tiny paper</article-title></title-group>
<pub-date><year>2026</year></pub-date>
</article-meta></front>
<body><sec><title>Results</title>
<p>The mean score was 4.01 in the treated group (n = 12).</p>
<p>Attrition was 12% and the model converged (p = .03).</p>
</sec></body>
<back><ref-list><ref><mixed-citation>Smith J (2011). A paper. J Things 12: 100.</mixed-citation></ref></ref-list></back>
</article>
"""


def _paper(tmp_path, xml: str = XML):
    d = tmp_path / "paper"
    d.mkdir(parents=True, exist_ok=True)
    (d / "paper.xml").write_text(xml, encoding="utf-8")
    return d


def _built(tmp_path, xml: str = XML):
    """(paper dir, scaffold dir, document) for a paper that exists on disk."""
    d = _paper(tmp_path, xml)
    out = d / "scaffold"
    out.mkdir(exist_ok=True)
    return d, out, document.build(d)


def _boom(*a, **k):
    raise AssertionError("a pass was run: with a structure on disk, passes 1 and 2 "
                         "must not be called at all")


def _structure(doc=None, p1=None, p2=None, **kw):
    return structure.build(p1 or P1, p2 or P2, doc if doc is not None else _doc(), **kw)


# --------------------------------------------------------------------------
# Invariant 1: a structure on disk means no pass-1/2 call
# --------------------------------------------------------------------------


class TestAStructureOnDiskIsNotReDecomposed:

    def test_the_run_finishes_with_the_pass_runner_wired_to_explode(self, tmp_path, monkeypatch):
        d, out, doc = _built(tmp_path)
        structure.create(P1, P2, doc, out, freeze_draft=True)
        (out / "pass3.json").write_text(json.dumps(P3), encoding="utf-8")
        monkeypatch.setattr(passes, "run_pass", _boom)
        assert main([str(d), "--no-llm", "--no-recon", "--skip-residual"]) == 0
        account = json.loads((out / "account.json").read_text(encoding="utf-8"))
        st = account["structure"]
        assert st["version"] == 1 and st["status"] == "frozen"
        assert st["ids"]["variables"] == len(P2["variables"])
        assert not st["adjudicated"]
        assert "UNADJUDICATED" in (out / "account.md").read_text(encoding="utf-8")

    def test_the_detector_fires_when_there_is_no_structure(self, tmp_path, monkeypatch):
        """The positive control. Without the file the driver DOES reach for the
        pass runner, so the test above is measuring the structure and not a
        pass that was never going to run."""
        d, out, _doc_ = _built(tmp_path)
        monkeypatch.setattr(passes, "run_pass", _boom)
        with pytest.raises(AssertionError, match="passes 1 and 2"):
            main([str(d), "--no-recon", "--skip-residual"])

    def test_the_vocabulary_the_account_uses_is_the_files(self, tmp_path):
        d, out, doc = _built(tmp_path)
        st = structure.create(P1, P2, doc, out)
        assert structure.id_counts(st) == {
            "studies": 1, "groups": 2, "phases": 1,
            "variables": len(P2["variables"]),
            "levels": 2, "tests": 0}
        assert structure.load(out)["sha256"] == structure.content_sha256(st)


# --------------------------------------------------------------------------
# Invariant 2: a foreign id is nulled, counted, and kept as text
# --------------------------------------------------------------------------


class TestAForeignIdIsNeverAccepted:

    def _p3_with_foreign_ids(self):
        p3 = copy.deepcopy(P3)
        p3["table_readings"][0]["row_map"][0]["variable_id"] = "var:invented"
        p3["comparisons"][0]["contrast"]["group_ids"] = ["grp:veh", "grp:ghost"]
        p3["figure_panels"][0]["study_id"] = "study:never_declared"
        return p3

    def test_it_is_nulled_counted_and_the_text_survives(self):
        p3 = self._p3_with_foreign_ids()
        got = structure.close_vocabulary(structure.id_sets(_structure()), p3)
        assert got["unbound_foreign_id"] == 3
        assert got["by_field"] == {"group_ids": 1, "study_id": 1, "variable_id": 1}
        row = p3["table_readings"][0]["row_map"][0]
        assert row["variable_id"] is None and row["variable_id_as_read"] == "var:invented"
        cmp_ = p3["comparisons"][0]["contrast"]
        assert cmp_["group_ids"] == ["grp:veh"]
        assert cmp_["group_ids_as_read"] == ["grp:veh", "grp:ghost"]
        assert p3["figure_panels"][0]["study_id_as_read"] == "study:never_declared"

    def test_a_declared_id_is_left_exactly_as_it_was(self):
        p3 = copy.deepcopy(P3)
        before = json.dumps(p3, sort_keys=True)
        got = structure.close_vocabulary(structure.id_sets(_structure()), p3)
        assert got["unbound_foreign_id"] == 0
        assert json.dumps(p3, sort_keys=True) == before

    def test_a_table_entry_keeps_its_words_and_loses_the_id(self):
        doc = _doc()
        t = doc["tables"][0]
        t["reconstruction"] = {"status": "verified"}
        t["cells"][0]["entries"] = [{"variable": "Weight", "level": None, "group": "Veh",
                                     "statistic": "mean", "value": "23.0",
                                     "variable_id": "var:ghost", "level_id": None,
                                     "group_id": None}]
        account = bind.assemble(doc, P1, P2, copy.deepcopy(P3), structure=_structure())
        cv = account["structure"]["closed_vocabulary"]
        assert cv["unbound_foreign_id"] == 1 and cv["by_field"] == {"variable_id": 1}
        v = next(v for v in account["values"] if v.get("variable_as_read") == "Weight")
        assert v["variable_id_as_read"] == "var:ghost"
        # The name join is still allowed to bind the WORDS -- what is refused is
        # the id the reading composed, not the reading.
        assert v["variable_id"] == "var:weight" and v["id_check"] == "join"

    def test_the_count_survives_a_second_assembly_of_the_same_artifacts(self):
        """The account is assembled once per residual iteration. A count that
        fell to zero the second time round would hide the honest number in the
        one artifact a reader sees."""
        p3 = self._p3_with_foreign_ids()
        sets = structure.id_sets(_structure())
        first = structure.close_vocabulary(sets, p3)["unbound_foreign_id"]
        assert structure.close_vocabulary(sets, p3)["unbound_foreign_id"] == first == 3

    def test_the_account_says_so_in_section_1(self):
        from metascience_agent.scaffold import render
        account = bind.assemble(_doc(), P1, P2, self._p3_with_foreign_ids(),
                                structure=_structure())
        md = render.render(account)
        assert "## 1. Structure" in md
        assert "**3 id(s)**" in md and "var:invented" in md
        assert any("closed vocabulary" in p for p in account["problems"])


# --------------------------------------------------------------------------
# Invariant 3: two structures cannot be bound into one account
# --------------------------------------------------------------------------


class TestArtifactsOfTwoStructuresAreNotOneAccount:

    def test_two_different_stamps_are_refused(self):
        st = _structure()
        with pytest.raises(structure.StructureMismatch, match="different structures"):
            bind.assemble(_doc(), P1, P2, copy.deepcopy(P3), structure=st,
                          artifact_stamps={"pass3.meta.json": "a" * 64,
                                           "table_1.recon.meta.json": "b" * 64})

    def test_one_stamp_that_is_not_this_structure_is_refused(self):
        st = _structure()
        with pytest.raises(structure.StructureMismatch):
            bind.assemble(_doc(), P1, P2, copy.deepcopy(P3), structure=st,
                          artifact_stamps={"pass3.meta.json": "c" * 64})

    def test_unstamped_artifacts_are_not_a_mismatch(self):
        """An artifact made before the stamp existed says nothing about which
        structure it was read against, which is a different fact from being read
        against a different one."""
        st = _structure()
        sha = structure.content_sha256(st)
        account = bind.assemble(_doc(), P1, P2, copy.deepcopy(P3), structure=st,
                                artifact_stamps={"pass3.meta.json": None,
                                                 "table_1.recon.meta.json": sha})
        assert account["structure"]["sha256"] == sha

    def test_the_stamp_is_written_onto_every_artifact_meta(self, tmp_path):
        d, out, doc = _built(tmp_path)
        st = structure.create(P1, P2, doc, out)
        stamp = structure.stamp(st)
        assert stamp == {"structure_version": 1, "structure_sha256": structure.content_sha256(st)}
        (out / "pass3.meta.json").write_text(json.dumps(stamp), encoding="utf-8")
        assert structure.artifact_stamps(out) == {"pass3.meta.json": stamp["structure_sha256"]}


# --------------------------------------------------------------------------
# Invariant 4: a frozen version is never rewritten
# --------------------------------------------------------------------------


class TestAFrozenVersionIsNeverRewritten:

    def _second_decomposition(self):
        p2 = copy.deepcopy(P2)
        p2["variables"] = (p2["variables"][:2]
                           + [{**p2["variables"][2], "id": "var:whiskers_renamed"}]
                           + p2["variables"][3:])
        return p2

    def test_saving_different_content_over_a_frozen_version_is_refused(self, tmp_path):
        d, out, doc = _built(tmp_path)
        st = structure.create(P1, P2, doc, out, freeze_draft=True)
        changed = {**st, "pass2": self._second_decomposition()}
        with pytest.raises(structure.StructureFrozen, match="frozen"):
            structure.save(changed, out)
        assert structure.load(out)["sha256"] == structure.content_sha256(st)

    def test_freezing_twice_is_refused_so_frozen_at_stays_true(self, tmp_path):
        d, out, doc = _built(tmp_path)
        st = structure.create(P1, P2, doc, out, freeze_draft=True)
        with pytest.raises(structure.StructureFrozen, match="already frozen"):
            structure.freeze(st, out)

    def test_redecompose_writes_n_plus_1_and_leaves_n_on_disk(self, tmp_path):
        d, out, doc = _built(tmp_path)
        v1 = structure.create(P1, P2, doc, out, freeze_draft=True)
        v2, diff = structure.redecompose(v1, P1, self._second_decomposition(), doc, out)
        assert v2["version"] == 2 and v2["status"] == "draft"
        assert structure.load(out)["version"] == 2
        assert structure.versions_on_disk(out) == [1, 2]
        kept = structure.load_version(out, 1)
        assert kept["status"] == "frozen" and kept["sha256"] == structure.content_sha256(v1)
        assert diff["jaccard"]["variables"] == 0.6 and diff["jaccard"]["studies"] == 1.0
        assert diff["counts"]["variables"] == {"from": 4, "to": 4}
        assert "v1 -> v2" in structure.format_diff(diff)

    def test_freezing_a_draft_does_not_move_the_vocabulary(self, tmp_path):
        """Freezing changes the status and nothing a reading selected from, so
        an artifact read against the draft is still an artifact read against
        this vocabulary."""
        d, out, doc = _built(tmp_path)
        draft = structure.create(P1, P2, doc, out)
        frozen = structure.freeze(draft, out)
        assert frozen["status"] == "frozen" and frozen["frozen_at"]
        assert structure.content_sha256(frozen) == structure.content_sha256(draft)


# --------------------------------------------------------------------------
# Invariant 5: a changed document is said, never silently re-read
# --------------------------------------------------------------------------


class TestAChangedDocumentIsSaidNotReDecomposed:

    def _moved(self, doc):
        moved = copy.deepcopy(doc)
        moved["source"] = {**doc["source"], "text_sha256": "f" * 64,
                           "n_chars": (doc["source"].get("n_chars") or 0) + 900,
                           "n_chars_article": doc["source"].get("n_chars_article")}
        moved["supplement_spans"] = [{"file": "supp.docx", "n_chars": 900}]
        return moved

    def test_the_account_carries_both_hashes_and_the_chars_by_source(self):
        doc = _doc()
        doc["source"] = {"text_sha256": "a" * 64, "n_chars": 100, "n_chars_article": 100}
        st = _structure(doc)
        account = bind.assemble(self._moved(doc), P1, P2, copy.deepcopy(P3), structure=st)
        stale = account["structure"]["stale_document"]
        assert account["structure"]["document_matches"] is False
        assert stale["document_sha256_in_structure"] == "a" * 64
        assert stale["document_sha256_now"] == "f" * 64
        assert stale["changed_by_source"]["total"] == [100, 1000]
        assert stale["changed_by_source"]["supp.docx"] == [None, 900]
        assert any(p.startswith("stale document") for p in account["problems"])

    def test_nothing_is_re_decomposed_and_the_ids_are_the_earlier_documents(self):
        doc = _doc()
        doc["source"] = {"text_sha256": "a" * 64, "n_chars": 100, "n_chars_article": 100}
        st = _structure(doc)
        account = bind.assemble(self._moved(doc), P1, P2, copy.deepcopy(P3), structure=st)
        assert account["structure"]["ids"] == structure.id_counts(st)
        assert account["structure"]["version"] == 1

    def test_a_run_over_a_changed_paper_still_runs_no_pass(self, tmp_path, monkeypatch):
        d, out, doc = _built(tmp_path)
        structure.create(P1, P2, doc, out, freeze_draft=True)
        (out / "pass3.json").write_text(json.dumps(P3), encoding="utf-8")
        (d / "paper.xml").write_text(XML.replace("Attrition was 12%",
                                                 "Attrition was 12% of the sample"),
                                     encoding="utf-8")
        monkeypatch.setattr(passes, "run_pass", _boom)
        assert main([str(d), "--no-llm", "--no-recon", "--skip-residual"]) == 0
        account = json.loads((out / "account.json").read_text(encoding="utf-8"))
        assert account["structure"]["stale_document"]
        assert "STALE DOCUMENT" in (out / "account.md").read_text(encoding="utf-8")

    def test_the_same_document_is_not_stale(self):
        doc = _doc()
        doc["source"] = {"text_sha256": "a" * 64, "n_chars": 100}
        assert structure.stale_document(_structure(doc), doc) is None


# --------------------------------------------------------------------------
# Invariant 6: the structural adjudication gates
# --------------------------------------------------------------------------


def _disagreement(**kw) -> dict:
    d = {"field_class": "variables", "item": "what kind var:weight is",
         "reading_a": "continuous", "reading_b": "integer_score",
         "paper_supports": "b", "evidence": "the table header says so",
         "evidence_quote": None, "evidence_anchor": {"kind": "table_header", "table_id": "table:1"},
         "target_account": "a", "target_ids": ["var:weight"],
         "correction": {"field": "kind", "to": "integer_score"}}
    d.update(kw)
    return d


class TestTheStructuralAdjudicationGates:

    def test_an_added_variable_without_a_located_quote_is_refused(self):
        st = _structure()
        edit = {"op": "add_variable", "id": "var:latency", "parent_variable_id": None,
                "label": "Latency", "role": "measured_outcome", "kind": "continuous",
                "quote": "the paper surely measured latency", "why": "it is an outcome"}
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
            bound_variable_ids=set())
        assert audit["n_applied"] == 0
        assert audit["skipped"][0]["why"].startswith("an addition needs a verbatim quote")
        assert "var:latency" not in structure.id_sets(after)["variables"]

    def test_an_added_variable_with_a_located_quote_is_applied(self):
        """The positive control: the gate is refusing the missing quote and not
        refusing every addition."""
        st = _structure()
        edit = {"op": "add_variable", "id": "var:latency", "parent_variable_id": None,
                "label": "Latency", "role": "measured_outcome", "kind": "continuous",
                "quote": "Mice were injected with vehicle or drug 20 min before training",
                "why": "it is an outcome"}
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
            bound_variable_ids=set())
        assert audit["n_applied"] == 1 and audit["n_skipped"] == 0
        assert "var:latency" in structure.id_sets(after)["variables"]
        added = next(v for v in after["pass2"]["variables"] if v["id"] == "var:latency")
        assert added["bounds"]["source"] == "not_stated" and added["added_by_adjudication"]
        assert after["version"] == st["version"] + 1 and after["status"] == "adjudicated"
        assert st["version"] == 1, "the version it replaces is not touched"

    def test_a_removal_is_refused_while_a_value_binds(self):
        st = _structure()
        edit = {"op": "remove_variable", "id": "var:weight", "parent_variable_id": None,
                "label": None, "role": None, "kind": None, "quote": None,
                "why": "duplicated by var:pole"}
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
            bound_variable_ids={"var:weight"})
        assert audit["n_applied"] == 0
        assert "values bind to this variable" in audit["skipped"][0]["why"]
        assert "var:weight" in structure.id_sets(after)["variables"]

    def test_a_removal_with_nothing_bound_is_applied_and_an_unknown_is_refused(self):
        st = _structure()
        edit = {"op": "remove_variable", "id": "var:weight", "parent_variable_id": None,
                "label": None, "role": None, "kind": None, "quote": None,
                "why": "the paper does not measure it"}
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
            bound_variable_ids=set())
        assert audit["n_applied"] == 1
        assert "var:weight" not in structure.id_sets(after)["variables"]
        # Not knowing what binds is not knowing that nothing does.
        _, audit2 = structure.apply_structural_adjudication(
            st, {"disagreements": [], "structural_edits": [edit]}, TEXT,
            bound_variable_ids=None)
        assert audit2["n_applied"] == 0 and "unknown" in audit2["skipped"][0]["why"]

    def test_a_header_never_overrules_a_kind_the_text_decided(self):
        st = _structure()
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [_disagreement()], "structural_edits": []}, TEXT,
            bound_variable_ids=set())
        assert audit["n_applied"] == 0
        var = next(v for v in after["pass2"]["variables"] if v["id"] == "var:weight")
        assert var["kind"] == "continuous", "the kind is not changed"

    def test_a_kind_the_evidence_does_not_reach_is_recorded_as_a_conflict(self):
        """G11's own mechanism: where the evidence is of the right KIND for a
        variable (the Methods) but is not located in the paper, the two readings
        are recorded as a disagreement and neither is applied."""
        st = _structure()
        d = _disagreement(evidence_anchor={"kind": "methods_definition", "table_id": None})
        after, audit = structure.apply_structural_adjudication(
            st, {"disagreements": [d], "structural_edits": []}, TEXT,
            bound_variable_ids=set())
        assert audit["n_applied"] == 0 and audit["n_conflicts"] == 1
        assert audit["conflicts"][0]["variable_id"] == "var:weight"
        assert audit["conflicts"][0]["printed_kind"] == "integer_score"
        assert audit["conflicts"][0]["text_kind"] == "continuous"
        var = next(v for v in after["pass2"]["variables"] if v["id"] == "var:weight")
        assert var["kind"] == "continuous" and var["kind_conflict"]

    def test_the_audit_is_append_only_and_the_account_reports_it(self, tmp_path):
        d, out, doc = _built(tmp_path)
        st = structure.create(P1, P2, doc, out)
        once, _ = structure.apply_structural_adjudication(
            st, {"disagreements": [_disagreement(evidence_anchor={"kind": "methods_definition",
                                                                  "table_id": None})],
                 "structural_edits": []}, TEXT, bound_variable_ids=set(), out_dir=out)
        twice, _ = structure.apply_structural_adjudication(
            once, {"disagreements": [], "structural_edits": []}, TEXT,
            bound_variable_ids=set(), out_dir=out)
        assert len(twice["adjudication"]) == 2 and twice["version"] == 3
        assert structure.adjudication_counts(twice)["conflicts"] == 1
        account = bind.assemble(_doc(), P1, P2, copy.deepcopy(P3), structure=twice)
        from metascience_agent.scaffold import render
        md = render.render(account)
        assert "status `adjudicated`" in md and "2 round(s)" in md
        assert "UNADJUDICATED" not in md

    def test_the_driver_runs_the_paid_pass_only_on_the_flag_and_applies_it(self, tmp_path,
                                                                          monkeypatch):
        """The consumer is wired, and it is wired to a flag. A gated consumer
        nothing calls is the defect class this repo keeps finding (CLAUDE.md
        8c/8e): present, imported, and never reached."""
        d, out, doc = _built(tmp_path)
        structure.create(P1, P2, doc, out)
        (out / "pass3.json").write_text(json.dumps(P3), encoding="utf-8")
        served = {}

        def _canned(name, prompt, out_dir, **kw):
            served[name] = prompt
            data = {"overall": "one variable is missing", "disagreements": [],
                    "structural_edits": [{
                        "op": "add_variable", "id": "var:latency", "parent_variable_id": None,
                        "label": "Latency", "role": "measured_outcome", "kind": "continuous",
                        "quote": "The mean score was 4.01 in the treated group",
                        "why": "the Results report it"}]}
            (out_dir / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
            return {"data": data, "problems": [], "meta": {"cost_usd": 0.0, "elapsed_s": 0.0}}

        monkeypatch.setattr(passes, "run_pass", _canned)
        with pytest.raises(SystemExit, match="paid pass"):
            main([str(d), "--no-llm", "--no-recon", "--skip-residual",
                  "--adjudicate-structure"])
        assert main([str(d), "--resume", "--no-recon", "--skip-residual",
                     "--adjudicate-structure"]) == 0
        p = served["structure_review"]
        assert "STRUCTURE" in p and "are the studies separated correctly" in p
        # The task tells the reader to copy `target_ids` out of the ID INDEX, so
        # the index has to be there: an instruction pointing at a fence that is
        # not served is a false instruction.
        assert "ID INDEX (copy target_ids from here)" in p
        assert "var:weight" in p.split("ID INDEX (copy target_ids from here)")[1]
        st = structure.load(out)
        assert st["version"] == 2 and st["status"] == "adjudicated"
        assert "var:latency" in structure.id_sets(st)["variables"]
        assert structure.versions_on_disk(out) == [1, 2]
        account = json.loads((out / "account.json").read_text(encoding="utf-8"))
        assert account["structure"]["adjudicated"] is True
        assert account["structure"]["adjudication"]["applied"] == 1

    def test_the_schema_the_adjudicator_answers_in_is_valid_and_closed(self):
        import jsonschema
        sch = structure.structure_adjudication_schema()
        jsonschema.Draft202012Validator.check_schema(sch)
        assert "structural_edits" in sch["required"]
        good = {"overall": "x", "disagreements": [],
                "structural_edits": [{"op": "add_variable", "id": "var:x",
                                      "parent_variable_id": None, "label": "X",
                                      "role": "measured_outcome", "kind": "continuous",
                                      "quote": "the paper says so here", "why": "it is measured"}]}
        jsonschema.Draft202012Validator(sch).validate(good)
        bad = {**good, "structural_edits": [{**good["structural_edits"][0],
                                             "op": "rename_variable"}]}
        assert list(jsonschema.Draft202012Validator(sch).iter_errors(bad))
