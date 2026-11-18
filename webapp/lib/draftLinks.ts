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

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** The email body as HTML, for pasting into Gmail or another mail program
 *  with its formatting: paragraphs; a block whose lines are all indented by
 *  four spaces as code; bare URLs as links; and the opening sentence in its
 *  formatted form (title linked to the DOI, journal in italics, volume in
 *  bold) wherever the body still says it word for word. */
export function emailHtml(body: string, citation?: { plain?: string; html?: string } | null,
                          footer?: { plain?: string[]; html?: string[] } | null): string {
  // The footer's lines, plain -> formatted (its links), wherever they stand.
  const foot = new Map((footer?.plain || []).map((l, i) => [l, footer?.html?.[i] ?? ""] as const).filter(([l, h]) => l && h));
  const paras = body.replace(/\r\n?/g, "\n").split(/\n{2,}/).filter((p) => p.trim());
  const linkify = (s: string) => s.replace(/https?:\/\/[^\s<>"]+[^\s<>".,;:)]/g, (u) => `<a href="${u}">${u}</a>`);
  return paras.map((p) => {
    const lines = p.split("\n");
    if (lines.every((l) => /^ {4}|^\t/.test(l) || !l.trim())) {
      const code = lines.map((l) => l.replace(/^ {4}|^\t/, "")).join("\n");
      return `<pre style="font-family:monospace;background:#f5f5f5;padding:6px 8px">${escapeHtml(code)}</pre>`;
    }
    if (citation?.plain && citation.html && p.trim() === citation.plain) return `<p>${citation.html}</p>`;
    return `<p>${lines.map((l) => foot.get(l) ?? linkify(escapeHtml(l))).join("<br>")}</p>`;
  }).join("\n");
}
