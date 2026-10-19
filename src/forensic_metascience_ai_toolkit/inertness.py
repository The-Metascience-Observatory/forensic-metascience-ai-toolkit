"""Find machinery that looks like it works and does not.

THE BUG CLASS, named. Over the last weeks the same defect has been found by
hand, repeatedly, in unrelated parts of this codebase. Every instance has the
same shape: SOMETHING THAT APPEARS TO DO WORK BUT CANNOT, OR DOES NOT, AND
WHOSE FAILURE MODE IS SILENCE. A short and entirely real list:

  * a regex whose leading `\\b` became a literal backspace (0x08) through a
    non-raw string, so it matched nothing while reading correctly, and reviews
    sailed into a bucket that existed to exclude them;
  * `unbacked_accusations()`, whose own docstring says "A run linter must fire
    on this list", called from nothing but its own tests;
  * a `--figures` CLI flag that announced a pass which never ran;
  * `not_run` records generated per (cell, check) and consumed by nobody, so a
    table whose every cell was refused still read as "checked";
  * GRIM running in a regime where the check CANNOT fail and returning
    `consistent` -- 90 of 159 archived calls, every one presented as a pass;
  * `paper_text` swallowing every extraction crash, so four of its five
    consumers published a false all-clear.

WHY A SCANNER RATHER THAN MORE VIGILANCE. Each of those was found by accident,
by someone reading nearby code for another reason. That is not a process. The
defect is mechanically recognisable in most of its forms, and the ones that are
not mechanical are at least ENUMERABLE -- which is what this module does: it
reports what it can prove, and hands the rest to a reader as a worklist rather
than pretending the list is empty.

-----------------------------------------------------------------------------
WHAT THIS MODULE PROMISES, AND WHAT IT REFUSES TO DO
-----------------------------------------------------------------------------
The cardinal rule of this project is that a FALSE ACCUSATION is the worst
output. A linter is not exempt: one that cries wolf is switched off, and a
switched-off linter enforces nothing -- which is the very defect it exists to
catch, reproduced one level up. So every detector here:

  * reports `certain` only when the finding is a PROVEN property of the code
    (the regex cannot match; the name is referenced nowhere), and `worklist`
    when it is a candidate a human must settle;
  * carries an `evidence` string that a reader can check in one step;
  * has a NAMED false-positive shape in its docstring, and a positive-control
    test that constructs the defect and asserts the detector fires. A detector
    that cannot fire returns zero exactly as convincingly as a clean codebase,
    and this repo has already shipped that mistake once.

Nothing here is severity-graded, and nothing here is about a PAPER. These are
defects in our own machinery.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SRC = Path(__file__).resolve().parent
REPO = SRC.parent.parent

#: Directories that never hold a review and are expensive to walk. The paper
#: corpora are the whole point of the exclusion: 516 MB of PDFs and markdown,
#: none of it a run record.
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv",
              "cerebrolysin_papers", "fixtures"}




@dataclass
class Finding:
    """One piece of suspect machinery.

    `confidence` is `certain` for a proven property of the code and `worklist`
    for a candidate. The distinction is the whole ethic of the module: a
    worklist entry is an invitation to look, never a claim that something is
    broken.
    """
    detector: str
    confidence: str          # "certain" | "worklist"
    where: str               # path:line
    what: str                # one line, the claim
    evidence: str            # how to check it in one step
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"detector": self.detector, "confidence": self.confidence,
                "where": self.where, "what": self.what,
                "evidence": self.evidence, **({"extra": self.extra} if self.extra else {})}


# ---------------------------------------------------------------------------
# Shared parsing
# ---------------------------------------------------------------------------

def _py_files(root: Path, include_init: bool = False) -> list[Path]:
    """Our Python, without walking the paper corpora.

    `rglob` from the repo root spends forty seconds crossing 516 MB of PDFs and
    extracted markdown to find a few hundred `.py` files. `_SKIP_DIRS` is the
    same exclusion the archive walker uses and for the same reason.

    `include_init` EXISTS BECAUSE THE DEFAULT WAS WRONG IN THE DANGEROUS
    DIRECTION. `__init__.py` was excluded so the definition scanners would not
    trip over re-export blocks -- but `find_unconsumed_definitions` built its
    REFERENCE corpus from this same list, so a name whose only caller was an
    `__init__.py` re-export was reported as consumed by nobody. Its docstring
    claimed that shape was handled. Four of the 33 findings in the 2026-08-11
    triage were exactly this, and a linter that invents dead code is a linter
    that gets ignored. The reference corpus now passes `include_init=True`;
    the detectors that look for defects IN a file keep the old scope, because
    an `__init__.py` holds imports and nothing else here."""
    out: list[Path] = []
    stack = [root]
    if root == SRC:
        standalone = REPO / "metascience-observatory-image-analysis" / "src"
        if standalone.is_dir():
            stack.append(standalone)
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:  # noqa: PERF203
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in _SKIP_DIRS:
                    stack.append(e)
            elif e.suffix == ".py" and (include_init or e.name != "__init__.py"):
                out.append(e)
    return sorted(out)


def _parse(path: Path) -> tuple[ast.Module | None, str]:
    try:
        text = path.read_text(encoding="utf-8")
        return ast.parse(text), text
    except (OSError, SyntaxError):
        return None, ""


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# 1. Degenerate regexes -- the pattern that cannot match
# ---------------------------------------------------------------------------

#: Control characters that a regex literal essentially never wants and that
#: arrive almost exclusively from `\b`, `\a`, `\f`, `\v`, `\t` being
#: interpreted by PYTHON before `re` ever sees them -- i.e. from a non-raw
#: string. `\t` is excluded: a literal tab in a pattern is occasionally
#: deliberate, and flagging it would be the noise that gets a linter ignored.
_ESCAPE_ACCIDENTS = {
    "\x07": r"\a (alarm) -- almost certainly meant \A (start of string)",
    "\x08": r"\b (backspace) -- almost certainly meant \b (word boundary)",
    "\x0b": r"\v (vertical tab) -- almost certainly meant \v as a class",
    "\x0c": r"\f (form feed)",
}


def _string_literals_with_lines(tree: ast.Module) -> Iterable[tuple[str, int]]:
    """Every string constant, with its line. Implicit concatenation of adjacent
    literals is already folded into one node by the parser, which is exactly
    what we want: the accident happens in whichever fragment was not raw."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value, node.lineno


