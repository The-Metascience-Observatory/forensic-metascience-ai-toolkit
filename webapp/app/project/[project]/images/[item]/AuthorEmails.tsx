"use client";

import { useEffect, useState } from "react";
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
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
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

/** Author e-mail addresses read from each paper's PDF (or its XML when it
 *  has none), for a PubPeer
 *  submission. One list per paper: a cross-paper item has two author sets. */
export function AuthorEmails({ project, item }: { project: string; item: Item }) {
  const [found, setFound] = useState<Found[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const key = `${project}\u0000${item.run_id}\u0000${item.id}`;
  useEffect(() => { setFound(null); setCopied(null); }, [key]);

  const papers = [...new Map((item.papers.length ? item.papers : [item.paper])
    .filter(p => p?.dir).map(p => [p.dir, p])).values()];

  async function run() {
    setBusy(true);
    const out: Found[] = [];
    for (const p of papers) {
      try {
        if (isPdfReference(p.pdf)) { out.push({ dir: p.dir, source: "PDF", emails: await pdfEmails(mediaUrl(project, p.dir, p.pdf)) }); continue; }
        const emails = await paperXmlEmails(project, item.run_id, p.dir);
        out.push(emails ? { dir: p.dir, source: "XML", emails } : { dir: p.dir, error: "no PDF or XML on disk" });
      } catch (e) { out.push({ dir: p.dir, error: String(e instanceof Error ? e.message : e) }); }
    }
    setFound(out); setBusy(false);
  }

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
