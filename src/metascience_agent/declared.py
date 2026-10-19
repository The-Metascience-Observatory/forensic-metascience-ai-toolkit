"""The declared variables of the paper under review, and what a check owes them.

WHY THIS EXISTS. `anatomy.Variable` records what the paper measured -- family,
NOIR level, discreteness, bounds, units, items, how the value was derived. The
granularity checks take the same facts as loose scalars: `scale_min`,
`scale_max`, `data_type`, `bound_source`, `discreteness_source`. On the TABLE
path those are already read off the declared variable, by
`dispatch._variable_kwargs` -> `Variable.forensic_kwargs`, and the resulting
check record carries `variable_id`. That path is sound.

On the MODEL path they are not. When the model calls `grim_check` itself, it
restates the bounds and the discreteness freehand, and nothing ties the call to
the variable it declared two steps earlier. So the anatomy and the check are two
independent statements of one fact, never reconciled -- and a paper can be
declared Likert 1-7 discrete in the anatomy and checked as continuous on 0-100,
with no reader able to see the contradiction.

MEASURED across the three checks that accept scale bounds. CORRECTED
2026-08-18, and the correction is the point: the first count was 116 calls with
43 lacking bounds (37%), taken by walking the whole repo and counting every
`findings.json` on disk. Both halves were wrong. The walk reached run copies
outside the archive proper, and 22 of the 57 `findings.json` in the archive are
BYTE-IDENTICAL bundle copies of another -- a bundle carries its own copy of the
findings it renders. Counting files instead of runs inflated the numerator and
the denominator together, which is why the error hid: the ratio still looked
plausible.

Deduplicated by content hash, over the four archive directories:

    62 bound-taking calls          (grim 28, grimmer 25, sprite 9)
    16 of 62 (25.8%) passed no scale bounds at all
    14 of 62 (22.6%) passed no `data_type`
    40 of 62 (64.5%) passed no `bound_source`

Those are the calls whose rounding interval and severity ceiling were decided by
a registry default rather than by the paper. The conclusion is unchanged and the
magnitude is smaller than first reported.

WHICH SIDE WINS ON A DISAGREEMENT. Neither, silently. A check that quietly
preferred the record would let a mis-declared variable drive an accusation; one
that preferred the call would make the anatomy decorative. So a disagreement
resolves to the SAFER reading in every case -- the wider scale, the unknown
type, `assumed` provenance -- which can only ever make the check under-accuse,
and it is recorded so a reader sees that the two disagreed at all. This follows
the cardinal rule: a false accusation against an honest paper is the worst
output this toolkit can produce.
"""

from __future__ import annotations

from typing import Any

#: The variables declared for the paper currently under review, by id.
#:
#: Module-level because `ToolSpec.call` is the one point every path converges on
#: -- the table dispatcher, the model's MCP calls, and the CLI -- and threading a
#: parameter through all three would leave the one that forgot it unreconciled.
#: A run reviews one paper at a time, and `set_variables` REPLACES rather than
#: merges so a variable cannot survive into the next paper's review.
_VARIABLES: dict[str, dict] = {}


def set_variables(variables: Any) -> int:
    """Declare the variables for the paper under review. Returns the count."""
    _VARIABLES.clear()
    for v in variables or ():
        if isinstance(v, dict) and v.get("id"):
            _VARIABLES[str(v["id"])] = dict(v)
    return len(_VARIABLES)


def add_variables(variables: Any) -> int:
    """Merge declarations in, keeping what is already known. Returns the count.

    MERGE, not replace, because the model declares variables a table at a time:
    `check_table` is the only surface that takes them, so a paper with three
    tables declares three subsets, and replacing would leave only the last
    table's variables addressable by a later per-cell call.
    """
    for v in variables or ():
        if isinstance(v, dict) and v.get("id"):
            _VARIABLES[str(v["id"])] = dict(v)
    return len(_VARIABLES)


def clear() -> None:
    """Forget them. Called between papers."""
    _VARIABLES.clear()


def get(variable_id: Any) -> dict | None:
    return _VARIABLES.get(str(variable_id)) if variable_id is not None else None


def declared_count() -> int:
    return len(_VARIABLES)


#: The arguments a check takes that RESTATE a property of the variable. These
#: are the ones that can disagree with the record; everything else a check takes
#: (`mean`, `sd`, `n`, `decimals`) is a property of the CELL, not the variable.
RECONCILED = ("scale_min", "scale_max", "data_type",
              "bound_source", "discreteness_source", "items")


def _forensic_kwargs(variable: dict, share: bool = False) -> tuple[dict, str | None]:
    """What the declared variable says, in the checks' own vocabulary.

    Returns `(kwargs, error)`. The error is RETURNED rather than swallowed: an
    unreadable declaration used to come back as `{}`, which is exactly what a
    variable declaring nothing returns, so a malformed anatomy entry reconciled
    silently against nothing and the check ran on the model's own arguments as
    though the paper had been consulted.
    """
    try:
        from .dispatch import _as_variable
        return _as_variable(variable).forensic_kwargs(share=share), None
    except Exception as exc:  # noqa: BLE001 -- reported, not discarded
        return {}, f"{type(exc).__name__}: {exc}"


def _wider(a: Any, b: Any, *, take: str) -> Any:
    """The scale bound that makes the check more permissive."""
    try:
        return min(float(a), float(b)) if take == "min" else max(float(a), float(b))
    except (TypeError, ValueError):
        return None


