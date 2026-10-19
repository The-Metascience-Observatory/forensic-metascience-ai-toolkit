/** Slash-folding that must run in the browser. Do not import `node:` here. */

export function posixRel(rel: string): string {
  return String(rel || "").replace(/\\/g, "/");
}

export function sameRel(
  a: string | null | undefined, b: string | null | undefined,
): boolean {
  return posixRel(a || "") === posixRel(b || "");
}

/** `C:\Users\x` → `/mnt/c/Users/x`. Null when the string is not a drive path. */
export function windowsAbsToWsl(p: string): string | null {
  const m = /^([a-zA-Z]):[\\/](.*)$/.exec(String(p || "").trim());
  if (!m) return null;
  return `/mnt/${m[1].toLowerCase()}/${m[2].replace(/\\/g, "/")}`;
}

/** `/mnt/c/Users/x` → `C:\Users\x`. Null when the string is not a WSL mount. */
export function wslAbsToWindows(p: string): string | null {
  const m = /^\/mnt\/([a-zA-Z])\/(.*)$/.exec(posixRel(String(p || "").trim()));
  if (!m) return null;
  return `${m[1].toUpperCase()}:\\${m[2].replace(/\//g, "\\")}`;
}
