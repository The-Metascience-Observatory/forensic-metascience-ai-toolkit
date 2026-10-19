"""The default review sends exactly what the last reviewed oracle says.

An INDEPENDENT oracle, not two post-refactor paths compared with each other.
`tests/parity_capture.py` records every invocation's argv (system prompt,
allowlist, --json-schema, MCP config), environment overlay, sandbox files
(Codex/Grok config, schema, prompt), the user prompt each stage receives,
run_meta settings, `prompt_sha256`, `registry_sha256`, the history parent's
recorded parameters, channels, `is_error` and the findings document's keys,
for all three backends. Coverage limits are stated in `parity_capture.py`.

TWO FIXTURES, and the second exists only because the first is checked:

* `parity_05537458.json`: captured from origin/main 05537458, the last commit
  before pipelines existed. Phases 1, 2 and 3a sent exactly this.
* `parity_p3b.json`: captured from this tree at Phase 3b, which changed WHAT
  THE MODELS ARE TOLD on purpose (reproductions are generated, so the CLI map
  left both analyst prompts; the analysts' new names; the `reproduction`
  schema text). `test_phase3b_changed_only_what_the_models_are_told` proves
  the two fixtures differ ONLY in system prompts, output schemas and
  `prompt_sha256` -- every argv flag, env, allowlist, MCP config, user prompt,
  setting, history parameter and channel is still 05537458's.

The live capture is compared with the newest fixture. A later deliberate
change to what the default run sends adds a fixture and a scope test like
that one, and says so in CHANGELOG.md; regenerating a fixture to make a
failing comparison pass would turn the oracle into a mirror.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "data" / "parity_05537458.json"
P3B = ROOT / "tests" / "data" / "parity_p3b.json"
P175 = ROOT / "tests" / "data" / "parity_1_75.json"
P175B = ROOT / "tests" / "data" / "parity_1_75b.json"
P179 = ROOT / "tests" / "data" / "parity_1_79.json"
P182 = ROOT / "tests" / "data" / "parity_1_82.json"
P184 = ROOT / "tests" / "data" / "parity_1_84.json"
P1851 = ROOT / "tests" / "data" / "parity_1_85_1.json"
P186 = ROOT / "tests" / "data" / "parity_1_86.json"
P187 = ROOT / "tests" / "data" / "parity_1_87.json"
P188 = ROOT / "tests" / "data" / "parity_1_88.json"
P190 = ROOT / "tests" / "data" / "parity_1_90.json"
P191 = ROOT / "tests" / "data" / "parity_1_91.json"
P192 = ROOT / "tests" / "data" / "parity_1_92.json"

#: The pre-1.86 title bound, restored in the capture process for the scope
#: tests: every producer subset's `title` is the stored schema's again, and
#: the adjudicator's verdict rewrite is back to 90 with its old description.
_OLD_TITLE_BOUND = (
    "import copy, functools\n"
    "import metascience_agent.core.prompts as P\n"
    "_sub = P.producer_findings_schema.__wrapped__\n"
    "@functools.lru_cache(maxsize=None)\n"
    "def _old_sub(producer, figures=False):\n"
    "    s = _sub(producer, figures)\n"
    "    full = P.findings_schema_v2()['properties']['findings']['items']\n"
    "    s['properties']['findings']['items']['properties']['title'] = \\\n"
    "        copy.deepcopy(full['properties']['title'])\n"
    "    return s\n"
    "P.producer_findings_schema = _old_sub\n"
    "_adj = P.adjudication_schema.__wrapped__\n"
    "@functools.lru_cache(maxsize=None)\n"
    "def _old_adj():\n"
    "    s = _adj()\n"
    "    s['properties']['verdicts']['items']['properties']['title'] = {\n"
    "        'type': 'string', 'minLength': 8, 'maxLength': 90,\n"
    "        'description': 'Optional rewrite; the original is preserved as '\n"
    "                       'adjudication.title_was.'}\n"
    "    return s\n"
    "P.adjudication_schema = _old_adj\n")


def _capture(tmp_path, src_only_pythonpath: bool = False,
             title_bound_90: bool = False) -> dict:
    # The image package comes from its own installed checkout.
    roots = [ROOT / "src", ROOT / "copy_paste_detector" / "src"]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": os.pathsep.join([str(r) for r in roots]
                                         + [os.environ.get("PYTHONPATH", "")])}
    out = tmp_path / "capture.json"
    script = [str(ROOT / "tests" / "parity_capture.py"), str(out)]
    if src_only_pythonpath or title_bound_90:
        patch = ""
        if src_only_pythonpath:
            # The pre-1.85.1 server env: `<src>` alone, for the scope test.
            patch += (
                "import metascience_agent.agent as A, metascience_agent.llm_backend as lb\n"
                "old = lambda inherited=None: str(lb._pkg_root())\n"
                "A.forensic_pythonpath = lb.forensic_pythonpath = old\n")
        if title_bound_90:
            patch += _OLD_TITLE_BOUND
        script = ["-c", (
            "import runpy, sys\n" + patch +
            "sys.argv = sys.argv[1:]\n"
            "runpy.run_path(sys.argv[0], run_name='__main__')\n"), *script]
    proc = subprocess.run([sys.executable, *script], env=env, cwd=tmp_path,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return json.loads(out.read_text())


def test_default_run_matches_the_newest_oracle(tmp_path):
    got = _capture(tmp_path)
    want = json.loads(P192.read_text())
    assert set(got) == set(want) == {"claude", "codex", "grok"}
    for backend in want:
        for i, (g, w) in enumerate(zip(got[backend]["invocations"],
                                       want[backend]["invocations"])):
            assert g == w, f"{backend} invocation {i} ({w['stage']}) differs"
        assert got[backend] == want[backend], backend


#: Where a system prompt or an output schema rides, per backend. Everything
#: else in an invocation must be unchanged across Phase 3b.
_PROMPT_FLAGS = ("--append-system-prompt", "--json-schema")
_PROMPT_FILES = ("AGENTS.md", "schema.json")


def _without_prompts(capture: dict) -> dict:
    out = json.loads(json.dumps(capture))
    for backend in out.values():
        backend["prompt_sha256"] = "<PROMPTS>"
        for inv in backend["invocations"]:
            argv = inv["argv"]
            for i, a in enumerate(argv[:-1]):
                if a in _PROMPT_FLAGS:
                    argv[i + 1] = "<PROMPT>"
            for name in _PROMPT_FILES:
                if name in inv["files"]:
                    inv["files"][name] = "<PROMPT>"
    return out


def test_phase3b_changed_only_what_the_models_are_told():
    old = json.loads(FIXTURE.read_text())
    new = json.loads(P3B.read_text())
    for backend in old:
        # THE TWO DIFFERENCES NAMED BEFORE Phase 3b, carried forward: the
        # harness-written `pipeline` block on the findings document, and the
        # Codex skills override (2026-10-11).
        keys = new[backend]["document_keys"]
        assert "pipeline" in keys and "pipeline" not in old[backend]["document_keys"]
        old[backend]["document_keys"] = sorted(old[backend]["document_keys"] + ["pipeline"])
        if backend == "codex":
            from metascience_agent.llm_backend import CODEX_SKILLS_CONFIG
            assert CODEX_SKILLS_CONFIG not in json.dumps(old[backend])
            for inv in new[backend]["invocations"]:
                argv = inv["argv"]
                i = argv.index(CODEX_SKILLS_CONFIG)
                assert argv[i - 1] == "-c"
                del argv[i - 1:i + 1]
        # Grok carries its system prompt in a flag; no prompt file differs.
    a, b = _without_prompts(old), _without_prompts(new)
    for backend in a:
        for i, (x, y) in enumerate(zip(a[backend]["invocations"],
                                       b[backend]["invocations"])):
            assert x == y, f"{backend} invocation {i} changed beyond its prompts"
        assert a[backend] == b[backend], backend
    # ...and the prompts DID change, on every analyst invocation.
    assert old["claude"]["prompt_sha256"] != new["claude"]["prompt_sha256"]


def test_1_75_changed_only_what_the_models_are_told():
    """The 1.75 change (2026-10-14): the adjudicator's verdict bands are
    defined, and Grok's addendum says every problem must be filed. Against
    the Phase 3b oracle, only system prompts, output schemas and
    `prompt_sha256` may differ; Claude's analysts are byte-identical."""
    old = json.loads(P3B.read_text())
    new = json.loads(P175.read_text())
    a, b = _without_prompts(old), _without_prompts(new)
    for backend in a:
        for i, (x, y) in enumerate(zip(a[backend]["invocations"],
                                       b[backend]["invocations"])):
            assert x == y, f"{backend} invocation {i} changed beyond its prompts"
        assert a[backend] == b[backend], backend
    for o, n in zip(old["claude"]["invocations"], new["claude"]["invocations"]):
        if o["stage"] in ("tool_agent", "science_agent"):
            assert o == n, f"claude {o['stage']} changed"
    assert old["grok"]["invocations"][0] != new["grok"]["invocations"][0]


