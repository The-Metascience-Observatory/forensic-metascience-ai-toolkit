import path from "node:path";

export {
  posixRel, sameRel, windowsAbsToWsl, wslAbsToWindows,
} from "./rel.ts";

import { posixRel } from "./rel.ts";

export function badProject(p: string): boolean {
  return p.includes("..") || p.includes("/") || p.includes("\\") || p.startsWith(".");
}

export function badRel(rel: string): boolean {
  const s = String(rel || "");
  if (/^[a-zA-Z]:[\\/]/.test(s) || s.startsWith("\\\\") || s.startsWith("//")) {
    return true;
  }
  const posix = posixRel(s);
  if (path.isAbsolute(s) || path.isAbsolute(posix)) return true;
  return posix.split("/").includes("..");
}

/** True when `target` is a file or dir strictly inside `root`. */
export function contained(root: string, target: string): boolean {
  const rel = path.relative(root, target);
  if (!rel) return false;
  return !posixRel(rel).split("/").includes("..") && !path.isAbsolute(rel);
}
