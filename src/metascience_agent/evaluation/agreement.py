"""How much of what this pipeline reports would it report again?

Greg, 2026-08-13, after reading SPOT: implement pass@K.

WHY IT IS THE RIGHT METRIC TO BORROW. Son et al. (2025) evaluated frontier
models on 83 papers with 91 errata/retraction-grade errors and found "across
eight independent runs, models rarely rediscover the same errors" -- alongside
21.1% recall and 6.1% precision at best on the FULL multimodal corpus. (The
qualifier matters and was missing until 2026-08-18: their Table 3 reports o3 at
34.6% recall on the figure-independent subset, so a bare "at best" understates
them. Verified against the paper, not carried over from a summary.) Our own Romano variability study, run
for unrelated reasons, found the same thing with a sharper edge:

    checks with a unique, argument-free target      8 of 8 recurred  (100%)
    checks where the MODEL picks the target         0 of 10 recurred (0%)

Two teams, two corpora, one finding: TOOL DETERMINISM DOES NOT SURVIVE TARGET
FREEDOM. We measured it once, by hand, on one paper. SPOT made it a standing
number, and a standing number is the difference between knowing this and
remembering it.

WHAT pass@K MEANS HERE. Not "did the model solve the task" -- there is no task
to solve. For each distinct finding the pipeline has ever produced on a paper,
`c` of `n` runs found it, and

    pass@k = 1 - C(n-c, k) / C(n, k)

is the chance that at least one of k runs surfaces it. pass@1 is the honest
single-run reliability; the gap to pass@n is what a reader loses by our giving
them one run.

THE MATCHING RULE IS THE WEAK POINT, SO TWO ARE REPORTED AND THE TRUTH IS
BRACKETED. Deciding that two runs found "the same" finding is a judgement no
string comparison makes well, and a single rule dressed as a number is worse
than no number.

    STRICT   full normalised location + severity band. Under-merges badly:
             `location` is free prose, so "Table 1, BDI / CIA / DERS
             total-score rows" and "Table 1, BDI, CIA and DERS total-score
             rows" -- the same finding, two runs -- do not match. A FLOOR.
    LOOSE    structural anchor only (table 3 / figure 2 / the section name)
             plus band. Over-merges: two genuinely different defects in one
             table become one. A CEILING.

MEASURED 2026-08-13 on Romano's three archived runs, the strict rule put 58 of
59 clusters in exactly one run -- which contradicts the hand-done variability
study on the same paper (5 of 10 clusters shared by substance) and is therefore
a fact about the rule, not about the pipeline. That is why both are reported.
The honest reading is the interval: pass@1 is somewhere in 34%-64%.

**AND THAT INTERVAL IS TOO WIDE TO BE USEFUL, WHICH IS THE POINT OF THIS NOTE.**
A standing metric exists to show improvement, and nothing moves a number that
spans thirty points. Greg, 2026-08-13: "the evaluation of test-retest
reliability of our tool might be complicated by the phenomenon you just
observed, whereby the same finding might be classified differently across runs
... have another dedicated agent (run separately, for the purposes of
development) do its best to rigorously classify the inter-run findings and
decide what constitutes rediscovery. Based on how the findings are syntheses of
multiple pieces of data, this kind of semi-quantitative scoring modality is
probably the best we can hope for."

That is right, it is the same lesson as every other discriminating step in this
project, and SPOT reached it independently -- their true positive requires a
location match AND an LLM confirming the two descriptions denote the same error.
A finding is a synthesis of location, claim, computed values, severity and
warrant; two runs can agree on the defect and differ on three of those, and no
string rule sees through that.

So WHAT IS BELOW IS A PLACEHOLDER, deliberately cheap and deliberately
bracketed, and the interval is the honest statement of how little it knows.
Task #154 replaces it with an adjudicator, scored first against the hand-done
Romano labels -- because an unvalidated judge trades a bad number for an
unfalsifiable one. Keep these string rules afterwards as a free regression
check, never as the reported figure.
"""