def test_1_75b_changed_only_prompts_and_the_flow_tool():
    """The parity-audit fixes (2026-10-14): rulebook rule 18 (a significance
    mark's comparison is a premise), rule 16's `also_reported` sentence, the
    science agent's flow steps, Grok's findings-writing section -- all system
    prompt -- and `check_flow_arithmetic`'s new `also_reported` parameter,
    which moves `registry_sha256` because the MCP tool definition changed.
    Against the 1.75 oracle nothing else may differ: no argv flag, output
    schema, user prompt, environment, allowlist, setting or channel."""
    old = json.loads(P175.read_text())
    new = json.loads(P175B.read_text())
    a, b = _without_prompts(old), _without_prompts(new)
    for backend in a:
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"]
        a[backend]["registry_sha256"] = b[backend]["registry_sha256"] = "<REGISTRY>"
        for i, (x, y) in enumerate(zip(a[backend]["invocations"],
                                       b[backend]["invocations"])):
            assert x == y, f"{backend} invocation {i} changed beyond its prompts"
        assert a[backend] == b[backend], backend
    # The output schemas did NOT change: only the --append-system-prompt.
    for o, n in zip(old["claude"]["invocations"], new["claude"]["invocations"]):
        i = o["argv"].index("--json-schema")
        assert o["argv"][i + 1] == n["argv"][i + 1], o["stage"]
    from metascience_agent import registry
    flow = next(t for t in registry.SPECS if t.name == "check_flow_arithmetic")
    assert "also_reported" in flow.description


