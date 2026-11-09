"use client";

import { loadPdfjs } from "@/lib/pdfjs";
import { useCallback, useEffect, useRef, useState } from "react";
import { isPdfReference, mediaUrl, type Item } from "@/app/images/lib";
import { extractEmails, xmlEmails } from "@/lib/emails";

type Found = { dir: string; emails: string[]; source: "PDF" | "XML" } | { dir: string; error: string };

/** A paper with no PDF: its publisher XML, located by the same `source` read
 *  the XML paper pane makes (an archived, hash-verified copy when sealed). */
async function paperXmlEmails(project: string, run: string, dir: string): Promise<string[] | null> {
  const query = new URLSearchParams({ method: "source", project, dir, run, component: "image_forensics" });
  const response = await fetch(`/api/workbench?${query}`);
  const source = await response.json().catch(() => ({}));
  if (!response.ok || source.error) throw new Error(source.error || response.statusText);
  const rel = source.article?.xml_relpath;
  if (!rel) return null;
  const xml = await fetch(mediaUrl(project, dir, rel));
  if (!xml.ok) throw new Error(`XML ${xml.status} ${xml.statusText}`);
  return xmlEmails(await xml.text());
}

async function pdfEmails(url: string): Promise<string[]> {
  const pdfjs = await loadPdfjs();
  const pdf = await pdfjs.getDocument({ url, withCredentials: false }).promise;
  try {
    const texts: string[] = [];
    for (let n = 1; n <= pdf.numPages; n++) {
      const page = await pdf.getPage(n);
      // mailto: link annotations first: they are exact where the text layer
      // may have split or ligatured the printed address.
      for (const a of await page.getAnnotations())
        if (typeof a.url === "string" && /^mailto:/i.test(a.url))
          texts.push(decodeURIComponent(a.url.replace(/^mailto:/i, "").split("?")[0]));
      const content = await page.getTextContent();
      let text = "";
      for (const it of content.items)
        if ("str" in it) text += it.str + (it.hasEOL ? "\n" : "");
      texts.push(text);
      page.cleanup();
    }
    return extractEmails(texts);
  } finally {
    void pdf.destroy();
  }
}

/** PubPeer's notify-authors field takes one line of addresses. */
export function joinEmails(emails: readonly string[]): string {
  return emails.join(", ");
}

/** Author e-mail addresses read from each paper's PDF (or its XML when it
 *  has none), for a PubPeer submission. One list per paper: a cross-paper
 *  item has two author sets. `autoStart` reads the paper as soon as the
 *  component mounts (the summary-figure dialog, where the addresses are
 *  wanted at once); the item page keeps the explicit button. */
export function AuthorEmails({ project, item, autoStart = false }: { project: string; item: Item; autoStart?: boolean }) {
  const [found, setFound] = useState<Found[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const key = `${project}\u0000${item.run_id}\u0000${item.id}`;
  useEffect(() => { setFound(null); setCopied(null); }, [key]);

  const papers = [...new Map((item.papers.length ? item.papers : [item.paper])
    .filter(p => p?.dir).map(p => [p.dir, p])).values()];
  const paperKey = papers.map(p => `${p.dir}\u0000${p.pdf ?? ""}`).join("|");
  const runId = item.run_id;

  const run = useCallback(async () => {
    setBusy(true);
    const out: Found[] = [];
    for (const p of papers) {
      try {
        if (isPdfReference(p.pdf)) { out.push({ dir: p.dir, source: "PDF", emails: await pdfEmails(mediaUrl(project, p.dir, p.pdf)) }); continue; }
        const emails = await paperXmlEmails(project, runId, p.dir);
        out.push(emails ? { dir: p.dir, source: "XML", emails } : { dir: p.dir, error: "no PDF or XML on disk" });
      } catch (e) { out.push({ dir: p.dir, error: String(e instanceof Error ? e.message : e) }); }
    }
    setFound(out); setBusy(false);
    // `papers` is derived from the item; `paperKey` stands in for it so the
    // callback changes exactly when the papers do.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, runId, paperKey]);

  // Once per item when asked to start on its own; a re-extract is still the button.
  const startedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!autoStart || startedFor.current === key || !papers.length) return;
    startedFor.current = key;
    void run();
  }, [autoStart, key, run, papers.length]);

  async function copy(dir: string, email: string) {
    await navigator.clipboard.writeText(email);
    setCopied(`${dir}\u0000${email}`);
  }

  return (
    <div style={{ margin: "8px 0" }}>
      <button type="button" onClick={run} disabled={busy || !papers.length}
              title="read author e-mail addresses from the paper's PDF, or its XML when there is no PDF (for PubPeer's notify-authors field)">
        {busy ? "reading paper…" : found ? "re-extract emails" : "Extract author emails"}
      </button>
      {found?.map(f => (
        <div key={f.dir} style={{ marginTop: 6 }}>
          {papers.length > 1 && <div className="mono muted" style={{ fontSize: 11 }}>{f.dir}</div>}
          {"error" in f ? <p className="muted" style={{ margin: 0 }}>Could not read: {f.error}</p>
            : !f.emails.length ? <p className="muted" style={{ margin: 0 }}>{f.source === "PDF"
                ? "No e-mail address found in the PDF text (it may be an image, or list none)."
                : "No e-mail address found in the XML (it may list none)."}</p>
            : <>
                {f.emails.length > 1 && (
                  <button type="button" style={{ fontSize: 11, marginTop: 4 }}
                          title="Copy every address, comma-separated, for PubPeer's notify-authors field"
                          onClick={() => void copy(f.dir, joinEmails(f.emails))}>
                    {copied === `${f.dir}\u0000${joinEmails(f.emails)}` ? "copied all" : `copy all ${f.emails.length}`}
                  </button>
                )}
                <ul style={{ margin: "2px 0", paddingLeft: 16 }}>
                  {f.emails.map(e => (
                    <li key={e} style={{ marginBottom: 2 }}>
                      <span className="mono" style={{ userSelect: "all" }}>{e}</span>{" "}
                      <button type="button" onClick={() => void copy(f.dir, e)} style={{ fontSize: 11 }}>
                        {copied === `${f.dir}\u0000${e}` ? "copied" : "copy"}
                      </button>
                    </li>
                  ))}
                </ul>
              </>}
        </div>
      ))}
    </div>
  );
}
