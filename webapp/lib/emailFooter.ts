/** An email footer as a user types it: plain lines, where `[text](https://…)`
 *  makes a link. Pure, shared by the Settings page (preview) and the server
 *  (the drafts). */
export const MAX_FOOTER_CHARS = 1000;

const LINK = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g;

const escapeHtml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** `{plain, html}`, line for line: the plain lines go into the draft's text
 *  under the signature; the HTML lines replace them in the formatted copy. */
export function footerParts(source: string): { plain: string[]; html: string[] } {
  const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n").map((l) => l.trimEnd())
    .filter((l, i, all) => l || (i > 0 && i < all.length - 1));
  while (lines.length && !lines[lines.length - 1]) lines.pop();
  return {
    plain: lines.map((l) => l.replace(LINK, "$1")),
    html: lines.map((l) => {
      let out = "", at = 0;
      for (const m of l.matchAll(LINK)) {
        out += escapeHtml(l.slice(at, m.index)) + `<a href="${escapeHtml(m[2])}">${escapeHtml(m[1])}</a>`;
        at = (m.index ?? 0) + m[0].length;
      }
      return out + escapeHtml(l.slice(at));
    }),
  };
}