def test_1_79_changed_only_prompts_and_the_grim_description():
    """1.79.0 (2026-10-16): `grim_check`'s MCP description says GRIM needs no
    scale maximum, and so does its guidance bullet in the tools agent's system
    prompt; the adjudicator prompt says how to act on a handoff note. That
    moves the tools agent's and the adjudicator's system prompts and
    `registry_sha256`, and nothing else: the science agent's invocation is
    byte-identical, and no argv flag, output schema, user prompt,
    environment, allowlist, setting or channel differs from the 1.75b
    oracle. (The docket's new `unchecked` section is user-prompt content;
    the capture's analysts file no `unchecked` entries, so it does not show
    here -- `tests/test_adjudicate.py::TestDocket` covers it.)"""
    old = json.loads(P175B.read_text())
    new = json.loads(P179.read_text())
    a, b = _without_prompts(old), _without_prompts(new)
    for backend in a:
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"]
        a[backend]["registry_sha256"] = b[backend]["registry_sha256"] = "<REGISTRY>"
        for i, (x, y) in enumerate(zip(a[backend]["invocations"],
                                       b[backend]["invocations"])):
            assert x == y, f"{backend} invocation {i} changed beyond its prompts"
        assert a[backend] == b[backend], backend
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if o["stage"] == "science_agent":
                assert o == n, f"{backend} science_agent changed"
    for o, n in zip(old["claude"]["invocations"], new["claude"]["invocations"]):
        i = o["argv"].index("--json-schema")
        assert o["argv"][i + 1] == n["argv"][i + 1], o["stage"]
    from metascience_agent import registry
    grim = next(t for t in registry.SPECS if t.name == "grim_check")
    assert "needs NO scale range" in grim.description


_NEW_182 = ("list_tables", "declare_table")


