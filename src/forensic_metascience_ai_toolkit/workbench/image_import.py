"""`python -m forensic_metascience_ai_toolkit.workbench.image_import [args]`: the image review
import CLI (`review_workbench.local_image_import.main` in the image package),
run with the host's storage bound first. The package's own module cannot run
it unbound: its `ImageCatalog` is assembled from the host's bases and raises
`HostUnavailable` until they are lent."""
from .image_review_host import load

if __name__ == "__main__":
    raise SystemExit(load("local_image_import").main())