#: Names whose argument is a regex. Used to keep the scan to strings that are
#: actually compiled, so a docstring mentioning a backspace is not a finding.
_RE_CALLS = {"compile", "search", "match", "fullmatch", "findall",
             "finditer", "sub", "subn", "split"}


def _regex_literals(tree: ast.Module) -> Iterable[tuple[str, int]]:
    """String literals in the pattern position of an `re.*` call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else "")
        if name not in _RE_CALLS or not node.args:
            continue
        # THE RECEIVER MUST BE `re`. `split`, `match` and `sub` are all string
        # methods too, and `"a|b".split("|")` is not a regex -- it was three of
        # the four `empty_regex_alternative` findings on the live tree, i.e. the
        # detector was mostly reporting ordinary string splitting as a broken
        # pattern. A bare-name call (`compile(...)` after `from re import *`)
        # is accepted; an attribute call must be on something spelled `re`.
        if isinstance(fn, ast.Attribute):
            recv = fn.value
            if not (isinstance(recv, ast.Name) and recv.id == "re"):
                continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            yield first.value, first.lineno


def find_degenerate_regexes(root: Path | None = None) -> list[Finding]:
    """Regexes that cannot match what their author plainly meant.

    THE REAL INSTANCE: `eval/corpus_expansion.py`'s review-title exclusion was
    assembled through a non-raw string, so its leading `\\b` became 0x08 and the
    whole first alternative required a control character no title contains. It
    matched nothing, looked correct, and let reviews into a corpus of primary
    research.

    FALSE POSITIVE SHAPE: a pattern that deliberately matches a control
    character -- a parser for terminal output, say, or a check for stray form
    feeds in extracted PDF text. Those exist. They are rare, they are obvious on
    sight, and the finding names the exact character so the reader settles it in
    one step. Reported `certain` because the property is proven (the character
    IS in the compiled pattern); whether it was intended is the reader's call,
    and the `what` line says so.
    """
    out: list[Finding] = []
    for path in _py_files(root or REPO):
        tree, _ = _parse(path)
        if tree is None:
            continue
        for pattern, line in _regex_literals(tree):
            for ch, why in _ESCAPE_ACCIDENTS.items():
                if ch in pattern:
                    at = pattern.index(ch)
                    out.append(Finding(
                        detector="degenerate_regex", confidence="certain",
                        where=f"{_rel(path)}:{line}",
                        what=(f"regex contains a literal {ch!r} at offset {at}: "
                              f"{why}. Unless a control character is genuinely "
                              "intended, this alternative can never match."),
                        evidence=f"pattern repr: {pattern!r}",
                        extra={"char": ch, "offset": at}))
    return out


def find_unanchorable_alternatives(root: Path | None = None) -> list[Finding]:
    """Alternations with an EMPTY branch, which make the whole pattern match
    everywhere and therefore test nothing.

    `a|b|` matches the empty string at every position. As a guard it passes
    always; as a filter it excludes everything. Both are silent.

    FALSE POSITIVE SHAPE: an intentionally-optional group written as `(x|)`
    rather than `x?`. Legal, and occasionally clearer. Reported `worklist`, not
    `certain`, for that reason.
    """
    out: list[Finding] = []
    empty_branch = re.compile(r"\((?:\?:)?[^()]*\|\)|\|\)")
    for path in _py_files(root or REPO):
        tree, _ = _parse(path)
        if tree is None:
            continue
        for pattern, line in _regex_literals(tree):
            if empty_branch.search(pattern) or pattern.endswith("|"):
                out.append(Finding(
                    detector="empty_regex_alternative", confidence="worklist",
                    where=f"{_rel(path)}:{line}",
                    what="an alternation has an empty branch, so the pattern "
                         "matches the empty string everywhere and discriminates "
                         "nothing",
                    evidence=f"pattern repr: {pattern!r}"))
    return out


# ---------------------------------------------------------------------------
# 2. Defined, tested, consumed by nobody
# ---------------------------------------------------------------------------

#: Ways a name legitimately reaches a caller without appearing as an identifier
#: in another module. Each is a REAL mechanism in this repo, and each would
#: otherwise generate a false positive.
_INDIRECT_USE_NOTE = (
    "Names can be reached without an import: the tool registry dispatches by "
    "string, typer/CLI decorators register functions, and the MCP server "
    "exposes callables by name. All three are searched as STRINGS before a "
    "name is reported."
)


def _defined_names(tree: ast.Module) -> list[tuple[str, int, str]]:
    """(name, line, kind) for public module-level defs, classes and constants."""
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                out.append((node.name, node.lineno, "function"))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                out.append((node.name, node.lineno, "class"))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_") \
                        and t.id.isupper():
                    out.append((t.id, node.lineno, "constant"))
    return out


def _docstring_constants(tree: ast.Module) -> set[int]:
    """`id()` of every string Constant that is a module/class/function docstring."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            out.add(id(body[0].value))
    return out