def test_1_82_changed_only_the_tool_agents_surface():
    """1.82.0 (2026-10-18): `list_tables` and `declare_table` join the tools
    agent's role, and its system prompt gains step 2a (declare every table;
    the harness checks and files GRIM). Against the 1.79 oracle: the tools
    agent's allowlist gains exactly those two tools and its system prompt
    changes; the MCP tool list it is configured with (Codex `-c`, AGENTS.md)
    follows; on Grok the other two roles DENY the two new tools by name; and
    `prompt_sha256` / `registry_sha256` move. Nothing else: no output schema
    (both are excluded from the technique enum, `NON_TECHNIQUE_TOOLS`), no
    user prompt, environment, setting or channel, and Claude's science agent
    and adjudicator invocations are byte-identical."""
    old = json.loads(P179.read_text())
    new = json.loads(P182.read_text())
    for backend in old:
        assert old[backend]["prompt_sha256"] != new[backend]["prompt_sha256"]
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"]
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if o["stage"] == "tool_agent":
                added = set(n["allowed_tools"]) - set(o["allowed_tools"])
                assert {a.split("__")[-1] for a in added} == set(_NEW_182)
                assert not set(o["allowed_tools"]) - set(n["allowed_tools"])
            else:
                assert o["allowed_tools"] == n["allowed_tools"], o["stage"]
            for k in o:
                if k not in ("argv", "files", "allowed_tools"):
                    assert o[k] == n[k], f"{backend} {o['stage']} {k}"
            if "--json-schema" in o["argv"]:
                i, j = o["argv"].index("--json-schema"), n["argv"].index("--json-schema")
                assert o["argv"][i + 1] == n["argv"][j + 1], f"{backend} {o['stage']} schema"
            if backend == "grok" and o["stage"] != "tool_agent":
                extra = [a for a in n["argv"] if a not in o["argv"]]
                assert sorted(extra) == sorted(
                    f"MCPTool(forensic_metascience__{t})" for t in _NEW_182)
            if backend == "claude" and o["stage"] != "tool_agent":
                assert o == n, f"claude {o['stage']} changed"
            if o["stage"] != "tool_agent":
                assert o["files"] == n["files"], f"{backend} {o['stage']} files"
        for k in old[backend]:
            if k not in ("invocations", "prompt_sha256", "registry_sha256"):
                assert old[backend][k] == new[backend][k], f"{backend} {k}"


def test_1_84_changed_only_the_tool_agents_user_prompt():
    """1.84.0 (2026-10-18): the tools agent's per-paper prompt names the
    table-declaration step and the paper directory (`agent.
    table_declarations_text`). Against the 1.82 oracle, on every backend, the
    tool agent's user prompt is the ONLY difference: no system prompt, schema,
    allowlist, argv, environment, setting or channel, and no other stage."""
    old = json.loads(P182.read_text())
    new = json.loads(P184.read_text())
    for backend in old:
        assert old[backend]["user_prompts"]["tool_agent"] != new[backend]["user_prompts"]["tool_agent"]
        a, b = json.loads(json.dumps(old[backend])), json.loads(json.dumps(new[backend]))
        a["user_prompts"]["tool_agent"] = b["user_prompts"]["tool_agent"] = "<USER PROMPT>"
        assert a == b, backend


def test_1_85_1_changed_only_the_childrens_pythonpath(tmp_path):
    """1.85.1 (2026-10-18): the forensic MCP server's env carries BOTH source
    roots of this tree (`llm_backend.forensic_pythonpath`), not `<src>` alone
    -- a pinned worktree run had resolved copy_paste_detector from the shared
    checkout and lost every tools agent. The MCP config is hashed in the
    capture, so the scope is proved by construction: the current tree with
    the OLD value restored captures the 1.84 oracle byte for byte, and with
    the new value captures the 1.85.1 oracle; and the two oracles differ.
    (Since 1.86 the capture also restores the old title bound; see the 1.86
    scope test.)"""
    old = json.loads(P184.read_text())
    new = json.loads(P1851.read_text())
    assert old != new
    # Since then 1.87.0 changed the tools agent's system prompt and 1.88.0
    # every role's (`test_1_87_...`, `test_1_88_...`), and both moved the
    # registry; with those masked, and the pre-1.86 title bound restored, the
    # old value captures the 1.84 oracle.
    assert (_mask_system_prompts(_capture(tmp_path, src_only_pythonpath=True,
                                          title_bound_90=True))
            == _mask_system_prompts(old))
    for backend in old:
        for k in old[backend]:
            if k != "invocations":
                assert old[backend][k] == new[backend][k], f"{backend} {k}"