def reconcile(accepts: set, args: dict) -> tuple[dict, dict | None]:
    """Settle a call's variable properties against the declared record.

    `accepts` is the set of parameter names the check actually takes, so a
    property is only filled in where the check can use it.

    Returns `(args, provenance)`. `provenance` is None when the call named no
    variable, which leaves today's behaviour exactly as it was: this can turn an
    unreconciled call into a reconciled one and can never change a call that
    never mentioned a variable.
    """
    vid = args.get("variable_id")
    if vid is None:
        return args, None

    variable = get(vid)
    if variable is None:
        # NAMED BUT NOT DECLARED. Not an error to refuse over -- the model may
        # name a variable the anatomy pass never wrote -- but it must not read
        # as reconciled, and nothing is filled in from a record we do not have.
        return args, {"variable_id": str(vid), "status": "not_declared",
                      "note": ("This check named a variable that is not in the "
                               "declared anatomy, so nothing about its scale or "
                               "type could be checked against the paper.")}

    # A check that takes a `percentage` and a `data_type` (grim_percentage)
    # reads a category family as the share of the sample it is; the table
    # path sends it that reading, and the record must agree with it.
    declared, declaration_error = _forensic_kwargs(
        variable, share={"percentage", "data_type"} <= set(accepts))
    out = dict(args)
    filled: list[str] = []
    agreed: list[str] = []
    disagreed: list[dict] = []

    for key in RECONCILED:
        if key not in accepts or key not in declared:
            continue
        want = declared[key]
        if key not in args or args[key] is None:
            out[key] = want
            filled.append(key)
            continue
        if args[key] == want:
            agreed.append(key)
            continue
        disagreed.append({"parameter": key, "call_said": args[key],
                          "paper_declared": want})
        # THE SAFER READING, never a silent preference for one side.
        if key == "scale_min":
            out[key] = _wider(args[key], want, take="min")
        elif key == "scale_max":
            out[key] = _wider(args[key], want, take="max")
        else:
            # `data_type` unknown, and both provenance fields `assumed`, are the
            # least-licensing values each of them has: they widen the rounding
            # interval and withdraw the licence to say `impossible`.
            out[key] = "unknown" if key == "data_type" else "assumed"

    if disagreed:
        # A disagreement anywhere withdraws the `stated` provenance, even on the
        # parameters that agreed. If the call and the paper cannot agree on what
        # this variable IS, neither of them has established its bounds.
        for key in ("bound_source", "discreteness_source"):
            if key in accepts:
                out[key] = "assumed"

    prov: dict = {
        "variable_id": str(vid),
        "name": variable.get("name"),
        "family": variable.get("family"),
        "measurement_level": variable.get("measurement_level"),
        "discreteness": variable.get("discreteness"),
        "bounds": [variable.get("lower_bound"), variable.get("upper_bound")],
        "derivation": variable.get("derivation"),
        "status": ("unreadable_declaration" if declaration_error
                   else "disagreed" if disagreed else "reconciled"),
        "filled_from_the_paper": filled or None,
        "agreed": agreed or None,
        "disagreements": disagreed or None,
    }
    if declaration_error:
        prov["error"] = declaration_error
        prov["note"] = (
            "This variable's declaration could not be read, so NOTHING about "
            "the check's scale or type was checked against the paper. The "
            "check ran on its own arguments alone. Treat it as unreconciled, "
            "not as agreeing."
        )
    elif disagreed:
        prov["note"] = (
            "This check's own arguments contradict the variable the paper "
            "declared. Neither side was preferred: each contested value was "
            "resolved to the reading that makes the check LESS likely to "
            "accuse -- the wider scale, the unknown type -- and the provenance "
            "was downgraded to `assumed`, which withdraws the licence to call "
            "anything impossible. Resolve the declaration before reading a "
            "verdict off this."
        )
    return out, prov


#: NOIR levels on which a MEAN is not a defined quantity.
#:
#: Nominal only. Ordinal is deliberately absent: a Likert item is ordinal, and
#: GRIM on Likert means is the canonical use of the check, so refusing ordinal
#: would delete the toolkit's main case to make a philosophical point.
_NO_MEAN = {"nominal"}


def mean_is_undefined(args: dict) -> dict | None:
    """Is this a mean-based check on a variable that cannot have a mean?

    `measurement_level` is the paper's NOIR declaration. Until now nothing read
    it: it was asked for in the sweep prompt, carried on `Variable`, printed in
    the report table and the viewer, and consumed by no check -- the same defect
    the `derivation` field carried before it was wired. This is its consumer.
    """
    variable = get(args.get("variable_id"))
    if not variable:
        return None
    level = str(variable.get("measurement_level") or "").strip().lower()
    if level not in _NO_MEAN:
        return None
    return {
        "severity": "indeterminate",
        "applicable": False,
        "consistent": None,
        "error": (f"{variable.get('name') or args.get('variable_id')} is "
                  f"declared {level}, and a mean of a {level} variable is not a "
                  "defined quantity"),
        "explanation": (
            "Not a statement about the paper's arithmetic. The check was asked "
            "to test the granularity of a mean on a variable the paper declares "
            "as unordered categories, where no mean exists to test. Either the "
            "cell is not a mean, or the variable's `measurement_level` is wrong."
        ),
        "variable": {"variable_id": str(args.get("variable_id")),
                     "measurement_level": level,
                     "family": variable.get("family")},
    }
