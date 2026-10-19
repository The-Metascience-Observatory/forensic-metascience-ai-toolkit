"""Generate the checked-in ladder artifacts from the Python sources of truth.

Two encodings of ONE payload, both written by `metascience
gen-webapp-constants` so they cannot drift apart:

  - `webapp/lib/constants.gen.ts` -- the Next.js app, which needs `as const`
    typing and the `sev9Label`/`sev9Color`/`legacyToNine` helpers.
  - `docs/severity_ladder.json` -- everything else. A static ladder page, a
    paper appendix or an external consumer should not have to parse
    TypeScript to read the rungs.

R1: `severity9.py` owns the 1-9 ladder; `review_io` owns the decision
vocabulary; `webapp_index` owns the channel states. The webapp gets a
CHECKED-IN generated file rather than build-time codegen -- it must keep
working on a Windows checkout with no Python -- and a Python test
regenerates and byte-compares each artifact, so a stale checkout fails the
suite instead of silently shipping a divergent ladder (the registry-snapshot
pattern).

The module name is narrower than what it now emits. A rename would churn
`cli.py` and the tests to no behavioural end; one module and one command is
what keeps the two artifacts in step.
"""

from __future__ import annotations

import json
from pathlib import Path

HEADER = """// GENERATED FILE -- do not edit.
// Regenerate with: metascience gen-webapp-constants
// Sources of truth: severity9.py (ladder, legacy map), review_io.py
// (decision vocabulary), webapp_index.py (channel states), names.py
// (display names of stored producer/stage/channel identifiers).
// tests/test_webapp_constants.py regenerates and byte-compares.
"""


def render() -> str:
    from . import severity9
    from .review_io import IMAGE_DECISIONS, NUMERIC_DECISIONS
    from .webapp_index import CHANNEL_STATES

    ladder = severity9.as_json()
    lines = [HEADER]
    lines.append("export const SEVERITY9 = "
                 + json.dumps(ladder, indent=2, sort_keys=True)
                 + " as const;\n")
    lines.append("export const FIVE_TO_NINE: Record<string, number> = "
                 + json.dumps(severity9.FIVE_TO_NINE, sort_keys=True)
                 + ";\n")
    lines.append("export const ACCUSATORY_MIN = "
                 + str(severity9.ACCUSATORY_MIN) + ";\n")
    lines.append("export const NUMERIC_DECISIONS = "
                 + json.dumps(list(NUMERIC_DECISIONS)) + " as const;\n")
    lines.append("export const IMAGE_DECISIONS = "
                 + json.dumps(list(IMAGE_DECISIONS)) + " as const;\n")
    lines.append("export const CHANNEL_STATES = "
                 + json.dumps(list(CHANNEL_STATES)) + " as const;\n")
    from .names import display_names
    lines.append("export const DISPLAY_NAMES: Record<string, string> = "
                 + json.dumps(display_names(), indent=2, sort_keys=True) + ";\n")
    lines.append("""
export type Sev9Level = (typeof SEVERITY9)["levels"][number];

const byN = new Map<number, Sev9Level>(SEVERITY9.levels.map((l) => [l.n, l]));

/** Ladder label for a 1-9 level; "" when the value is not on the ladder. */
export function sev9Label(n: number | null | undefined): string {
  const l = typeof n === "number" ? byN.get(n) : undefined;
  return l ? `S${l.n} \u00b7 ${l.label}` : "";
}

/** Color for a 1-9 level in the given theme. */
export function sev9Color(n: number | null | undefined,
                          theme: "light" | "dark" = "light"): string {
  const l = typeof n === "number" ? byN.get(n) : undefined;
  return l ? l.colors[theme] : "transparent";
}

/** Map a legacy 5-enum severity string onto the ladder; null when unmapped
 * (consistent/indeterminate carry no level -- absence, not zero). A mapped
 * value must always render with a "(legacy)" marker: a mapped S5 presented
 * as an assigned S5 is exactly the substitution this toolkit exists to
 * catch. */
export function legacyToNine(sev5: string | null | undefined): number | null {
  return sev5 != null && sev5 in FIVE_TO_NINE ? FIVE_TO_NINE[sev5] : null;
}

/** The name a person reads for a stored producer value, stage label or
 * channel key (`tool_expert` -> "Tools agent"); unknown ones pass through.
 * The stored values never change: they are hashed into finding ids. */
export function displayName(id: string | null | undefined): string {
  return id ? DISPLAY_NAMES[id] ?? id : "";
}
""")
    return "\n".join(lines)


def render_ladder_json() -> str:
    """The ladder payload as JSON. `sort_keys` + a fixed indent + a trailing
    newline are what make the byte-compare in tests/test_webapp_constants.py
    meaningful rather than a diff of formatting noise."""
    from . import severity9

    return json.dumps(severity9.as_json(), indent=2, sort_keys=True) + "\n"


def _root(repo_root: Path | None = None) -> Path:
    return repo_root or Path(__file__).resolve().parents[2]


def target_path(repo_root: Path | None = None) -> Path:
    return _root(repo_root) / "webapp" / "lib" / "constants.gen.ts"


def ladder_json_path(repo_root: Path | None = None) -> Path:
    return _root(repo_root) / "docs" / "severity_ladder.json"


def write(repo_root: Path | None = None) -> list[Path]:
    """Write BOTH artifacts and return their paths, in render order."""
    written = []
    for path, text in (
        (target_path(repo_root), render()),
        (ladder_json_path(repo_root), render_ladder_json()),
    ):
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
