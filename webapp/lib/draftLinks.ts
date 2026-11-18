/** Links that hand a drafted email to the reviewer's own mail program.
 *  Pure, so they are tested without a browser. Nothing is sent by the app. */

export interface Recipient { email: string; selected: boolean }

export const ticked = (rows: readonly Recipient[]): string[] =>
  rows.filter((r) => r.selected && r.email).map((r) => r.email);

/** A `mailto:` link. Addresses are joined with commas, unescaped (RFC 6068
 *  allows that and mail programs expect it); subject and body are encoded. */
export function mailtoUrl(to: readonly string[], cc: readonly string[], subject: string, body: string): string {
  const q = [
    cc.length ? `cc=${cc.map(encodeURIComponent).join(",")}` : "",
    subject ? `subject=${encodeURIComponent(subject)}` : "",
    body ? `body=${encodeURIComponent(body.replace(/\r?\n/g, "\r\n"))}` : "",
  ].filter(Boolean).join("&");
  return `mailto:${to.map(encodeURIComponent).join(",")}${q ? `?${q}` : ""}`;
}

/** Gmail's compose window, pre-filled. */
export function gmailUrl(to: readonly string[], cc: readonly string[], subject: string, body: string): string {
  const q = new URLSearchParams({ view: "cm", fs: "1", to: to.join(","), cc: cc.join(","), su: subject, body });
  return `https://mail.google.com/mail/?${q}`;
}

/** Mail programs and browsers cut long `mailto:` links; past this, the pane
 *  says to copy the body instead. */
export const MAILTO_SAFE_LENGTH = 1900;

/** PubPeer's search, which lands on the article's page for its DOI. */
export const pubpeerSearchUrl = (doi: string): string =>
  `https://pubpeer.com/search?q=${encodeURIComponent(doi)}`;
