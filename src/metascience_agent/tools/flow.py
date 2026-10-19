"""Participant-flow (CONSORT) arithmetic.

The one numeric check the numeric sweep never covers: whether the flow
diagram's own ledger reconciles. Every check is EXACT integer arithmetic --
enrollment counts are counts of people, so there is no rounding window and
no tolerance parameter (contract: docs/specs/pipeline.md section 7).

Four checks, four distinct `failure_mode`s, never fused:
  step_mismatch                stage[i].n - sum(excluded) != stage[i+1].n
  arms_dont_sum                sum(arms[].n) != the stage's n
  analyzed_exceeds_randomized  a later stage (or arm) exceeds the anchor
  unaccounted_attrition        n dropped with NO excluded rows -- capped
                               `suspicious`: papers legitimately omit reasons

A missing or non-integer count is a GUARD path (`indeterminate`), never an
accusation: a tool pointed at the wrong data must refuse, not accuse.
"""

import re

from .severity import CONSISTENT, HIGHLY_SUSPICIOUS, IMPOSSIBLE, INDETERMINATE, SUSPICIOUS

_HARD_MODES = ("step_mismatch", "arms_dont_sum", "analyzed_exceeds_randomized")


#: Stage units, normalised. A flow's monotonicity is only meaningful WITHIN a
#: unit: randomising 24 schools and analysing 1043 pupils is not a flow that
#: gained people, it is two different things being counted.
_UNIT_ALIASES = {
    "participant": "person", "participants": "person", "patient": "person",
    "patients": "person", "subject": "person", "subjects": "person",
    "person": "person", "people": "person", "pupil": "person",
    "pupils": "person", "student": "person", "students": "person",
    "child": "person", "children": "person", "adult": "person",
    "cluster": "cluster", "clusters": "cluster", "school": "cluster",
    "schools": "cluster", "clinic": "cluster", "clinics": "cluster",
    "practice": "cluster", "practices": "cluster", "site": "cluster",
    "sites": "cluster", "ward": "cluster", "wards": "cluster",
    "village": "cluster", "villages": "cluster", "class": "cluster",
    "classroom": "cluster", "classrooms": "cluster",
}


def _norm_unit(value) -> str | None:
    """The declared unit, canonicalised, or None when the stage does not say."""
    if not isinstance(value, str) or not value.strip():
        return None
    key = value.strip().lower()
    return _UNIT_ALIASES.get(key, key)


def _unit_from_label(label) -> str | None:
    """The unit a stage LABEL names, if it names one.

    A CONSORT flow rarely declares units, but it almost always says them:
    "Schools randomized" and "Pupils analyzed" name their units in the words
    the paper printed. Reading them is not a guess -- it is using the paper's
    own text, which is what every other structural question here resorts to.

    RULE 1 APPLIES (a derived boundary may NARROW a premise, never SUPPLY one).
    A label that names no unit yields None, and None never licenses skipping a
    check: only POSITIVE evidence of two DIFFERENT units narrows anything. So
    the canonical `randomized` -> `analyzed` flow, which names no units at all,
    keeps the hard verdict it has always had.
    """
    words = re.findall(r"[a-z]+", str(label or "").lower())
    for w in words:
        unit = _UNIT_ALIASES.get(w)
        if unit:
            return unit
    return None


def _unit_relation(cur: dict, nxt: dict) -> str:
    """`same` | `different` | `unknown` -- and each licenses a different verdict.

      same       both stages declare the same unit. An increase is genuinely
                 impossible and keeps its verdict.
      different  both declare, and they differ. A cluster trial randomising
                 schools and analysing pupils is not an anomaly at all, so
                 there is NOTHING to report -- flagging it would train a reader
                 to ignore this check on every cluster design.
      unknown    at least one stage does not say. Reported, never alleged: the
                 increase is real and a unit change explains it exactly as well
                 as an error does, and no arithmetic separates them.

    UNDECLARED IS NOT "SAME", which is the fail-closed direction: the
    accusation is what needs licensing, and a stage that does not say what it
    counts has not licensed one.
    """
    a, b = cur.get("unit"), nxt.get("unit")
    if a and b:
        return "same" if a == b else "different"

    # Fall back to what the labels say. Only a pair of RECOGNISED and DIFFERING
    # units narrows anything; anything else keeps the existing behaviour.
    la = a or _unit_from_label(cur.get("label"))
    lb = b or _unit_from_label(nxt.get("label"))
    if la and lb and la != lb:
        return "unknown" if not (a and b) else "different"
    return "same"


