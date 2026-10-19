/** PDF image bounds in the same displayed-page frame used by review boxes.
 * Read image paints from the page itself, including strips absent from the
 * finding's panel list. Text, paths and image masks cannot extend a figure. */
type Matrix = [number, number, number, number, number, number];
type Rect = [number, number, number, number];
const multiply = (a: Matrix, b: Matrix): Matrix => [
  a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
  a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
  a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5],
];
export function pdfImageRects(list: { fnArray: number[]; argsArray: unknown[][] }, ops: Record<string, number>,
                              viewport: { transform: number[] }): Rect[] {
  let matrix: Matrix = [1, 0, 0, 1, 0, 0];
  const stack: Matrix[] = [], result: Rect[] = [];
  const transform = (args: unknown) => {
    if (Array.isArray(args) && args.length === 6 && args.every(v => typeof v === "number" && Number.isFinite(v)))
      matrix = multiply(matrix, args as Matrix);
  };
  list.fnArray.forEach((fn, i) => {
    const args = list.argsArray[i];
    if (fn === ops.save) stack.push([...matrix]);
    else if (fn === ops.restore) matrix = stack.pop() || [1, 0, 0, 1, 0, 0];
    else if (fn === ops.transform) transform(args);
    else if (fn === ops.paintFormXObjectBegin) { stack.push([...matrix]); transform(args?.[0]); }
    else if (fn === ops.paintFormXObjectEnd) matrix = stack.pop() || [1, 0, 0, 1, 0, 0];
    else if (fn === ops.paintImageXObject || fn === ops.paintInlineImageXObject) {
      const [a, b, c, d, e, f] = multiply(viewport.transform as Matrix, matrix);
      // Only axis-aligned strips can extend an axis-aligned crop.
      if (Math.abs(a * b) > 1e-6 || Math.abs(c * d) > 1e-6) return;
      const xs = [e, a + e, c + e, a + c + e], ys = [f, b + f, d + f, b + d + f];
      result.push([Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]);
    }
  });
  return result;
}
