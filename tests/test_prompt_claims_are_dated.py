"""A measured claim in the model's instructions must say WHEN it was measured.

This repository has now been bitten twice by the same defect, and neither time
was the number wrong when it was written:

  1. `specificity 0.846 / 0.0000` sat in the README and was quoted back by five
     source files, the CLI and the agent itself -- injecting an unsourced figure
     into the model's own instructions. Purged in e6a4c23.

  2. The stage-2 verdict calibration asserted "`trustworthy` and `untrustworthy`
     have never once been emitted", measured at 14 of 14 questionable. By
     2026-08-13 the archive read 24 questionable / 3 untrustworthy / 0
     trustworthy -- `untrustworthy` HAD been emitted, once on a paper later
     retracted. So the text told the model that the calibration it introduces had
     failed, when it had worked, which hands the model a reason to avoid a
     verdict and collapses the field back to one value. Corrected in 314813c.

A date does not make a claim true and this test does not check arithmetic --
that is not decidable in general. What it does is make STALENESS VISIBLE. An
undated measurement reads as timeless fact forever; "MEASURED 2026-08-06" tells
the next reader exactly what to re-run, and tells the author that the number has
a shelf life.

Dates were recovered from `git blame`, not invented: each is the day the claim
was written.

THE RULE THIS TEST DOES NOT ENFORCE, AND SHOULD BE READ BESIDE IT. Requiring a
DATE on a measured claim silently blesses the claim's presence, and by
2026-08-13 the prompts held eight of them. Greg, on finding a transcription base
rate in the stage-1 prompt: "why would that figure be in the stage 1 prompt?
that seems irrelevant to the operation of the agent."

He was right, and about more than one number. Five of the eight justified a
design decision to a HUMAN READER of the prompt -- they were commit messages in
the wrong file -- and two were worse than inert:

    "86.7% of unrecorded figures turn out to be transcriptions"
        hands the model a prior that ITS OWN unrecorded numbers are fine, in the
        section whose whole purpose is to make it record provenance.
    "over 357 archived titles, you have never once broken this one"
        tells the model it may relax a rule. Same shape as defect 2 above,
        which this very docstring describes.

So the standing question for a measured claim in a prompt is not "is it dated?"
but WHAT WOULD THE MODEL DO DIFFERENTLY IF IT WERE 40% INSTEAD? If the answer is
nothing, the claim belongs in the code comment beside the mechanism, where the
human who needs the justification will find it. Three survive that test and are
kept: each is a concrete failure the instruction exists to prevent (figure PNGs
sitting unopened, 125 collapsed passes the editorial stage never saw), not a
base rate about how often the model gets it right.
"""

import re
from pathlib import Path

import pytest

from metascience_agent import verdicts as _verdicts

SCHEMAS = Path(__file__).resolve().parents[1] / "src/metascience_agent/schema"

#: An ASSERTED measurement, in this repo's own convention: the word used as a
#: claim, not as an ordinary verb ("a value measured off a bar").
#: NOTE the optional date between the word and its preposition. Stamping the
#: claims broke the first version of this pattern -- "Measured on a real corpus"
#: became "Measured 2026-08-08 on a real corpus" and stopped matching, so the
#: detector silently found 7 claims where there are 11. A guard that quietly
#: stops seeing the thing it guards is worse than no guard.
CLAIM = re.compile(r"\bMEASURED\b(?!\s+(?:off|value|values))"
                   r"|\bMeasured\b(?:\s+20\d\d-\d\d-\d\d,?)?\s+(?:on|across|over|in|at)\b")
DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def _claims():
    from metascience_observatory_image_analysis.prompts import PROMPTS_DIR
    from metascience_agent.core.prompts import prompt_files
    for f in sorted({*SCHEMAS.rglob("*"), *PROMPTS_DIR.rglob("*"), *prompt_files()}):
        if f.is_dir() or f.suffix not in (".md", ".json"):
            continue
        lines = f.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines, 1):
            if CLAIM.search(line):
                # The date may sit in the sentence around it, not the same line.
                ctx = "\n".join(lines[max(0, i - 3):i + 3])
                yield f, i, line.strip(), bool(DATE.search(ctx))


class TestEveryAssertedMeasurementCarriesItsDate:
    @pytest.mark.usefixtures("image_package")
    def test_the_prompts_contain_asserted_measurements_at_all(self):
        """Guard against the regex silently matching nothing, which would make
        every assertion below vacuously true."""
        assert sum(1 for _ in _claims()) >= 10

    @pytest.mark.usefixtures("image_package")
    def test_none_is_undated(self):
        undated = [f"{f.name}:{i}  {s[:90]}" for f, i, s, dated in _claims() if not dated]
        assert not undated, (
            "a measured claim in the model's instructions must carry the date it "
            "was measured, so a later reader can tell a current number from a "
            "stale one:\n  " + "\n  ".join(undated))


