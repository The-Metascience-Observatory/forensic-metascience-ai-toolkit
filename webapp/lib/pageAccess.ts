import "server-only";

import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { hostedMode, identity, mayOpenProject, type Identity } from "./auth.ts";
import { sourceView } from "./projectSources.ts";

/** Access checks for server-rendered pages, which call the workbench
 *  directly and never pass through an API route's guard. The proxy has
 *  already refused unknown users and unassigned projects; these repeat that
 *  (a page must not depend on the proxy's matcher) and add what the proxy
 *  cannot know: whether the project is one of the configured sources. */

/** The signed-in user; `null` in local mode (where everyone is the admin). */
export async function currentUser(): Promise<Identity | null> {
  if (!hostedMode()) return null;
  return identity({ headers: await headers() });
}

export async function isAdminViewer(): Promise<boolean> {
  return !hostedMode() || (await currentUser())?.role === "admin";
}

/** 404 unless this viewer may open this project and it exists. */
export async function requireProjectPage(project: string): Promise<void> {
  if (hostedMode()) {
    const who = await currentUser();
    if (!who || !mayOpenProject(who, project)) notFound();
  }
  const view = await sourceView();
  if (view && !view.projects.has(project)) notFound();
}

/** The subset of `names` this viewer may see: configured sources only (when
 *  any are configured) and, for a reviewer, their assigned projects. */
export async function visibleProjectFilter(): Promise<(name: string) => boolean> {
  const view = await sourceView();
  const who = await currentUser();
  if (hostedMode() && !who) return () => false;
  return (name) => (!view || view.projects.has(name)) && (!who || mayOpenProject(who, name));
}