from __future__ import annotations

import json
import math
import re
import pathlib
from pathlib import Path

#: Severity collapsed to two bands. A finding that moves `suspicious` <->
#: `highly_suspicious` between runs is the same finding disagreeing about
#: degree; one that moves `consistent` <-> `suspicious` is not.
from ..finding_view import is_accusatory


def _band(finding: dict) -> str:
    """Accuses or clears, by the shared reader.

    This read `str(finding["severity"]) in ACCUSATORY` -- the five v1 words --
    while `from_review_dirs` had been fixed (2026-09-01) to load
    `findings.v2.json`, whose rows carry an INTEGER. So on every v2 paper every
    row banded "clears": MEASURED over the 285 rows of the ten litvak control
    runs (v1.22.0), 285 clears, 0 accuses, against 51 problem rows at level 3+.
    An accusation and a pass at the same location also collapsed into one
    cluster, so the strict floor was wrong too. (The one two-run v2 paper in
    reach, `masliah_papers/10.1038--s41398-021-01709-9`, carries no accusation
    in either run, so its `accusations: 0 clusters` is a true zero before and
    after -- the proof is the band count above, not that paper.)
    """
    return "accuses" if is_accusatory(finding) else "clears"


#: The structural anchors a location can name. Order matters: the first that
#: matches wins, so "Table 2, Figure 3 caption" anchors on the table.
_ANCHOR = re.compile(
    r"\b(table\s*s?\d+|figure\s*s?\d+|fig\.?\s*s?\d+|appendix\s*\w?|"
    r"abstract|methods?|results?|discussion|introduction|supplement\w*)\b", re.I)


def cluster_key(finding: dict, loose: bool = False) -> str:
    """The identity of a finding under one of the two rules.

    `loose=True` keeps only the structural anchor, which over-merges and gives
    a ceiling; the default keeps the full location and under-merges badly,
    giving a floor. Neither is right; the pair brackets the answer.
    """
    loc = str(finding.get("location") or "").lower()
    band = _band(finding)
    if loose:
        m = _ANCHOR.search(loc)
        anchor = re.sub(r"\s+", " ", m.group(1)).strip() if m else (loc[:18] or "?")
        return f"{anchor}|{band}"
    return f"{' '.join(re.sub(r'[^a-z0-9]+', ' ', loc).split())}|{band}"


def pass_at_k(c: int, n: int, k: int) -> float:
    """Probability at least one of k draws from n runs hits a finding seen c times."""
    if c <= 0 or k <= 0 or n <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def agreement(runs: list[list[dict]]) -> dict:
    """`runs` is one findings list per independent run of the SAME paper."""
    n = len(runs)
    if n < 2:
        return {"n_runs": n, "measurable": False,
                "note": "pass@K needs at least two runs of one paper. With one "
                        "run there is nothing to disagree with -- this is NOT "
                        "an agreement of 100%."}

    def count(loose: bool, only_accusations: bool) -> dict[str, int]:
        out: dict[str, int] = {}
        for run in runs:
            keys = {cluster_key(f, loose) for f in run
                    if isinstance(f, dict)
                    and (not only_accusations or is_accusatory(f))}
            for k in keys:
                out[k] = out.get(k, 0) + 1
        return out

    seen = count(False, False)
    acc_seen = count(False, True)
    seen_loose = count(True, False)
    acc_loose = count(True, True)

    def summarise(counts: dict[str, int]) -> dict:
        if not counts:
            return {"n_clusters": 0, "pass_at": {}, "in_every_run": 0,
                    "in_one_run_only": 0}
        return {
            "n_clusters": len(counts),
            "in_every_run": sum(1 for c in counts.values() if c == n),
            "in_one_run_only": sum(1 for c in counts.values() if c == 1),
            "pass_at": {
                str(k): round(
                    sum(pass_at_k(c, n, k) for c in counts.values()) / len(counts), 3)
                for k in range(1, n + 1)},
        }

    all_s, acc_s = summarise(seen), summarise(acc_seen)
    all_l, acc_l = summarise(seen_loose), summarise(acc_loose)
    return {
        "n_runs": n, "measurable": True,
        "all_findings": all_s, "accusations": acc_s,
        "all_findings_loose": all_l, "accusations_loose": acc_l,
        "pass_at_1_bracket": [all_s["pass_at"].get("1", 0.0),
                              all_l["pass_at"].get("1", 0.0)],
        "matching_rule": "TWO rules, bracketing: strict full-location (floor) "
                         "and loose structural-anchor (ceiling). See the module "
                         "docstring -- neither is correct alone.",
        "note": _note(n, all_s, acc_s, all_l, acc_l),
    }


