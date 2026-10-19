"""Resolve source aliases for static contract audits without executing modules."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _image_src():
    """The image analysis package's source directory, from wherever it is
    installed (its own checkout since 2026-10-16), or None when it is not."""
    import importlib.util
    try:
        spec = importlib.util.find_spec("metascience_observatory_image_analysis")
    except (ImportError, ValueError):
        return None
    return Path(list(spec.submodule_search_locations)[0]).resolve() if spec else None


#: `<image checkout>/src/metascience_observatory_image_analysis`, or None.
IMAGE_SRC = _image_src()
#: The image package's checkout root (scripts/, examples/, tests/), or None.
IMAGE_ROOT = IMAGE_SRC.parents[1] if IMAGE_SRC else None

def canonical(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if "_sys.modules[__name__] = _impl" not in text:
        return path
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
            name = ast.literal_eval(node.args[0])
            roots = {"metascience_agent": ROOT / "src/metascience_agent",
                     "metascience_observatory_image_analysis": IMAGE_SRC}
            package, _, rest = name.partition(".")
            if package in roots and roots[package] is None:
                return path      # an alias of a package that is not installed
            if package in roots:
                target = roots[package].joinpath(*rest.split(".")).with_suffix(".py")
                return canonical(target)
        # The plugin form (`_impl = _load("extraction.figures")` through
        # `image_plugin.load`): a module of the image package.
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("_load", "load")
                and node.args and isinstance(node.args[0], ast.Constant)):
            if IMAGE_SRC is None:
                return path
            return canonical(IMAGE_SRC.joinpath(*node.args[0].value.split(".")).with_suffix(".py"))
    raise AssertionError(f"Unresolved source alias: {path}")
