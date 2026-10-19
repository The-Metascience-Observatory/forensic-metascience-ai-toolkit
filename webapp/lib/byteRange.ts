/** null means no range (including unsupported multipart); false is unsatisfiable. */
export function byteRange(value: string | null, size: number): { start: number; end: number } | null | false {
  if (!value || value.includes(",")) return null;
  const m = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!m || (!m[1] && !m[2]) || size === 0) return false;
  const a = Number(m[1]), b = Number(m[2]);
  if (!Number.isSafeInteger(a) || !Number.isSafeInteger(b)) return false;
  if (!m[1]) return b > 0 ? { start: Math.max(0, size - b), end: size - 1 } : false;
  const end = m[2] ? Math.min(b, size - 1) : size - 1;
  return a < size && a <= end ? { start: a, end } : false;
}
