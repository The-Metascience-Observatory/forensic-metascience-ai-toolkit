"""Textured synthetic panels for the image-forensics tests.

Every panel in `test_summary_figure.py` and `test_review_media.py` used to be
a flat `Image.new("RGB", size, colour)`. A flat panel has zero local variance,
so any correlation-based measurement returns "did not agree" on it -- which
means a gate that could never pass would leave those suites green
(LESSONS.md #4). These builders give a test something a measurement can
actually see: a seeded noise field standing in for a micrograph, and the two
shapes the unaligned control exists to tell apart.
"""
from __future__ import annotations

import numpy as np


def noise_field(shape=(220, 300), seed=0, blur=2) -> np.ndarray:
    """A smooth grey field with pixel-scale grain, uint8 -- a stand-in
    micrograph. `blur` gives it structure a 15 px window can correlate."""
    rng = np.random.default_rng(seed)
    base = rng.random(shape)
    if blur:
        import cv2
        base = cv2.GaussianBlur(base.astype(np.float32), (0, 0), blur)
        base = (base - base.min()) / max(1e-9, base.max() - base.min())
    grain = rng.normal(0, 0.03, shape)
    return np.clip((base * 0.8 + 0.1 + grain) * 255, 0, 255).astype(np.uint8)


def shifted_crop_pair(seed=1, shift=(40, 90), size=(160, 200)):
    """The duplication shape: ONE field, cropped twice at an offset.

    Returns `(a, b, affine)` where `affine` maps a's pixels onto b's -- the
    detector's convention -- and the two crops share the pixels wherever
    they overlap."""
    field = noise_field((size[0] + abs(shift[1]) + 20, size[1] + abs(shift[0]) + 20), seed)
    dx, dy = shift
    a = field[0:size[0], 0:size[1]].copy()
    b = field[dy:dy + size[0], dx:dx + size[1]].copy()
    affine = [[1.0, 0.0, -float(dx)], [0.0, 1.0, -float(dy)]]
    return a, b, affine


def independent_pair(seed=2, size=(160, 200)):
    """Two different fields: nothing to agree, aligned or not."""
    a = noise_field(size, seed)
    b = noise_field(size, seed + 1000)
    return a, b, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def template_pair(seed=3, size=(160, 200)):
    """The chart-furniture shape: two independent fields under ONE drawn
    grid, so they correlate on the grid alone, aligned or not."""
    import cv2
    a, b, affine = independent_pair(seed, size)
    for img in (a, b):
        for x in range(0, size[1], 25):
            cv2.line(img, (x, 0), (x, size[0]), 255, 3)
        for y in range(0, size[0], 25):
            cv2.line(img, (0, y), (size[1], y), 255, 3)
    return a, b, affine


def save_png(path, arr) -> None:
    import cv2
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), arr)
