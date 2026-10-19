"""No function may read a local before it is assigned.

WHY THIS EXISTS
---------------
`analyze_paper` referenced `run_meta` about 80 lines before it was built. Every
one of the 1,654 tests passed, because the suite exercises the annotators and
the renderer directly and never runs `analyze_paper` end to end -- that path
needs a paid model call. So the only way to discover it was to spend twenty
minutes of a real run and watch the paper fail with

    local variable 'run_meta' referenced before assignment

after both stages had already been billed.

A static check is the right shape for this: it costs nothing, it covers every
function including the paid paths, and it catches the whole class rather than
the one instance.

The analysis is deliberately conservative -- it only flags a load that is
lexically before EVERY assignment of that name in the same function, and skips
anything touched by a comprehension, `global`/`nonlocal`, `try` bodies that may
bind late, or augmented assignment. It is looking for the unambiguous case.
"""
import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).parent.parent / "src" / "forensic_metascience_ai_toolkit"
#: The image package's source too. Host modules moved there (2026-10-01:
#: `extraction/regions_docling.py`) would otherwise leave this lint's reach
#: without anyone deciding they should.
from tests.source_paths import IMAGE_SRC
FILES = sorted(SRC.rglob("*.py")) + (sorted(IMAGE_SRC.rglob("*.py")) if IMAGE_SRC else [])


NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
                 ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _walk_own_scope(fn: ast.AST):
    """Yield nodes in this function's OWN scope, not nested ones.

    Comprehensions matter as much as nested functions here: in Python 3 they
    have their own scope, and their loop variable is Stored at the `for`
    clause, which is often lexically AFTER the element expression that reads
    it -- `[x.id for x in items]`. Walking into them reports every
    comprehension variable as read-before-assignment.
    """
    stack = [fn]
    while stack:
        node = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, NESTED_SCOPES):
                continue
            yield child
            stack.append(child)


def _unbound_loads(fn: ast.AST) -> list[tuple[str, int]]:
    """Names loaded strictly before any assignment to them in this function."""
    assigned: dict[str, list[int]] = {}
    loaded: dict[str, list[int]] = {}
    declared_elsewhere: set[str] = set()

    for node in _walk_own_scope(fn):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            declared_elsewhere.update(node.names)
        elif isinstance(node, ast.Name):
            (assigned if isinstance(node.ctx, ast.Store) else loaded) \
                .setdefault(node.id, []).append(node.lineno)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            assigned.setdefault(node.name, []).append(node.lineno)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = (alias.asname or alias.name).split(".")[0]
                assigned.setdefault(bound, []).append(node.lineno)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            for n in ast.walk(node.optional_vars):
                if isinstance(n, ast.Name):
                    assigned.setdefault(n.id, []).append(n.lineno)

    args = getattr(fn, "args", None)
    if args:
        for a in (list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs)
                  + [args.vararg, args.kwarg]):
            if a is not None:
                assigned.setdefault(a.arg, []).append(fn.lineno)

    out = []
    for name, load_lines in loaded.items():
        if name in declared_elsewhere or name not in assigned:
            continue
        first_assign = min(assigned[name])
        for ln in load_lines:
            if ln < first_assign:
                out.append((name, ln))
    return out


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_local_read_before_assignment(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for name, line in _unbound_loads(node):
                problems.append(f"{path.name}:{line} reads `{name}` in "
                                f"`{node.name}` before it is assigned")
    assert not problems, (
        "local read before assignment -- this raises UnboundLocalError at "
        "runtime on a path the tests may never execute:\n  "
        + "\n  ".join(problems))
