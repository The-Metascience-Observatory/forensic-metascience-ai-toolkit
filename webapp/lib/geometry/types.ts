/** The geometry vocabulary the image modules share.
 *
 *  `Box` and `Rect` are one type, [x0, y0, x1, y1] in pixels (the comparator
 *  said Box, the summary figure said Rect). `Crop` is the detector's panel
 *  crop in ROW/COLUMN order, [r0, c0, r1, c1], as `panels/*.json` records it.
 *  `Size` is [width, height]. `Matrix` is the canvas 2x3 affine
 *  [a, b, c, d, e, f] (x' = a x + c y + e, y' = b x + d y + f), the same as
 *  `affine.M`. */
export type Box = [number, number, number, number];
export type Rect = Box;
export type Crop = [number, number, number, number];
export type Size = [number, number];
export type Matrix = [number, number, number, number, number, number];