def _code_uses(tree: ast.Module, ident: re.Pattern) -> Counter:
    """Identifier occurrences in CODE -- not in comments, not in docstrings.

    WHY THIS IS NOT `ident.findall(source)`. It was, and prose satisfied it.
    `own_uses` is the gate that decides a name is used where it was defined, so
    a name mentioned twice in its own module's COMMENTS scored as consumed and
    never reached the report. Three genuinely uncalled functions hid behind
    exactly that -- `recognition_hits`, `sigma_from_geometry` and
    `blinding.verify` -- and the first of those is the output half of the
    blinding check, i.e. the measurement the module's own docstring calls the
    one irreducible risk. A detector that a written explanation can silence is
    worse than none, because the explanation is likeliest to exist precisely
    where somebody once knew the wiring was missing.

    NON-DOCSTRING string literals still count. The tool registry dispatches by
    string; `BY_NAME["statcheck"]` is a real call and must not be read as dead.
    """
    docs = _docstring_constants(tree)
    uses: Counter = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            uses[node.id] += 1
        elif isinstance(node, ast.Attribute):
            uses[node.attr] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            uses[node.name] += 1
        elif isinstance(node, ast.arg):
            uses[node.arg] += 1
        elif isinstance(node, ast.keyword) and node.arg:
            uses[node.arg] += 1
        elif isinstance(node, ast.alias):
            uses[node.name.split(".")[0]] += 1
            if node.asname:
                uses[node.asname] += 1
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docs):
            for tok in ident.findall(node.value):
                uses[tok] += 1
    return uses