def test_1_86_changed_only_the_title_bound_in_the_output_schemas(tmp_path):
    """1.86.0 (2026-10-18): a producer may submit a finding title up to
    `findings_v2.PRODUCER_TITLE_MAX` characters (the stored row is cut back to
    90 by the harness), and so may the adjudicator's rewrite -- 44 of 52
    StructuredOutput rejections in the p-value benchmark were titles just
    over 90. Proved by construction: the current tree with the OLD bound
    restored captures the 1.85.1 oracle byte for byte; and against it the
    1.86 oracle differs only in the output schema each invocation carries
    (`--json-schema` on Claude and Grok, `schema.json` on Codex)."""
    old = json.loads(P1851.read_text())
    new = json.loads(P186.read_text())
    assert old != new
    # Since 1.87.0/1.88.0 system prompts and the registry differ too (masked;
    # the output schemas this test is about are not).
    assert (_mask_system_prompts(_capture(tmp_path, title_bound_90=True))
            == _mask_system_prompts(old))
    for backend in old:
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if "--json-schema" in o["argv"]:
                i = o["argv"].index("--json-schema")
                assert o["argv"][i + 1] != n["argv"][i + 1], o["stage"]
                o["argv"][i + 1] = n["argv"][i + 1] = "<SCHEMA>"
            if "schema.json" in o["files"]:
                assert o["files"]["schema.json"] != n["files"]["schema.json"]
                o["files"]["schema.json"] = n["files"]["schema.json"] = "<SCHEMA>"
        assert old[backend] == new[backend], backend


def _mask_tool_agent_prompt(capture: dict) -> dict:
    """The capture with the tools agent's system prompt and both hashes masked."""
    out = json.loads(json.dumps(capture))
    for backend in out.values():
        backend["prompt_sha256"] = "<PROMPTS>"
        backend["registry_sha256"] = "<REGISTRY>"
        for inv in backend["invocations"]:
            if inv["stage"] != "tool_agent":
                continue
            argv = inv["argv"]
            i = argv.index("--append-system-prompt") if "--append-system-prompt" in argv else None
            if i is not None:
                argv[i + 1] = "<PROMPT>"
            if "AGENTS.md" in inv["files"]:
                inv["files"]["AGENTS.md"] = "<PROMPT>"
    return out


def test_1_87_changed_only_the_tool_agents_prompt_and_registry():
    """1.87.0 (2026-10-18; released on its branch as 1.86.0): the p tools take `p_relation` and check an EXACT
    printed p in both directions; `check_estimate_ci` honours a stated level.
    That changes six MCP tool definitions (`registry_sha256`) and the tools
    agent's system prompt (its guidance bullet for the p tools). Against the
    1.86 oracle nothing else differs: no output schema, user prompt,
    allowlist, environment, setting or channel, and the science agent and
    adjudicator invocations are byte-identical on every backend."""
    old = json.loads(P186.read_text())
    new = json.loads(P187.read_text())
    for backend in old:
        assert old[backend]["prompt_sha256"] != new[backend]["prompt_sha256"]
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"]
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if o["stage"] != "tool_agent":
                assert o == n, f"{backend} {o['stage']} changed"
    assert _mask_tool_agent_prompt(old) == _mask_tool_agent_prompt(new)
    from metascience_agent import registry
    for name in ("recalc_stat_to_p", "recalc_chi_squared", "recalc_anova",
                 "recalc_f_to_p", "recalc_independent_t", "check_regression"):
        assert "p_relation" in registry.BY_NAME[name].schema(), name


def _mask_system_prompts(capture: dict) -> dict:
    """The capture with EVERY role's system prompt and both hashes masked --
    output schemas, user prompts, argv and env stay compared in full."""
    out = json.loads(json.dumps(capture))
    for backend in out.values():
        backend["prompt_sha256"] = "<PROMPTS>"
        backend["registry_sha256"] = "<REGISTRY>"
        for inv in backend["invocations"]:
            argv = inv["argv"]
            if "--append-system-prompt" in argv:
                argv[argv.index("--append-system-prompt") + 1] = "<PROMPT>"
            if "AGENTS.md" in inv["files"]:
                inv["files"]["AGENTS.md"] = "<PROMPT>"
    return out


