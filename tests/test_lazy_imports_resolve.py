"""Every `from .x import name` inside src names something `x` actually defines.

WHY THIS EXISTS. v1.27.0 (`1d6a832`) deleted `agent.write_review_outputs`.
`cli.analyze` still began with

    from .agent import analyze_paper, write_review_outputs

INSIDE the function body, so `import forensic_metascience_ai_toolkit.cli` succeeded, every
test that imports the CLI passed, and `metascience analyze <paper>` -- the
verb the toolkit exists for -- raised ImportError on every invocation, before
any spend. Found 2026-09-05 while splitting agent.py; Dan's main carried the
same line (cli.py:498 at `70baa33`). The suite was green at 9,279 throughout,
because nothing in it runs that verb past its imports: the paid paths are
exactly the lines a test suite never executes.

A lazy import is a promise about ANOTHER module that is checked only when the
line runs. This test checks all of them statically, the way
`tests/test_no_unbound_locals.py` checks locals: parse every module, find every
`from`-import that targets a sibling in this package -- at any depth, including
inside functions -- and require each imported name to be a top-level binding
of the target module (or one of its submodules). It costs nothing and it covers
the paid paths.
"""
from __future__ import annotations

from tests.source_paths import canonical, IMAGE_SRC
import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"
PACKAGE = "forensic_metascience_ai_toolkit"


def _bindings(tree: ast.Module) -> set[str]:
    """Names a module binds at top level, including inside top-level `if`/`try`
    (the `try: import x / except: x = None` idiom) and `__all__` is NOT
    consulted -- a name must actually be bound."""
    out: set[str] = set()

    def add_target(t):
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                add_target(e)
        elif isinstance(t, ast.Starred):
            add_target(t.value)

    def visit(stmts):
        for n in stmts:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    add_target(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                add_target(n.target)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    if a.name != "*":
                        out.add(a.asname or a.name.split(".")[0])
            elif isinstance(n, (ast.If, ast.Try, ast.With)):
                visit(n.body)
                for h in getattr(n, "handlers", []):
                    visit(h.body)
                visit(getattr(n, "orelse", []))
                visit(getattr(n, "finalbody", []))
            elif isinstance(n, (ast.For, ast.While)):
                visit(n.body)
                visit(n.orelse)
    visit(tree.body)
    return out


def _target(path: pathlib.Path, root: pathlib.Path, node: ast.ImportFrom) -> tuple[str, ...] | None:
    """The target module as parts relative to `root`, or None if the import is
    not into this package."""
    if node.level == 0:
        if not node.module or not (node.module == PACKAGE or node.module.startswith(PACKAGE + ".")):
            return None
        return tuple(node.module.split(".")[1:])
    pkg = list(path.relative_to(root).parent.parts)
    up = node.level - 1
    if up > len(pkg):
        return None
    base = pkg[: len(pkg) - up] if up else pkg
    return tuple(base) + (tuple(node.module.split(".")) if node.module else ())


def unresolved(root: pathlib.Path) -> list[str]:
    """`file:line: from <target> import <name>` for every name the target does
    not bind. A target module that does not exist is reported once."""
    cache: dict[pathlib.Path, set[str]] = {}
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            parts = _target(path, root, node)
            if parts is None:
                continue
            mod_file = root.joinpath(*parts).with_suffix(".py") if parts else None
            pkg_dir = root.joinpath(*parts) if parts else root
            if mod_file is not None and mod_file.is_file():
                target = mod_file
            elif (pkg_dir / "__init__.py").is_file():
                target = pkg_dir / "__init__.py"
            else:
                problems.append(f"{path.relative_to(root)}:{node.lineno}: "
                                f"target module {'.'.join(parts)!r} does not exist")
                continue
            if target not in cache:
                cache[target] = _bindings(ast.parse(canonical(target).read_text(encoding="utf-8")))
            names = cache[target]
            for a in node.names:
                if a.name == "*" or a.name in names:
                    continue
                if target.name == "__init__.py" and (
                        (target.parent / f"{a.name}.py").is_file()
                        or (target.parent / a.name / "__init__.py").is_file()):
                    continue  # importing a submodule from its package
                problems.append(f"{path.relative_to(root)}:{node.lineno}: "
                                f"from {'.'.join(parts) or PACKAGE} import {a.name}")
    return problems


class TestEveryInPackageImportResolves:
    def test_src_has_no_import_of_a_name_the_target_does_not_define(self):
        problems = unresolved(SRC)
        assert problems == [], (
            f"{len(problems)} import(s) name something the target module does "
            "not bind. Each raises ImportError the first time its line RUNS --\n"
            "  " + "\n  ".join(problems)
            + "\n\nThe known instance: v1.27.0 deleted `write_review_outputs` "
              "and cli.analyze kept importing it lazily, so `metascience "
              "analyze` failed on every invocation while the suite stayed green.")

    def test_it_would_have_caught_the_cli_defect(self, tmp_path):
        """Known positive: the exact shape of cli.py:542 at 846bdc0 -- a lazy
        import, inside a function, of a name the target once defined."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "agent.py").write_text("async def analyze_paper():\n    pass\n")
        (pkg / "cli.py").write_text(
            "def analyze():\n"
            "    from .agent import analyze_paper, write_review_outputs\n"
            "    return analyze_paper, write_review_outputs\n")
        assert unresolved(pkg) == ["cli.py:2: from agent import write_review_outputs"]

    def test_a_submodule_import_from_a_package_is_fine(self, tmp_path):
        pkg = tmp_path / "pkg"
        (pkg / "sub").mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "sub" / "__init__.py").write_text("")
        (pkg / "sub" / "leaf.py").write_text("X = 1\n")
        (pkg / "user.py").write_text("from .sub import leaf\nfrom .sub.leaf import X\n")
        assert unresolved(pkg) == []

    def test_a_missing_target_module_is_reported(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "user.py").write_text("def f():\n    from .gone import x\n")
        assert unresolved(pkg) == ["user.py:2: target module 'gone' does not exist"]

    def test_a_name_bound_inside_a_try_counts(self, tmp_path):
        """`try: import yaml / except ImportError: yaml = None` binds `yaml`."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "opt.py").write_text("try:\n    import yaml\nexcept ImportError:\n    yaml = None\n")
        (pkg / "user.py").write_text("from .opt import yaml\n")
        assert unresolved(pkg) == []

    def test_the_check_is_not_vacuous(self):
        """It must have seen a lot of imports to mean anything."""
        n = 0
        for path in SRC.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError):
                continue
            n += sum(1 for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and _target(path, SRC, node) is not None)
        assert n > 200, n
