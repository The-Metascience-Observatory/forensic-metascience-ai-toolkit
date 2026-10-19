"""Lends the host workbench's storage to the image package's review backend.

The image review logic lives in
`metascience_observatory_image_analysis.review_workbench`. It is built on
three host classes that also serve the statistical workbench and the Neon
cache -- `Catalog`, `Repository`, `Service` -- so the package holds the image
behaviour as mixins and this module lends it the bases (`host.bind`). Host
code reaches the storage-backed review modules through `load`, which binds
first, so every route sees one bound backend.
"""

#: Review modules whose classes are assembled from the host's bases, and the
#: binding each needs before it is usable.
_NEEDS_SERVICE = frozenset({"local_image_service"})
_NEEDS_STORAGE = frozenset({"local_images", "local_image_import"})


def load(name: str):
    """`review_workbench.<name>`, with the host's bases bound first when the
    module is assembled from them. Raises `ImagePluginUnavailable` without
    the image package."""
    if name in _NEEDS_SERVICE:
        configure_service()
    elif name in _NEEDS_STORAGE:
        configure()
    from ..image_plugin import load as _load
    return _load(f"review_workbench.{name}")



def configure():
    """Bind the storage bases (idempotent)."""
    from ..image_plugin import load
    host = load("review_workbench.host")
    if host.Catalog is not None:
        return host
    from .catalog import Catalog
    from .repository import Repository
    host.bind(catalog=Catalog, repository=Repository, remote=_remote, register_shared=_register_shared)
    return host


def configure_service():
    """Bind the storage bases and the JSON-lines service base (idempotent)."""
    host = configure()
    if host.Service is None:
        from .service import Service
        host.bind_service(Service)
    return host


def _remote():
    # Neon connections stay host-side; only `--from-neon` imports reach this.
    from .remote import Remote
    return Remote()


def _register_shared(root):
    # Looked up at call time, as the import used to be, so the shared
    # registry's own configuration (and a test's patch of it) still applies.
    from .notifications import register_shared
    return register_shared(root)
