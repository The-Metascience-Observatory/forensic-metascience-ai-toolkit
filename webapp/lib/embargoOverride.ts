/** Publishing a finding from a corpus under a selection embargo
 *  (EMBARGO.json) is refused unless the owner overrides it, deliberately and
 *  for ONE finding at a time. The marker itself is never edited or removed.
 *
 *  Why it exists (Dan, 2026-10-22: "I want to override and publish some of
 *  these"): the marker says it is lifted only by the corpus owner's explicit
 *  decision. The phrase must be typed, and the server checks it, so a stray
 *  click or a script cannot lift it. Every override is appended to
 *  EMBARGO_OVERRIDES.jsonl beside the marker, written BEFORE the website files
 *  are, so a publication with no record cannot happen. */
export const OVERRIDE_PHRASE = "OVERRIDE EMBARGO";
export const OVERRIDE_LOG = "EMBARGO_OVERRIDES.jsonl";

export const overrideConfirmed = (typed: string | null | undefined): boolean =>
  (typed ?? "").trim() === OVERRIDE_PHRASE;

export type OverrideRecord = {
  at: string; action: "website_publication"; project: string; dir: string;
  doi: string; website_id: string; marker: string; confirmed_phrase: string;
};

export const overrideLine = (r: Omit<OverrideRecord, "at" | "action" | "confirmed_phrase">,
                             now: Date = new Date()): string =>
  JSON.stringify({ at: now.toISOString(), action: "website_publication",
    ...r, confirmed_phrase: OVERRIDE_PHRASE }) + "\n";