def _note(n: int, all_s: dict, acc_s: dict, all_l: dict, acc_l: dict) -> str:
    if not all_s["n_clusters"]:
        return "No findings in any run."
    lo, hi = all_s["pass_at"].get("1", 0.0), all_l["pass_at"].get("1", 0.0)
    head = (f"Across {n} runs, ONE RUN SURFACES BETWEEN {lo:.0%} AND {hi:.0%} "
            "of what the pipeline is capable of finding on this paper "
            f"(pass@1, strict to loose matching; {all_s['n_clusters']} to "
            f"{all_l['n_clusters']} distinct findings depending on the rule).")
    if acc_l["n_clusters"]:
        alo = acc_s["pass_at"].get("1", 0.0)
        ahi = acc_l["pass_at"].get("1", 0.0)
        head += (f" For ACCUSATIONS specifically it is {alo:.0%} to {ahi:.0%}.")
    return head + (" The interval is wide because matching findings across runs "
                   "by string is unreliable, not because the answer is unknown "
                   "in principle -- an accusation only one run makes is not "
                   "thereby wrong, but a reader handed one run is seeing a "
                   "sample and should be told so.")


def _paper_id_of(run_dir: Path) -> str | None:
    """Which paper a review directory is about, from whichever file says so."""
    for name in ("run_meta.json", "report.json", "findings.json"):
        f = run_dir / name
        if not f.is_file():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        pid = d.get("paper_id") or (d.get("paper_metadata") or {}).get("doi")
        if pid:
            return str(pid)
    return None


