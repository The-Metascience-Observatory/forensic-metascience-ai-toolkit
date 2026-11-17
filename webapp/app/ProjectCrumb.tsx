"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

/** The project name, in the top bar beside the platform's name, on every page
 *  under /project/<name>. */
export function ProjectCrumb() {
  const m = /^\/project\/([^/]+)/.exec(usePathname() || "");
  if (!m) return null;
  let project = m[1];
  try { project = decodeURIComponent(project); } catch { /* keep the raw segment */ }
  return (
    <span data-project-crumb style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span aria-hidden="true" style={{ color: "var(--muted)" }}>|</span>
      <Link href={`/project/${encodeURIComponent(project)}`}
            style={{ fontWeight: 600, color: "color-mix(in srgb, var(--accent) 70%, var(--fg))" }}>
        {project} project
      </Link>
    </span>
  );
}