def find_unconsumed_definitions(root: Path | None = None,
                                tests: Path | None = None) -> list[Finding]:
    """Public names in `src/` that only their own module and the tests mention.

    THE REAL INSTANCE: `unbacked_accusations()` -- whose docstring says "A run
    linter must fire on this list" -- was called from nothing but its own tests
    while 17 of 21 archived runs sat beside a BREACH verdict and every one
    exited 0. Tested and inert are not opposites; a green test on an unwired
    function is the most convincing possible disguise.

    FALSE POSITIVE SHAPES, all of them real here and all handled:
      * dispatched by string (the tool registry) -- the whole repo is searched
        for the name as a quoted string, not only as an identifier;
      * registered by decorator (typer commands, MCP tools) -- the definition
        site is checked for decorators;
      * re-exported through `__init__.py` for external callers.
    Because those escapes exist and cannot all be proven absent, EVERY finding
    here is `worklist`. This detector never claims something is dead; it claims
    nobody in this repository calls it.
    """
    root = root or (SRC)
    tests = tests or (REPO / "tests")
    # TWO LISTS, DELIBERATELY. Definitions are looked for in real modules; the
    # reference corpus must also include `__init__.py`, because a re-export is
    # how a name reaches an external caller and reading it as silence is what
    # made four of the 33 findings wrong.
    files = _py_files(root)
    ref_files = _py_files(root, include_init=True)

    # TOKENISE ONCE, LOOK UP PER NAME. The first version compiled one regex per
    # public name and ran it over every other file plus a concatenation of every
    # `.md`/`.json` in the repository -- which here includes a 516 MB corpus of
    # papers, so the scan did not finish inside ten minutes. Identifiers are
    # word-shaped, so a single tokenisation into a set answers the same question
    # in one pass, and the reference corpus is bounded to the places a name can
    # plausibly be dispatched from.
    ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    def tokens(paths: Iterable[Path], cap: int = 4_000_000) -> set[str]:
        seen: set[str] = set()
        for p in paths:
            try:
                if p.stat().st_size > cap:
                    continue
                seen.update(ident.findall(p.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):  # noqa: PERF203
                continue
        return seen

    def code_tokens(p: Path) -> set[str]:
        """Identifiers a `.py` file USES, not ones it talks about.

        THE PROSE SUPPRESSION IS CROSS-MODULE TOO, and worse there. A comment
        in module B naming a function in module A is not a call, and this repo
        writes long comments: `sigma_from_geometry` was suppressed by a single
        mention in `extraction/ocr.py`'s module docstring, and `recognition_hits`
        was suppressed by the docstring in THIS FILE that explains why it was
        being missed. A linter that its own explanation silences is the exact
        failure mode it was built to find, so the reference corpus is parsed,
        not grepped."""
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return set()
        try:
            return set(_code_uses(ast.parse(text), ident))
        except SyntaxError:
            return set(ident.findall(text))   # fail toward silence, not noise

    src_text = {p: p.read_text(encoding="utf-8") for p in files}
    per_file_tokens = {p: code_tokens(p) for p in ref_files}
    test_tokens: set[str] = set()
    if tests.exists():
        for p in tests.rglob("*.py"):
            test_tokens |= code_tokens(p)
    # Where a name can be reached WITHOUT an import: the prompts (the model is
    # told tool names), the registry snapshots, packaging metadata, and the
    # project's own docs. Deliberately NOT the paper corpus -- a tool name
    # appearing inside somebody's PDF text is not a caller.
    other_paths: list[Path] = []
    for d in ("src/forensic_metascience_ai_toolkit/core/prompts", "src/forensic_metascience_ai_toolkit/schema", "docs"):
        p = REPO / d
        if p.is_dir():
            other_paths.extend(q for q in p.rglob("*") if q.is_file())
    other_paths.extend(q for q in REPO.glob("*.md") if q.is_file())
    other_paths.extend(q for q in REPO.glob("*.toml") if q.is_file())
    other_paths.extend(q for q in REPO.glob("*.cfg") if q.is_file())
    other_tokens = tokens(other_paths)

    out: list[Finding] = []
    for path, text in src_text.items():
        tree, _ = _parse(path)
        if tree is None:
            continue
        decorated = {n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                       ast.ClassDef)) and n.decorator_list}
        # USES INSIDE THE DEFINING MODULE COUNT, and getting this wrong is what
        # made the first version of this detector useless: keyed on "referenced
        # by no OTHER module" it returned 232 candidates, essentially all of them
        # ordinary module-local constants like `PARTIAL_COVERAGE_NOTE`, which
        # `agent.py` uses twice a hundred lines further down. A name used where
        # it was defined is not inert; it is scoped. The real signal is a name
        # referenced NOWHERE beyond the line that creates it.
        own_uses = _code_uses(tree, ident)
        for name, line, kind in _defined_names(tree):
            if name in decorated:
                continue                      # registered by decorator
            # One occurrence is the definition itself. A class or function also
            # spends one on its own name; anything more is a use.
            if own_uses.get(name, 0) > 1:
                continue
            if any(name in toks for p2, toks in per_file_tokens.items()
                   if p2 != path):
                continue
            if name in other_tokens:
                continue                      # named in a prompt/config/doc
            in_tests = name in test_tokens
            out.append(Finding(
                detector="unconsumed_definition", confidence="worklist",
                where=f"{_rel(path)}:{line}",
                what=(f"public {kind} `{name}` is referenced by no other module"
                      + (" -- only by tests" if in_tests
                         else " and by no test either")),
                evidence=(f"grep -rn '\\b{name}\\b' src/ tests/ | grep -v "
                          f"'{path.name}'"),
                extra={"kind": kind, "referenced_in_tests": in_tests,
                       "note": _INDIRECT_USE_NOTE}))
    return out