def from_review_dirs(dirs: list[str | Path]) -> dict:
    """Read `findings.json` from each directory and compare them.

    REFUSES A MIXED SET, and it did not until 2026-08-18.

    pass@K asks how much of what this pipeline can find on ONE PAPER a single
    run surfaces. Computed across runs of DIFFERENT papers the arithmetic still
    completes, every cluster appears in exactly one run because no two runs saw
    the same paper, and the result is a low, authoritative-looking reliability
    figure that means nothing.

    MEASURED: pointing `find_runs` at `funder_demo_2026-08-10/reviews` (a
    directory removed from the repo on 2026-09-02) -- it held reviews of
    THREE different papers -- returned pass@1
    bracketed at 26%-41%, under a note reading "of what the pipeline is capable
    of finding ON THIS PAPER". There was no this paper. The caller error was
    mine; the silence was the module's.
    """
    runs, used, ids = [], [], {}
    schemas: dict[str, str] = {}
    for d in dirs:
        # BOTH FILENAMES, AND WHICH ONE IS RECORDED.
        #
        # This read only `findings.json`. The current pipeline writes
        # `findings.v2.json`, so on a paper with runs of both kinds this verb
        # selected EXCLUSIVELY the retired-schema ones and published a
        # reproducibility percentage about a pipeline that no longer exists --
        # CLAUDE.md section 0b implemented as a command. Measured on
        # 10.1002--ajcp.70049: three runs used, all three schema 1.0, while
        # `metascience runs` reports 3 current and 3 stale and the two sets are
        # disjoint.
        found = None
        for name, schema in (("findings.v2.json", "v2"), ("findings.json", "v1")):
            candidate = Path(d) / name
            if candidate.is_file():
                found = (candidate, schema)
                break
        if found is None:
            continue
        p, schema = found
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        fl = data.get("findings") if isinstance(data, dict) else data
        if isinstance(fl, list):
            runs.append(fl)
            used.append(Path(d).name)
            ids[Path(d).name] = _paper_id_of(Path(d))
            schemas[Path(d).name] = schema

    # SCHEMAS ARE NOT COMPARABLE, and mixing them silently would be worse than
    # the bug above. A v1 finding and a v2 finding of the same defect differ in
    # id derivation, severity type and technique vocabulary, so "the same
    # finding in both runs" cannot be decided across the boundary. Refuse, and
    # say which runs are which, rather than reporting an agreement figure that
    # measures the schema change.
    if len({s for s in schemas.values()}) > 1:
        by = {}
        for name, s in schemas.items():
            by.setdefault(s, []).append(name)
        return {"error": "mixed_schemas", "runs_used": [], "schemas": schemas,
                "note": ("These runs do not use one findings schema, so they "
                         "cannot be compared: a v1 and a v2 row differ in id "
                         "derivation, severity type and technique vocabulary, "
                         "and any agreement figure across them would be "
                         "measuring the schema change rather than the "
                         "pipeline. "
                         + "; ".join(f"{s}: {', '.join(sorted(v))}"
                                     for s, v in sorted(by.items()))
                         + ". Re-run `metascience agreement` on runs of one "
                           "schema -- `metascience runs <paper>` says which "
                           "are current.")}

    distinct = {v for v in ids.values() if v}
    if len(distinct) > 1:
        return {
            "measurable": False,
            "n_runs": len(runs),
            "runs_used": used,
            "n_dirs_given": len(list(dirs)),
            "paper_ids": ids,
            "pass_at_1_bracket": None,
            "note": (
                "NOT MEASURED: these directories are reviews of "
                f"{len(distinct)} DIFFERENT papers ({', '.join(sorted(distinct))}). "
                "pass@K measures how much of what the pipeline can find on ONE "
                "paper a single run surfaces; across different papers the "
                "arithmetic completes and answers nothing, because no two runs "
                "ever saw the same text. Pass repeated runs of one paper."),
        }

    out = agreement(runs)
    out["runs_used"] = used
    out["n_dirs_given"] = len(list(dirs))
    out["paper_id"] = next(iter(distinct), None)
    if not distinct:
        out["note"] = ("No run recorded which paper it reviewed, so whether "
                       "these are runs of the SAME paper is unverified. "
                       + str(out.get("note") or ""))
    if len(used) < len(list(dirs)):
        out["note"] = (f"{len(list(dirs)) - len(used)} of the directories given "
                       "carried no readable findings.json and were skipped. "
                       + str(out.get("note") or ""))
    return out


def find_runs(paper_dir: str | Path) -> list[Path]:
    """Every review directory under a paper that carries findings."""
    base = Path(paper_dir)
    if not base.is_dir():
        return []
    # BOTH FILENAMES. This looked only for `findings.json`, which the current
    # pipeline does not write -- so on a paper carrying runs of both kinds it
    # returned exclusively the retired-schema ones, and `metascience agreement`
    # published a reproducibility percentage about a pipeline that no longer
    # exists.
    #
    # CURRENT FIRST. When a paper has runs of both schemas the two cannot be
    # compared (see `from_review_dirs`), and the useful answer is about the
    # pipeline in use, so v2 runs are preferred outright rather than mixed.
    def _carries(d: pathlib.Path) -> str | None:
        if (d / "findings.v2.json").is_file():
            return "v2"
        if (d / "findings.json").is_file():
            return "v1"
        return None

    by_schema: dict[str, list] = {}
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        schema = _carries(d)
        if schema:
            by_schema.setdefault(schema, []).append(d)
    return by_schema.get("v2") or by_schema.get("v1") or []