class TestEveryRequiredFieldIsExplainedSomewhere:
    """A field a schema REQUIRES but no prompt names is an obligation the model
    was never told about -- the same defect as `declaration_template` (a channel
    with no instruction) and `triage` (an instruction with no channel), in its
    third costume.

    Swept 2026-08-13: 4 required fields were unnamed, deduping to 3. Two --
    `paper_id` and `schema_version` -- are written by code (`agent.py:1304`), not
    by the model, so they are exempt. The third was real:
    `anatomy/hypotheses[]/status`, a REQUIRED four-value taxonomy that decides
    whether multiplicity correction applies, and which no prompt explained.

    Over 98 archived hypotheses the model emitted 48 exploratory, 45
    confirmatory, 5 unstated -- and `preregistered_confirmatory` NOT ONCE. It was
    guessing at a vocabulary nobody had given it."""

    #: Written by the pipeline, never by the model, so no prompt need name them.
    CODE_FILLED = {"paper_id", "schema_version"}

    #: WHOLE schemas describing records written by CODE. The deterministic image
    #: and text tracks are child subprocesses: their output is built in Python
    #: and validated against these files, and no model is ever asked to produce
    #: one. The premise of this test -- "the model is obliged to supply
    #: something it was never told about" -- does not apply, because no model is
    #: obliged to supply any of it. Exempting the FILE rather than listing its
    #: fields keeps that reason in one place instead of scattering it.
    #:
    #: `findings.v2.schema.json` (added 2026-08-21) is the full v2 CONTRACT,
    #: never handed to a model: its required-but-unnamed fields (`finding_id`,
    #: `producer`, `computed_by`, ...) are written by the annotator, pipeline,
    #: or converter (docs/specs/findings_v2.md sections 1 and 4). What a model
    #: WILL see is the generated producer subset
    #: (`prompts.producer_findings_schema`), which strips every
    #: not-producer-written field by omission -- tests/test_findings_schema_v2.py
    #: pins that subtraction, so a field a producer must supply cannot hide
    #: behind this exemption.
    CODE_WRITTEN_SCHEMAS = {
        "image_track.schema.json",
        "text_track.schema.json",
        "findings.v2.schema.json",
    }

    def _required_unnamed(self):
        import json
        from pathlib import Path
        from metascience_agent.core.prompts import prompt_files
        prompts = "\n".join(f.read_text(encoding="utf-8") for f in prompt_files())
        out = []

        def walk(node, path, name, depth=0):
            if depth > 7 or not isinstance(node, dict):
                return
            for r in (node.get("required") or []):
                if r in self.CODE_FILLED:
                    continue
                if not re.search(rf"\b{re.escape(r)}\b", prompts):
                    out.append(f"{name}: {'/'.join(path + [r])}")
            for k, v in (node.get("properties") or {}).items():
                walk(v, path + [k], name, depth + 1)
                if isinstance(v, dict) and isinstance(v.get("items"), dict):
                    walk(v["items"], path + [k, "[]"], name, depth + 1)
            if isinstance(node.get("items"), dict):
                walk(node["items"], path + ["[]"], name, depth + 1)

        for f in sorted(SCHEMAS.glob("*.json")):
            if f.name in self.CODE_WRITTEN_SCHEMAS:
                continue
            walk(json.loads(f.read_text(encoding="utf-8")), [], f.name)
        return sorted(set(out))

    def test_no_required_field_is_unexplained(self):
        unnamed = self._required_unnamed()
        assert not unnamed, (
            "a schema REQUIRES these and no prompt names them, so the model is "
            "obliged to supply something it was never told about:\n  "
            + "\n  ".join(unnamed))

    def test_the_hypothesis_taxonomy_is_a_closed_enum(self):
        """The four values lived in a free-text `description`, so the schema
        could not reject a typo or an invented category."""
        import json
        from pathlib import Path
        p = (Path(__file__).resolve().parents[1]
             / "src/metascience_agent/schema/findings.v2.schema.json")
        s = json.loads(p.read_text(encoding="utf-8"))
        st = (s["properties"]["anatomy"]["properties"]["hypotheses"]
              ["items"]["properties"]["status"])
        assert st.get("enum") == ["preregistered_confirmatory", "confirmatory",
                                  "exploratory", "unstated"]