# ---------------------------------------------------------------------------
# 3. Swallowed failure -- the except block that records nothing
# ---------------------------------------------------------------------------

#: Calls that constitute RECORDING a failure rather than discarding it. A
#: handler that does any of these is doing its job, however broad its `except`.
_RECORDING = ("append", "warn", "warning", "error", "log", "print", "raise",
              "console", "record", "setdefault", "add", "update", "problems")


#: Catches that hide an UNKNOWN failure. Everything else -- `except ValueError`
#: around a `float()`, `except KeyError` around a lookup -- is a parser, not a
#: swallow: the exception type IS the semantic answer, and returning `None`
#: states it completely.
_BROAD = {"Exception", "BaseException"}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """True for `except:`, `except Exception:`, `except BaseException:`.

    THE DISTINCTION THIS DRAWS, and it took a false-positive round to find it.
    Keyed on "discards and records nothing" alone, the detector returned 47
    `certain` findings, and the ones I checked were all of this shape:

        try:
            f = float(s)
        except (TypeError, ValueError):
            return None

    Nothing is hidden there. `float("abc")` failing MEANS "not a number", the
    caller gets that answer, and no information is lost. The `paper_text` bug --
    the reason this detector exists -- was `except Exception`, which also
    swallows a MemoryError, a decoder crash and a bug in our own code, and
    reports all of them as an empty paper.
    """
    t = handler.type
    if t is None:                       # bare `except:`
        return True
    names = [t] if not isinstance(t, ast.Tuple) else list(t.elts)
    return any(isinstance(n, ast.Name) and n.id in _BROAD for n in names)


def find_swallowed_failures(root: Path | None = None) -> list[Finding]:
    """`except` blocks that discard the exception AND record nothing anywhere.

    THE REAL INSTANCE: `paper_text` swallowed every extraction crash and
    returned "", so four of its five consumers reported a clean result on a
    paper they had never read. The bug is not the broad `except` -- this
    pipeline deliberately guards paid analyses so a bookkeeping error cannot
    destroy a completed run. The bug is a handler that leaves NO TRACE, because
    then nobody can tell a paper with no problems from a paper we failed to
    open.

    FALSE POSITIVE SHAPE: a genuine "absence is the answer" probe -- e.g.
    `try: import x except ImportError: available = False`. That assigns a value
    the caller inspects, so the failure IS recorded, in a variable. Handlers
    that assign to a name are therefore not reported, and only `pass` or a bare
    constant `return` counts as a discard.
    """
    out: list[Finding] = []
    for path in _py_files(root or SRC):
        tree, _ = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not _is_broad(node):
                continue
            body = node.body
            # Discard shapes: `pass`, or a return of a literal, and nothing else.
            discards = (
                len(body) == 1
                and (isinstance(body[0], ast.Pass)
                     or (isinstance(body[0], ast.Return)
                         and (body[0].value is None
                              or isinstance(body[0].value, ast.Constant)
                              or (isinstance(body[0].value, (ast.List, ast.Dict,
                                                             ast.Tuple))
                                  and not getattr(body[0].value, "elts",
                                                  getattr(body[0].value, "keys", []))))))
            )
            if not discards:
                continue
            seg = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
            if any(k in seg for k in _RECORDING):
                continue
            # A comment inside or immediately above the handler is this repo's
            # convention for a deliberate guard. Its presence does not make the
            # handler safe, but it does mean somebody decided -- so it drops to
            # a worklist entry rather than a flat finding.
            src_lines = path.read_text(encoding="utf-8").splitlines()
            window = src_lines[max(0, node.lineno - 4):node.lineno + 3]
            explained = any(l.strip().startswith("#") for l in window)
            out.append(Finding(
                detector="swallowed_failure",
                confidence="worklist" if explained else "certain",
                where=f"{_rel(path)}:{node.lineno}",
                what=("an exception is discarded and nothing records that it "
                      "happened, so a caller cannot tell failure from a clean "
                      "result" + (" (a comment nearby suggests this was a "
                                  "decision -- check that it was)" if explained
                                  else "")),
                evidence=f"sed -n '{max(1, node.lineno - 2)},{node.lineno + 4}p' "
                         f"{_rel(path)}"))
    return out


# ---------------------------------------------------------------------------
# 4. Checks with no power -- the dynamic half
# ---------------------------------------------------------------------------

