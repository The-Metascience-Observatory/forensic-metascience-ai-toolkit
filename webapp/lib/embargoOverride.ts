/** Publishing a finding from a corpus under a selection embargo
 *  (EMBARGO.json) is refused unless the owner overrides it, deliberately and
 *  for ONE finding at a time. The marker itself is never edited or removed.
 *
 *  Why it exists (Dan, 2026-10-22: "I want to override and publish some of
 *  these"; later "just have a submit anyway button"): the marker says it is
 *  lifted only by the corpus owner's explicit decision. The decision is the
 *  click on "submit anyway", which appears only AFTER the server has refused,
 *  and the server requires its flag, so a plain submit still cannot lift the
 *  embargo. Every override is appended to EMBARGO_OVERRIDES.jsonl beside the
 *  marker, written BEFORE the website files are, so a publication with no
 *  record cannot happen. */
export const OVERRIDE_FIELD = "embargoOverride";
export const OVERRIDE_VALUE = "submit-anyway";
export const OVERRIDE_LOG = "EMBARGO_OVERRIDES.jsonl";

export const overrideConfirmed = (value: string | null | undefined): boolean =>
  (value ?? "").trim() === OVERRIDE_VALUE;

export type OverrideRecord = {
  at: string; action: "website_publication"; project: string; dir: string;
  doi: string; website_id: string; marker: string; confirmed_by: string;
};

export const overrideLine = (r: Omit<OverrideRecord, "at" | "action" | "confirmed_by">,
                             now: Date = new Date()): string =>
  JSON.stringify({ at: now.toISOString(), action: "website_publication",
    ...r, confirmed_by: "submit anyway button" }) + "\n";