def _units_differ(cur: dict, nxt: dict) -> bool:
    """True when an increase must NOT be called impossible."""
    return _unit_relation(cur, nxt) != "same"


def _count(value):
    """An exact people-count, or None. Accepts ints and integral floats
    ("120.0" from a JSON round-trip); anything fractional or negative is not
    a count of people."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    return None


def _refuse(reason: str) -> dict:
    return {
        "success": False,
        "severity": INDETERMINATE,
        "consistent": None,
        "applicable": False,
        "error": reason,
        "failures": [],
        "explanation": f"Flow arithmetic refused: {reason}",
    }


def check_flow_arithmetic(stages: list, randomized_label: str | None = None,
                          description: str = "participant flow") -> dict:
    if not isinstance(stages, list) or not stages:
        return _refuse("`stages` must be a non-empty ordered list of "
                       "{label, n, excluded?, arms?} objects")
    parsed = []
    for i, st in enumerate(stages):
        if not isinstance(st, dict):
            return _refuse(f"stage {i} is not an object")
        label = str(st.get("label") or f"stage {i + 1}")
        unit = _norm_unit(st.get("unit"))
        n = _count(st.get("n"))
        if n is None:
            return _refuse(
                f"stage '{label}' has no usable integer n "
                f"({st.get('n')!r}) -- flow counts are whole people, and an "
                "absent or fractional operand cannot support an accusation")
        excluded = []
        for j, ex in enumerate(st.get("excluded") or []):
            if not isinstance(ex, dict):
                return _refuse(f"stage '{label}' excluded[{j}] is not an object")
            ex_n = _count(ex.get("n"))
            if ex_n is None:
                return _refuse(
                    f"stage '{label}' exclusion "
                    f"'{ex.get('reason') or j}' has no usable integer n")
            excluded.append((str(ex.get("reason") or f"exclusion {j + 1}"), ex_n))
        arms = []
        for j, arm in enumerate(st.get("arms") or []):
            if not isinstance(arm, dict):
                return _refuse(f"stage '{label}' arms[{j}] is not an object")
            arm_n = _count(arm.get("n"))
            if arm_n is None:
                return _refuse(
                    f"stage '{label}' arm "
                    f"'{arm.get('label') or j}' has no usable integer n")
            arms.append((str(arm.get("label") or f"arm {j + 1}"), arm_n))
        also = []
        for j, other in enumerate(st.get("also_reported") or []):
            if not isinstance(other, dict):
                return _refuse(f"stage '{label}' also_reported[{j}] is not an object")
            other_n = _count(other.get("n"))
            if other_n is None:
                return _refuse(
                    f"stage '{label}' also_reported "
                    f"'{other.get('source') or j}' has no usable integer n")
            also.append((str(other.get("source") or f"another passage {j + 1}"), other_n))
        parsed.append({"label": label, "n": n, "unit": unit, "excluded": excluded,
                       "arms": arms, "also": also})

    failures: list[dict] = []
    n_checks = 0

    # 1 + 4: step arithmetic where exclusions are given; attrition where not.
    for cur, nxt in zip(parsed, parsed[1:]):
        n_checks += 1
        if cur["excluded"]:
            expected = cur["n"] - sum(n for _, n in cur["excluded"])
            if nxt["n"] != expected:
                failures.append({
                    "failure_mode": "step_mismatch",
                    "stage": cur["label"], "next_stage": nxt["label"],
                    "expected": expected, "observed": nxt["n"],
                    "difference": nxt["n"] - expected,
                    "sentence": (
                        f"'{cur['label']}' (n={cur['n']}) minus its "
                        f"{len(cur['excluded'])} stated exclusion(s) "
                        f"({sum(n for _, n in cur['excluded'])}) leaves "
                        f"{expected}, but '{nxt['label']}' reports "
                        f"{nxt['n']} -- {abs(nxt['n'] - expected)} "
                        "participant(s) unaccounted for by the paper's own "
                        "arithmetic."),
                })
        elif (nxt["n"] > cur["n"]
              and _unit_relation(cur, nxt) == "different"):
            # Declared, and different. Nothing anomalous happened.
            pass
        elif nxt["n"] > cur["n"] and _units_differ(cur, nxt):
            # A FLOW CAN ONLY LOSE PEOPLE -- and only when consecutive stages
            # COUNT THE SAME PEOPLE. A cluster-randomised trial randomises
            # schools and analyses pupils; a surgical trial randomises patients
            # and analyses knees; a lab study randomises animals and analyses
            # samples. In every one, a later stage is legitimately LARGER.
            #
            # MEASURED before this guard: 30 schools assessed, 24 randomised,
            # 1043 pupils analysed -- an ordinary cluster RCT -- returned
            # `impossible`, "Nobody can be analyzed who was never randomized."
            # Cluster designs are routine in education and public health, which
            # is the literature this toolkit is aimed at.
            #
            # Reported, never alleged: the increase is real and worth showing,
            # but a unit change explains it exactly as well as an error does
            # and no arithmetic separates them.
            failures.append({
                "failure_mode": "step_increase_or_unit_change",
                "stage": cur["label"], "next_stage": nxt["label"],
                "expected": cur["n"], "observed": nxt["n"],
                "difference": nxt["n"] - cur["n"],
                "sentence": (
                    f"'{nxt['label']}' reports {nxt['n']} -- more than the "
                    f"{cur['n']} at the preceding stage '{cur['label']}'. A "
                    f"flow can only lose people WHEN BOTH STAGES COUNT THE "
                    f"SAME UNIT, and these two do not say. A cluster design "
                    f"(schools randomised, pupils analysed) produces exactly "
                    f"this shape. Declare `unit` on each stage to have this "
                    f"checked, or confirm the unit before treating it as a "
                    f"finding."),
            })
        elif nxt["n"] > cur["n"]:
            failures.append({
                "failure_mode": "step_mismatch",
                "stage": cur["label"], "next_stage": nxt["label"],
                "expected": cur["n"], "observed": nxt["n"],
                "difference": nxt["n"] - cur["n"],
                "sentence": (
                    f"'{nxt['label']}' reports {nxt['n']} participants -- "
                    f"more than the {cur['n']} present at the preceding "
                    f"stage '{cur['label']}'. A flow can only lose people."),
            })
        elif nxt["n"] < cur["n"]:
            failures.append({
                "failure_mode": "unaccounted_attrition",
                "stage": cur["label"], "next_stage": nxt["label"],
                "expected": cur["n"], "observed": nxt["n"],
                "difference": nxt["n"] - cur["n"],
                "sentence": (
                    f"{cur['n'] - nxt['n']} participant(s) drop between "
                    f"'{cur['label']}' and '{nxt['label']}' with no stated "
                    "exclusions. Not itself an error -- papers legitimately "
                    "omit attrition reasons -- but the reader cannot audit "
                    "the loss."),
            })

    # 2: arms sum to their stage total.
    for st in parsed:
        if st["arms"]:
            n_checks += 1
            total = sum(n for _, n in st["arms"])
            if total != st["n"]:
                failures.append({
                    "failure_mode": "arms_dont_sum",
                    "stage": st["label"],
                    "expected": st["n"], "observed": total,
                    "difference": total - st["n"],
                    "sentence": (
                        f"the arms of '{st['label']}' sum to {total}, but "
                        f"the stage reports n={st['n']} -- "
                        f"{abs(total - st['n'])} participant(s) appear or "
                        "vanish between the total and its own breakdown."),
                })

    # 5: ONE STAGE, PRINTED TWICE. MEASURED 2026-10-14 (cerebrolysin_flow,
    # grok): the cascade was built from the Results (30 -> 21 -> 15), the
    # abstract says 16 rats reached the second operation, and the consistent
    # result was reported as "the flow reconciles" -- a false clearance of
    # the paper's central contradiction. A count the paper prints in two
    # places is checked against itself. `highly_suspicious`, not
    # `impossible`: that both passages describe the SAME stage is the
    # caller's reading, not printed arithmetic.
    for st in parsed:
        for source, other_n in st["also"]:
            n_checks += 1
            if other_n != st["n"]:
                failures.append({
                    "failure_mode": "conflicting_reports",
                    "stage": st["label"],
                    "expected": st["n"], "observed": other_n,
                    "difference": other_n - st["n"],
                    "sentence": (
                        f"'{st['label']}' is n={st['n']} in the cascade but "
                        f"{other_n} in {source} -- the paper prints two counts "
                        "for what it presents as the same stage."),
                })

    # 3: nothing after the anchor may exceed it.
    anchor = None
    if randomized_label:
        anchor = next((s for s in parsed
                       if s["label"].lower() == randomized_label.lower()), None)
        if anchor is None:
            return _refuse(
                f"randomized_label {randomized_label!r} names no stage")
    else:
        anchor = next((s for s in parsed if "random" in s["label"].lower()),
                      None)
    anchor_note = None
    if anchor is not None:
        idx = parsed.index(anchor)
        for later in parsed[idx + 1:]:
            n_checks += 1
            over = [("stage", later["label"], later["n"])] \
                if later["n"] > anchor["n"] else []
            over += [("arm", lbl, n) for lbl, n in later["arms"]
                     if n > anchor["n"]]
            # THE SAME UNIT PREMISE AS THE STEP CHECK. "Nobody can be analyzed
            # who was never randomized" is true of PEOPLE and false across a
            # unit change: a cluster trial randomises 24 schools and analyses
            # 1043 pupils, and every pupil was in a randomised school. Measured
            # before this guard, that flow returned `impossible`.
            if over and _unit_relation(anchor, later) == "different":
                over = []          # declared, and different: nothing to report
            if over and _units_differ(anchor, later):
                for kind, lbl, n in over:
                    failures.append({
                        "failure_mode": "exceeds_randomized_or_unit_change",
                        "stage": lbl,
                        "expected": anchor["n"], "observed": n,
                        "difference": n - anchor["n"],
                        "sentence": (
                            f"{kind} '{lbl}' reports {n}, more than the "
                            f"{anchor['n']} at '{anchor['label']}'. Nobody can "
                            f"be analyzed who was never randomized -- WHEN BOTH "
                            f"STAGES COUNT THE SAME UNIT, and these do not say. "
                            f"A cluster design randomises clusters and analyses "
                            f"individuals, which produces exactly this. Declare "
                            f"`unit` on each stage to have this checked."),
                    })
                over = []
            for kind, lbl, n in over:
                failures.append({
                    "failure_mode": "analyzed_exceeds_randomized",
                    "stage": lbl,
                    "expected": anchor["n"], "observed": n,
                    "difference": n - anchor["n"],
                    "sentence": (
                        f"{kind} '{lbl}' reports {n} participants, more "
                        f"than the {anchor['n']} at '{anchor['label']}'. "
                        "Nobody can be analyzed who was never randomized."),
                })
    else:
        anchor_note = ("no randomized stage identified (pass "
                       "`randomized_label`); the analyzed<=randomized check "
                       "did not run")

    if n_checks == 0:
        return _refuse("a single stage with no exclusions and no arms gives "
                       "this check nothing to verify")

    hard = [f for f in failures if f["failure_mode"] in _HARD_MODES]
    conflicting = [f for f in failures if f["failure_mode"] == "conflicting_reports"]
    soft = [f for f in failures if f["failure_mode"] not in _HARD_MODES
            and f["failure_mode"] != "conflicting_reports"]
    if hard:
        severity = IMPOSSIBLE
        explanation = (
            f"The {description} does not reconcile: " +
            " ".join(f["sentence"] for f in hard + conflicting))
    elif conflicting:
        severity = HIGHLY_SUSPICIOUS
        explanation = (
            f"The {description} is printed with conflicting counts: " +
            " ".join(f["sentence"] for f in conflicting))
    elif soft:
        severity = SUSPICIOUS
        explanation = (
            f"The {description} balances arithmetically but "
            f"{len(soft)} transition(s) drop participants with no stated "
            "reason: " + " ".join(f["sentence"] for f in soft))
    else:
        severity = CONSISTENT
        explanation = (f"The {description} AS PASSED reconciles: {n_checks} flow "
                       "identit(ies) hold exactly. Only the counts passed were "
                       "checked; a stage the paper prints with a different "
                       "count elsewhere is caught only through `also_reported`.")

    result = {
        "success": True,
        "severity": severity,
        "consistent": not failures,
        "applicable": True,
        "n_checks": n_checks,
        "n_stages": len(parsed),
        "failures": failures,
        "explanation": explanation,
    }
    if anchor_note:
        result["note"] = anchor_note
    return result