def _archive_files(root: Path, name: str = "findings.v2.json") -> list[Path]:
    """Run records, found without walking the paper corpora."""
    out: list[Path] = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:  # noqa: PERF203
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in _SKIP_DIRS:
                    stack.append(e)
            elif e.name == name:
                out.append(e)
    return out


def find_constant_outcome_checks(archive: Path | None = None,
                                 min_calls: int = 12) -> list[Finding]:
    """Tools whose archived calls returned ONE outcome, every time.

    THE REAL INSTANCE: GRIM was called 159 times in the archive and 90 of those
    calls sat in a regime where the check mathematically cannot fail -- every
    one returned `consistent` and was presented to a reader as a pass. A check
    that has never once returned anything else has not been shown to work; it
    has been shown to be silent, and the two are indistinguishable from the
    outside.

    NOT AN ACCUSATION, AND THE THRESHOLD SAYS SO. Many checks SHOULD almost
    always pass -- that is what a clean corpus looks like. The finding is a
    prompt to ask "could this ever have failed on these inputs?", which is the
    question `discriminating_power` answers for the GRIM family and which most
    tools cannot yet answer for themselves. `min_calls` keeps a tool that ran
    three times out of the report entirely.
    """
    archive = archive or REPO
    outcomes: dict[str, Counter] = {}
    # Bounded on purpose: `rglob` over the whole repo walks a 516 MB paper
    # corpus to find a few dozen review directories, and the walk itself is the
    # cost. Reviews live beside the papers they are about, in directories whose
    # names end `_review`/`forensic_review`, plus `eval/` and `runs/`.
    for f in sorted(_archive_files(archive)):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items = data.get("findings") if isinstance(data, dict) else data
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            # What the TOOL returned, not the adjudicated 1-9 rung: a v2 row
            # carries the tool's own word in `tool_verdict`, and a row with no
            # tool verdict is counted by its outcome.
            tool = str(it.get("technique") or it.get("tool") or "")
            tv = it.get("tool_verdict") if isinstance(it.get("tool_verdict"), dict) else {}
            sev = str(tv.get("severity") or it.get("outcome") or "")
            if tool and sev:
                outcomes.setdefault(tool, Counter())[sev] += 1

    out: list[Finding] = []
    for tool, counts in sorted(outcomes.items()):
        n = sum(counts.values())
        if n < min_calls or len(counts) > 1:
            continue
        only = next(iter(counts))
        out.append(Finding(
            detector="constant_outcome_check", confidence="worklist",
            where=f"archive:{tool}",
            what=(f"`{tool}` returned `{only}` on all {n} archived calls. It may "
                  "be correct and the corpus clean -- or the check may have had "
                  "no power to return anything else on these inputs."),
            evidence=(f"grep -rl '\"technique\": \"{tool}\"' --include=findings.v2.json ."),
            extra={"n_calls": n, "only_outcome": only}))
    return out


# ---------------------------------------------------------------------------
# 5. Prompt-law with no enforcement
# ---------------------------------------------------------------------------

#: Sentences in the prompts that state a HARD rule. Extracted so the set can be
#: read as a checklist against the Python that is supposed to enforce them.
_RULE = re.compile(
    r"^[^\n]*\b(?:MUST|NEVER|may not|must never|is forbidden|do not|"
    r"cannot|caps? at|no \w+ (?:survives|reaches))\b[^\n]*$",
    re.M)


def find_unenforced_prompt_rules(prompts: Path | None = None) -> list[Finding]:
    """Imperative rules in the prompts, listed against the code that enforces
    them -- or against nothing.

    THE REAL INSTANCE: `stage2_editorial.md` had told the model since forever
    that a hand-worked finding may not reach `impossible`. Nothing enforced it.
    Measured over 23 runs it leaked twice, and both leaks were at the top of the
    severity ladder, which is the only place the rule matters. The clamp now
    exists; the rule sat unenforced for months because nobody had a list.

    THIS DETECTOR CANNOT DECIDE, and does not pretend to. Whether a rule is
    enforced is a judgement about meaning, not a property of the text. It
    produces a WORKLIST: every hard rule in the prompts, with the identifiers
    that look related, so a reviewer can walk it. Its value is that the list
    exists at all -- prompt-law is invisible precisely because it lives in
    English, in a file nobody greps.
    """
    out: list[Finding] = []
    if prompts is None:
        # Every prompt file, wherever it lives (`prompts.prompt_files`): the
        # agents' prompts moved into their module folders on 2026-10-15, and
        # a glob of `prompts/` alone would have stopped seeing them.
        from .core.prompts import prompt_files
        md_files = prompt_files()
    elif prompts.exists():
        md_files = sorted(prompts.glob("*.md"))
    else:
        return out
    code = "\n".join(p.read_text(encoding="utf-8") for p in _py_files(SRC))
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        for m in _RULE.finditer(text):
            line = " ".join(m.group(0).split())
            if len(line) < 30 or line.lstrip().startswith(("|", ">")):
                continue
            lineno = text[:m.start()].count("\n") + 1
            # Identifiers a rule mentions in backticks are the cheapest possible
            # link to the code that might enforce it.
            ticks = re.findall(r"`([a-z_][a-z0-9_]{3,})`", line)
            enforced = [t for t in ticks if re.search(rf"\b{re.escape(t)}\b", code)]
            out.append(Finding(
                detector="prompt_rule", confidence="worklist",
                where=f"{_rel(md)}:{lineno}",
                what=f"hard rule stated to the model: {line[:150]}",
                evidence=("identifiers it names that exist in the code: "
                          + (", ".join(enforced) if enforced
                             else "NONE -- nothing obvious enforces this")),
                extra={"names_code": bool(enforced)}))
    return out


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------

