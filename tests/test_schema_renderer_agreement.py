"""What the pipeline writes must be what its own schemas allow.

`tests/test_tool_exposure.py` exists because a tool registered in two of three
places is unusable while every other test passes. The schemas have the same
shape of hole and had no equivalent guard.

MEASURED when this was written: `agent._checkable_census` writes
`rows_checked_by_batch_tools` and `batch_tools` into
`coverage_summary.checkable`, `report_render` reads both to build the coverage
sentence -- and `checkable` is declared `additionalProperties: false` without
either one. A report carrying them is rejected by
`prompts/schema/report.schema.json`:

    Additional properties are not allowed
    ('batch_tools', 'rows_checked_by_batch_tools' were unexpected)

Nothing noticed, because `--json-schema` constrains what the MODEL emits and
these keys are added by Python afterwards. The schema was documentation that
disagreed with the program.
"""
import json
import re
from pathlib import Path

import pytest

from metascience_agent.core import prompts

SRC = Path("src/metascience_agent")



try:  # the separately distributed image package; absent -> its modules are not scanned
    IMAGE_SRC = __import__("pathlib").Path(__import__("metascience_observatory_image_analysis").__file__).parent
except ImportError:
    IMAGE_SRC = None
def _closed_objects(node, path="$"):
    """Every `additionalProperties: false` object in a schema, with its path."""
    if isinstance(node, dict):
        if node.get("additionalProperties") is False and "properties" in node:
            yield path, set(node["properties"])
        for k, v in node.items():
            yield from _closed_objects(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _closed_objects(v, f"{path}[{i}]")


class TestFieldsTheRendererShowsAreNamedInASchema:
    def test_the_corresponding_author_line_rests_on_declared_fields(self):
        """The report renders a "Corresponding author" line above the author
        questions. Both fields reached the schema only through
        `paper_metadata`'s `additionalProperties: true`, so a reader of the
        contract could not tell they existed -- and `extraction/jats.py`, which
        is what actually writes them, had no declaration to write against."""
        pm = prompts.findings_schema_v2()["properties"]["paper_metadata"]["properties"]
        assert "corresponding_author" in pm
        assert "corresponding_email" in pm
        for f in ("corresponding_author", "corresponding_email"):
            assert "EXTRACTOR-WRITTEN" in pm[f]["description"], (
                "a model told to produce this would invent it")


class TestASchemaEnumDescribesAValueThatCanOccur:
    @pytest.mark.usefixtures("image_package")
    def test_the_image_track_does_not_advertise_a_refusal_it_cannot_emit(self):
        """`image_track.schema.json` lists `truncated_by_budget` as a
        `refusal_subtype`; `run_track` never emits it. An enum value nothing
        can produce is a promise to a reader that the pipeline distinguishes a
        case it does not."""
        schema = json.loads(
            (IMAGE_SRC / "prompts/schema/image_track.schema.json").read_text())
        declared = set(schema["properties"]["status"]["properties"]
                       ["refusal_subtype"].get("enum") or [])
        src = (IMAGE_SRC / "image_forensics" / "image_track.py").read_text(encoding="utf-8")
        # `_status(ran, refusal_subtype, detail, ...)` -- positional, so match
        # the string literal that follows the boolean.
        emitted = set(re.findall(
            r'_status\(\s*(?:True|False)\s*,\s*"([a-z_]+)"', src, re.S))
        missing = {v for v in declared if v} - emitted
        assert not missing, (
            f"{sorted(missing)} is declared as a refusal_subtype and never "
            f"emitted; either emit it or drop it from the enum")


class TestTruncationAnnouncesItself:
    """CLAUDE.md: "A budget-truncated run must announce itself." The paid
    stages do, via `_stage_meta`'s `truncated_by_budget`. The image track did
    not: truncation existed only as a caveat string inside `result`, which the
    editorial stage never sees, because `findings_rows` are summary-only by
    contract. A half-harvested paper reached stage 2 looking exactly like a
    fully harvested one.
    """

    @staticmethod
    def _run(truncated):
        import pathlib
        from unittest import mock
        import metascience_observatory_image_analysis.image_forensics.image_track as IT
        import metascience_observatory_image_analysis.image_forensics.image_analysis as IA
        fake = {"success": True, "severity": "consistent", "n_panels": 200,
                "n_eligible": 12, "duplicate_groups": [],
                "tiers_run": ["identical_stream"], "tiers_not_run": [],
                "documents": [{"path": "main.pdf", "role": "main",
                               "n_panels": 200, "n_eligible": 12,
                               "truncated": truncated}]}
        with mock.patch.object(IA, "analyze_paper_images", return_value=fake), \
             mock.patch("metascience_observatory_image_analysis.image_forensics.panels.panel_engine_status",
                        return_value={"available": True}), \
             mock.patch.object(IT, "_find_pdfs",
                               return_value=(pathlib.Path("main.pdf"), [], True)):
            return IT.run_track(".")

    @pytest.mark.usefixtures("image_package")
    def test_a_truncated_harvest_says_so_in_the_status(self):
        st = self._run(True)["status"]
        assert st["truncated_by_budget"] is True
        assert "TRUNCATED" in st["detail"]

    @pytest.mark.usefixtures("image_package")
    def test_a_complete_harvest_says_so_too(self):
        """Explicit False, not an absent key: "we did not truncate" and "nobody
        recorded whether we truncated" are different facts."""
        st = self._run(False)["status"]
        assert st["truncated_by_budget"] is False
        assert "TRUNCATED" not in st["detail"]

    @pytest.mark.usefixtures("image_package")
    def test_truncation_is_not_recorded_as_a_refusal(self):
        """It was declared as a `refusal_subtype` and could never have been
        emitted as one: those accompany `ran: false`, and a truncated harvest
        ran, on part of the paper."""
        st = self._run(True)["status"]
        assert st["ran"] is True
        assert st["refusal_subtype"] is None

    @pytest.mark.usefixtures("image_package")
    def test_the_status_validates_against_the_track_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        schema = json.loads(
            (IMAGE_SRC / "prompts/schema/image_track.schema.json").read_text())
        jsonschema.validate(self._run(True), schema)