def test_1_88_changed_only_system_prompts_and_the_stat_to_p_definition():
    """1.88.0 (2026-10-18; released on its branch as 1.86.0):
    `recalc_stat_to_p` bounds an unprinted t or chi2 df instead of refusing --
    new `df_min`/`df_max` params and a new MCP description, which move
    `registry_sha256` -- and rulebook rule 4's degrees-of-freedom bullet says
    to omit `df` for that sweep, which every role's system prompt carries.
    Against the 1.87 oracle nothing else may differ: no output schema, user
    prompt, argv flag, environment, MCP config, allowlist, setting or channel."""
    old = json.loads(P187.read_text())
    new = json.loads(P188.read_text())
    for backend in old:
        assert old[backend]["prompt_sha256"] != new[backend]["prompt_sha256"]
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"]
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            assert o != n, f"{backend} {o['stage']}: the rulebook reaches every role"
    assert _mask_system_prompts(old) == _mask_system_prompts(new)
    from metascience_agent import registry
    spec = registry.BY_NAME["recalc_stat_to_p"]
    assert "OMIT `df`" in spec.description
    assert {"df_min", "df_max"} <= set(spec.schema())


def test_1_90_changed_only_the_p_tool_definitions():
    """1.90.0 (2026-10-18): the p tools hold a declared bound to its exact
    endpoint, take `p_adjustment` (a declared correction explains an
    under-claim) and, for the two that rebuild a test from summary statistics,
    `test_confirmed`; `recalc_stat_to_p` takes a fractional df. Six MCP tool
    definitions change, which moves `registry_sha256` and NOTHING ELSE against
    the 1.88 oracle: no system or user prompt, output schema, argv flag,
    environment, MCP config, allowlist, setting or channel. (The declared-
    correction prompt block appears only for a paper that declares one; the
    capture fixture does not.)"""
    old = json.loads(P188.read_text())
    new = json.loads(P190.read_text())
    for backend in old:
        assert old[backend]["registry_sha256"] != new[backend]["registry_sha256"], backend
        a, b = json.loads(json.dumps(old[backend])), json.loads(json.dumps(new[backend]))
        a["registry_sha256"] = b["registry_sha256"] = "<REGISTRY>"
        assert a == b, backend
    from metascience_agent import registry
    for name in ("recalc_stat_to_p", "recalc_f_to_p", "recalc_anova",
                 "recalc_independent_t", "recalc_chi_squared", "check_regression"):
        assert "p_adjustment" in registry.BY_NAME[name].schema(), name
    for name in ("recalc_anova", "recalc_independent_t"):
        assert "test_confirmed" in registry.BY_NAME[name].schema(), name


def test_1_91_changed_only_the_tools_agent_system_prompt():
    """1.91.0 (2026-10-18): the tools prompt states the accounting rule for
    every backend (a suspicious result is a problem row, an `unchecked` entry
    with a reason, or an undecided row -- not a pass row) and stops calling an
    unstated hypothesis status a finding. Against the 1.90 oracle only the
    tools agent's system prompt moves, on every backend; the science agent and
    adjudicator invocations, the registry and every schema are identical. (The
    dedup, the unaccounted record and the recovery pass are post-processing
    and do not appear in an invocation.)"""
    old = json.loads(P190.read_text())
    new = json.loads(P191.read_text())
    for backend in old:
        assert old[backend]["prompt_sha256"] != new[backend]["prompt_sha256"], backend
        assert old[backend]["registry_sha256"] == new[backend]["registry_sha256"], backend
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if o["stage"] == "tool_agent":
                assert o != n, backend
            else:
                assert o == n, f"{backend} {o['stage']}"
    assert _mask_system_prompts(old) == _mask_system_prompts(new)


def test_1_92_changed_only_the_tools_agent_system_prompt():
    """1.92.0 (2026-10-18): internal contradictions belong to the proofreading
    agent and the tools agent hands them off (a figure that disagrees with the
    text excepted); `not_computational` is narrowed to how one statistic is
    written. Against the 1.91 oracle only the tools agent's system prompt
    moves; the proofreading agent and adjudicator are byte-identical. The
    tools_only configuration note also changes, but the default capture runs
    the complete review, which carries no note."""
    old = json.loads(P191.read_text())
    new = json.loads(P192.read_text())
    for backend in old:
        assert old[backend]["prompt_sha256"] != new[backend]["prompt_sha256"], backend
        assert old[backend]["registry_sha256"] == new[backend]["registry_sha256"], backend
        for o, n in zip(old[backend]["invocations"], new[backend]["invocations"]):
            if o["stage"] == "tool_agent":
                assert o != n, backend
            else:
                assert o == n, f"{backend} {o['stage']}"
    assert _mask_system_prompts(old) == _mask_system_prompts(new)