#: Keys whose consumer is a human, a model, or another process, so a code read
#: is not expected. Each needs its reason, for the same purpose `CLI_ONLY`
#: serves one file over: a deliberate exemption and a forgotten one look
#: identical in the source.
_CONSUMED_ELSEWHERE = {
    "note": "prose for the reader; every module writes one",
    "why": "prose for the reader",
    "why_not": "prose for the reader",
    "evidence": "prose for the reader",
    "reason": "prose for the reader",
    "detail": "prose for the reader",
    "help": "prose for the reader",
    "text": "the model reads tool results as text",
    "content": "the MCP envelope; the model reads it",
}


def find_write_only_keys(root: Path | None = None) -> list[Finding]:
    """Dict keys written by this package and read by nothing, anywhere.

    THE FAMILY THIS WHOLE MODULE EXISTS FOR, and the one shape it could not
    see. `unconsumed_definition` finds an unused NAME. This finds a computed
    ANSWER stored under a key nobody reads -- which is how every expensive
    defect of 2026-08-20 happened:

      * docling's `column_header` was set and discarded, so every stacked table
        header was read wrong;
      * JATS `image_only` was set and discarded, so 265 table cells were thrown
        away on two papers;
      * `result_truncated`, in the code's own words, was "computed and stored
        in this ledger for months and read by no renderer";
      * `exhaustive_checks` held 265 harness-aimed duplication comparisons and
        had ONE occurrence in the tree -- its write;
      * `predictor_disagrees` was recorded by a comment promising "It is now
        recorded", and rendered a report saying 8 of 24 were checked and 24
        were waiting.

    A KEY IS ONLY REPORTED WHEN ITS SOLE OCCURRENCE IN THE TREE IS ITS WRITE.
    The read side is checked by raw text across `src`, `tests`, `webapp` and
    the prompts -- not by AST -- because a real consumer may be TypeScript, an
    embedded viewer script inside a Python string, a markdown prompt, or a JSON
    schema. `bundle.py` alone carries roughly 720 lines of JavaScript inside
    string literals, and an AST-only reader would accuse three keys that page
    genuinely reads.

    `worklist`, never `certain`. THE FALSE POSITIVE: a key read through
    `**kwargs`, a variable subscript, or by a human reading a JSON artefact --
    `harness_sweep` and `ledger_problems` are both written into the report and
    register and read by people, and no static rule can see that. This invites
    a look and never asserts a defect.

    AND IT CAN BE BLINDED BY ITS OWN TEST. The read side is raw text, so naming
    a key in a test file counts as an occurrence and the finding disappears.
    Measured: asserting `quote_haystack_error` by name dropped the count from 20
    to 19 and made the assertion fail against itself. Tests for this detector
    must assert its METHOD, never a specific key.
    """
    root = root or SRC
    tree_roots = [root]
    if root == SRC:
        tree_roots.append(REPO / "metascience-observatory-image-analysis")
    for extra in (root.parent.parent / "tests", root.parent.parent / "webapp"):
        if extra.is_dir():
            tree_roots.append(extra)

    writes: dict[str, tuple[str, int]] = {}
    for path in _py_files(root):
        # A TOOL RESULT IS READ BY THE MODEL, NOT BY PYTHON. `registry` returns
        # every tool's result as `json.dumps(result)` inside an MCP text block,
        # so each key in a `tools/*` payload has a reader -- one that no static
        # analysis can see. Including them accused `fisher_odds_ratio`,
        # `achievable_t_interval` and a dozen more that the model reads on every
        # call.
        # `image_forensics/` holds `analyze_paper_images`, a registered tool
        # that moved out of `tools/`; the exemption follows the tool.
        if "tools" in path.parts or "image_forensics" in path.parts:
            continue
        tree, _src = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            # d["k"] = ...
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if (isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.slice, ast.Constant)
                            and isinstance(tgt.slice.value, str)):
                        writes.setdefault(tgt.slice.value, (_rel(path), tgt.lineno))
            # DICT LITERALS ARE NOT IN SCOPE, and that is what makes this
            # usable. Including them produced 336 worklist items dominated by
            # data tables and tool-result payloads -- LaTeX symbol maps
            # (`Delta`, `Omega`), env-var names (`TORCHDYNAMO_DISABLE`), and the
            # result keys of `tools/*`, every one of which is read by the MODEL
            # as text and by no Python at all. An audit that fires that often
            # teaches its reader to skip it, which is this module's own warning.
            #
            # A SUBSCRIPT WRITE IS THE SHAPE THAT ACTUALLY FAILED. Every
            # expensive instance was one: `meta["exhaustive_checks"] =
            # summary`, `out["predictor_disagrees"] = {...}`,
            # `row.update(image_only=...)`. It reads as "I computed this and
            # stored it somewhere", which is exactly the act that then reaches
            # nobody.

    # VENDORED TREES ARE NOT READERS. `webapp/` holds `node_modules/` and
    # `.next/` -- hundreds of MB of third-party .js/.json on an installed
    # checkout -- and sweeping them in did two bad things at once: the
    # counting pass took ~172 s (measured 2026-08-21: 1,302 full scans of the
    # concatenated blob, 99% of the whole `metascience lint-inert` runtime),
    # and any key whose name coincidentally appears in a vendored library was
    # silently counted as CONSUMED, suppressing the finding this detector
    # exists to make.
    _VENDORED = {"node_modules", ".next", ".git", "__pycache__",
                 ".extraction_cache", "dist", "build"}
    haystacks: list[str] = []
    for base in tree_roots:
        for path in base.rglob("*"):
            if _VENDORED.intersection(path.parts):
                continue
            if path.suffix.lower() not in (".py", ".ts", ".tsx", ".js", ".mjs",
                                           ".md", ".json", ".html"):
                continue
            try:
                haystacks.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    hay = "\n".join(haystacks)
    # ONE tokenising pass instead of three substring scans per key. The
    # substring test also over-credited prefixes -- `.key` matched inside
    # `.keyword`, so a key could be "consumed" by an unrelated attribute --
    # while these are whole-token counts.
    consumed = Counter(re.findall(r'["\'](\w+)["\']', hay))
    consumed.update(re.findall(r"\.(\w+)", hay))

    out: list[Finding] = []
    for key, (where, line) in sorted(writes.items()):
        if key in _CONSUMED_ELSEWHERE or len(key) < 4 or not key[0].isalpha():
            continue
        # One occurrence is the write itself. Two or more means somebody names
        # it somewhere -- a read, a test, a schema, a viewer script.
        if consumed[key] > 1:
            continue
        out.append(Finding(
            detector="write_only_key",
            confidence="worklist",
            where=f"{where}:{line}",
            what=(f"the key `{key}` is written here and its only occurrence in "
                  "src, tests, webapp and the prompts is this write, so whatever "
                  "was computed for it reaches no reader"),
            evidence=f"grep -rn '{key}' src tests webapp",
            extra={"key": key},
        ))
    return out


DETECTORS = {
    "degenerate_regex": find_degenerate_regexes,
    "empty_regex_alternative": find_unanchorable_alternatives,
    "unconsumed_definition": find_unconsumed_definitions,
    "swallowed_failure": find_swallowed_failures,
    "constant_outcome_check": find_constant_outcome_checks,
    "prompt_rule": find_unenforced_prompt_rules,
    "write_only_key": find_write_only_keys,
}


def scan(only: Iterable[str] | None = None) -> dict[str, Any]:
    """Run every detector and return findings plus per-detector counts.

    The counts are returned even when zero, and that is deliberate: a detector
    that reports nothing and a detector that did not run are indistinguishable
    in a bare list of findings, which is this module's own bug class turned on
    itself.
    """
    wanted = set(only) if only else set(DETECTORS)
    findings: list[Finding] = []
    ran: dict[str, int] = {}
    for name, fn in DETECTORS.items():
        if name not in wanted:
            continue
        got = fn()
        ran[name] = len(got)
        findings.extend(got)
    by_conf = Counter(f.confidence for f in findings)
    return {
        "n": len(findings),
        "by_detector": ran,
        "by_confidence": dict(by_conf),
        "findings": [f.as_dict() for f in findings],
    }
