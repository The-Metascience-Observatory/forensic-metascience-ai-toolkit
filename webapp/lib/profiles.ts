import "server-only";

import fs from "node:fs";
import path from "node:path";

import { settingsPath } from "./directory.ts";
import { MAX_FOOTER_CHARS } from "./emailFooter.ts";
import type { Reviewer } from "./directory.ts";

/** Each user's own preferences (today: the footer under their name in email
 *  drafts), in `profiles.json` beside `settings.json`. A user is their
 *  signed-in email when hosted; locally, the reviewer name in the header,
 *  resolved to the directory's email when the directory lists it. */
export interface Profile { email_footer: string }

export const profilesPath = (env: NodeJS.ProcessEnv = process.env) =>
  path.join(path.dirname(settingsPath(env)), "profiles.json");

function readAll(file = profilesPath()): Record<string, Profile> {
  try {
    const v = JSON.parse(fs.readFileSync(file, "utf8"));
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}

/** The key a user's profile is stored under. */
export function profileKey(who: { email?: string | null; name?: string | null }, directory: Reviewer[]): string | null {
  if (who.email) return who.email.trim().toLowerCase();
  const name = (who.name || "").trim();
  if (!name) return null;
  const listed = directory.find((r) => r.name.trim().toLowerCase() === name.toLowerCase());
  return listed ? listed.email.trim().toLowerCase() : `name:${name}`;
}

export function readProfile(key: string | null, file = profilesPath()): Profile {
  const p = key ? readAll(file)[key] : undefined;
  return { email_footer: typeof p?.email_footer === "string" ? p.email_footer : "" };
}

export function saveProfile(key: string, next: Partial<Profile>, file = profilesPath()): Profile {
  const all = readAll(file);
  const footer = String(next.email_footer ?? all[key]?.email_footer ?? "");
  if (footer.length > MAX_FOOTER_CHARS) throw new Error(`The footer is longer than ${MAX_FOOTER_CHARS} characters`);
  all[key] = { ...all[key], email_footer: footer };
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(all, null, 2) + "\n", { mode: 0o600 });
  fs.renameSync(tmp, file);
  return all[key];
}

/** The user a request is from: hosted, the signed-in directory entry; local
 *  (no sign-in), the name the header's reviewer chip sent, else the
 *  directory's first admin, who is the person running the local app. */
export function currentUser(signedIn: { email: string; name: string } | null, reviewer: string, directory: Reviewer[]):
  { name: string; key: string | null } {
  if (signedIn) return { name: signedIn.name, key: profileKey({ email: signedIn.email }, directory) };
  const name = reviewer.trim() || directory.find((r) => r.role === "admin")?.name || "";
  return { name, key: profileKey({ name }, directory) };
}
