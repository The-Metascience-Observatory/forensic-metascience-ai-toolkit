"""The image review behaviour the workbench classes inherit.

`Service` and `Repository` serve the statistical workbench and the image queue
alike; the image half is the image analysis package's (`ImageServiceMixin`,
`SharedImageQueueMixin`). Without that package the same names are stand-ins
whose image methods raise `ImagePluginUnavailable`, so an image request gets a
named error and every statistical route is unaffected.
"""
from ..image_plugin import ImagePluginUnavailable, INSTALL_HINT, available, load

#: `review_workbench.service_images.SHARED_QUEUE_METHODS` (the routing table
#: must not depend on the package being installed).
SHARED_QUEUE_METHODS = ('feed', 'feed_facets', 'image_run_options', 'image_navigation')


def _unavailable(*_args, **_kwargs):
    raise ImagePluginUnavailable(f"image review: {INSTALL_HINT}")


if available():
    _service = load("review_workbench.service_images")
    ImageServiceMixin = _service.ImageServiceMixin
    SHARED_QUEUE_METHODS = _service.SHARED_QUEUE_METHODS
    SharedImageQueueMixin = load("review_workbench.shared_queue").SharedImageQueueMixin
else:
    class ImageServiceMixin:
        """Stand-in: the image analysis package is not installed."""
        image_media = colour_panel = achromatic = _unavailable
        image_video = image_item = shared_image_queue = _unavailable

    class SharedImageQueueMixin:
        """Stand-in: the image analysis package is not installed."""
        item_view = local_video_items = feed = _unavailable
