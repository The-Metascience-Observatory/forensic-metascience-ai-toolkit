// Author e-mail addresses from a paper's text, for a PubPeer submission's
// "notify authors" field. Pure so it can be tested without a PDF.

const DOMAIN = String.raw`[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}`;
const LOCAL = String.raw`[A-Za-z0-9](?:[A-Za-z0-9._%+-]*[A-Za-z0-9_%+-])?`;
const PLAIN = new RegExp(`(${LOCAL})@(${DOMAIN})`, "g");
// "{smith, jones}@uni.edu" and "(smith, jones)@uni.edu": one domain shared
// by several local parts, common in physics/CS author blocks.
const GROUPED = new RegExp(String.raw`[{(\[]\s*(${LOCAL}(?:\s*[,;|]\s*${LOCAL})+)\s*[})\]]\s*@\s*(${DOMAIN})`, "g");

function tidy(text: string): string {
  return text
    .replace(/[\u00AD\u200B-\u200D\uFEFF]/g, "")   // soft hyphen, zero-width
    .replace(/[\uFF20\uFE6B]/g, "@")               // full-width / small @
    .replace(/\s*(?:\[\s*at\s*\]|\(\s*at\s*\))\s*/gi, "@")
    .replace(/\s*(?:\[\s*dot\s*\]|\(\s*dot\s*\))\s*/gi, ".")
    // PDF text runs split an address around its @ or dots ("smith @ uni .edu").
    .replace(/\s*@\s*/g, "@")
    // Only inside an address already begun with @, and only before a
    // lower-case TLD. " .edu" is always a split; ". edu" is one only while
    // the domain has no dot yet, so "…@uni.edu. co-authors" stays apart.
    .replace(/(@[A-Za-z0-9.-]*[A-Za-z0-9])\s+\.\s*(?=(?:com|org|net|edu|gov|ac|co|de|uk|fr|cn|jp|it|nl|es|ca|au|ch|se|br|in|kr|ru|pl|be|at|dk|fi|no|il|ie|nz|pt|gr|tw|hk|sg|mx|ar|za|cz|hu|tr|ir|eg)(?![A-Za-z-]))/g, "$1.")
    .replace(/(@[A-Za-z0-9-]*[A-Za-z0-9])\.\s+(?=(?:com|org|net|edu|gov|ac|co|de|uk|fr|cn|jp|it|nl|es|ca|au|ch|se|br|in|kr|ru|pl|be|at|dk|fi|no|il|ie|nz|pt|gr|tw|hk|sg|mx|ar|za|cz|hu|tr|ir|eg)(?![A-Za-z-]))/g, "$1.");
}

/** Unique addresses in first-seen order, lower-cased. */
export function extractEmails(texts: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const add = (local: string, domain: string) => {
    const addr = `${local}@${domain}`.toLowerCase().replace(/\.+$/, "");
    if (/\.(png|jpe?g|gif|tiff?)$/.test(addr) || seen.has(addr)) return;
    seen.add(addr);
    out.push(addr);
  };
  for (const raw of texts) {
    const text = tidy(raw.replace(/^mailto:/i, ""));
    for (const m of text.matchAll(GROUPED))
      for (const local of m[1].split(/\s*[,;|]\s*/)) add(local, m[2]);
    for (const m of text.matchAll(PLAIN)) add(m[1], m[2]);
  }
  return out;
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };
const unescape = (s: string) => s.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (_, e: string) =>
  e[0] === "#" ? String.fromCodePoint(e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10))
    : ENTITIES[e.toLowerCase()]);

/** Addresses in a publisher XML (JATS `<email>`, Elsevier `<ce:e-address>`,
 *  `mailto:` links), then any printed in its text. A paper delivered only as
 *  XML has no PDF to read, and its rendered article drops the author notes. */
export function xmlEmails(xml: string): string[] {
  const marked = [...xml.matchAll(/<((?:[\w-]+:)?(?:email|e-address))\b[^>]*>([\s\S]*?)<\/\1>/gi)]
    .map(m => unescape(m[2].replace(/<[^>]+>/g, "")));
  const links = [...xml.matchAll(/href\s*=\s*["']mailto:([^"'?]+)/gi)].map(m => unescape(decodeURIComponent(m[1])));
  const text = unescape(xml.replace(/<[^>]+>/g, " "));
  return extractEmails([...marked, ...links, text]);
}
