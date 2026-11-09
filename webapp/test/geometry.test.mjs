import { test } from "vitest";
import assert from "node:assert/strict";
import { cropToParent, finite, isRect, matchRegions, sizeOf, unmirror, wholeCrop } from "../lib/geometry/project.ts";
import { projectImageBox } from "../lib/imagePdfBoxes.ts";
import { projectXmlImageBox } from "../lib/imageXmlBoxes.ts";

// A small deterministic generator: the property holds for every crop, size
// and box, so a few hundred random cases are the check, not hand-picked ones.
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32); }

test("the PDF and XML projections agree through one crop mapping", () => {
  const r = rng(42);
  for (let i = 0; i < 300; i++) {
    const figure = [100 + Math.floor(r() * 900), 100 + Math.floor(r() * 900)];        // [w, h]
    const c0 = Math.floor(r() * figure[0] / 2), c1 = c0 + 10 + Math.floor(r() * (figure[0] - c0 - 10));
    const r0 = Math.floor(r() * figure[1] / 2), r1 = r0 + 10 + Math.floor(r() * (figure[1] - r0 - 10));
    const crop = [r0, c0, r1, c1];
    const size = [20 + Math.floor(r() * 500), 20 + Math.floor(r() * 500)];           // panel frame
    const x0 = r() * size[0] * 0.5, x1 = x0 + 1 + r() * (size[0] - x0 - 1);
    const y0 = r() * size[1] * 0.5, y1 = y0 + 1 + r() * (size[1] - y0 - 1);
    const region = [x0, y0, x1, y1];
    // PDF: identity placement over the whole parent, so points come back as
    // fractions of the parent figure.
    const panel = { crop_box: crop, placements: [] };
    const pl = { bbox_kind: "crop_exact", transform: [1, 0, 0, 1, 0, 0], parent_size: figure, page: 1 };
    const pts = projectImageBox(panel, pl, size, region);
    assert.ok(pts, "pdf projection");
    const xml = projectXmlImageBox({ crop, size, region }, figure);
    assert.ok(xml, "xml projection");
    const expect = [[xml[0], xml[1]], [xml[2], xml[1]], [xml[2], xml[3]], [xml[0], xml[3]]];
    pts.forEach(([u, v], k) => {
      assert.ok(Math.abs(u * figure[0] - expect[k][0]) < 1e-6 && Math.abs(v * figure[1] - expect[k][1]) < 1e-6,
        `corner ${k} differs: pdf ${[u * figure[0], v * figure[1]]} vs xml ${expect[k]}`);
    });
    // and both equal the shared helper directly
    const [px, py] = cropToParent([x0, y0], size, crop);
    assert.ok(Math.abs(px - xml[0]) < 1e-9 && Math.abs(py - xml[1]) < 1e-9);
  }
});

test("crop mapping, whole crop, mirroring and region selection", () => {
  assert.deepEqual(cropToParent([0, 0], [10, 10], [5, 7, 15, 27]), [7, 5]);
  assert.deepEqual(cropToParent([10, 10], [10, 10], [5, 7, 15, 27]), [27, 15]);
  assert.deepEqual(wholeCrop([300, 200]), [0, 0, 200, 300]);
  // B is un-mirrored only when the match flipped and this is side B and not a clone.
  assert.deepEqual(unmirror([10, 20, 50, 70], 1, [200, 100], true, false), [150, 20, 190, 70]);
  assert.deepEqual(unmirror([10, 20, 50, 70], 0, [200, 100], true, false), [10, 20, 50, 70]);
  assert.deepEqual(unmirror([10, 20, 50, 70], 1, [200, 100], false, false), [10, 20, 50, 70]);
  assert.deepEqual(unmirror([10, 20, 50, 70], 1, [200, 100], true, true), [10, 20, 50, 70]);
  // Regions: a clone's list (side 0), else the side's inlier box; absence stays absent.
  const ms = { inlier_box_a: [1, 2, 3, 4], inlier_box_b: [5, 6, 7, 8], regions: [{ bbox: [0, 0, 1, 1] }, null], flip: true };
  assert.deepEqual(matchRegions(ms, 0, false), [{ bbox: [1, 2, 3, 4] }]);
  assert.deepEqual(matchRegions(ms, 1, false), [{ bbox: [5, 6, 7, 8] }]);
  assert.deepEqual(matchRegions(ms, 0, true), [{ bbox: [0, 0, 1, 1] }, {}]);
  assert.deepEqual(matchRegions({}, 1, false), [{ bbox: undefined }]);
  assert.deepEqual(matchRegions({ regions: "no" }, 0, true), [{ bbox: undefined }]);
  // Guards.
  assert.equal(finite([1, 2, NaN], 3), false);
  assert.deepEqual(sizeOf([3, 0]), null);
  assert.equal(isRect([0, 0, 1, 1]), true);
  assert.equal(isRect([-1, 0, 1, 1], { nonNegative: true }), false);
  assert.equal(isRect([2, 0, 1, 1]), false);
});
