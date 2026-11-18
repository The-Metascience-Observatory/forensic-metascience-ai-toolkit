"use client";

import { useEffect, useState } from "react";

import { readReviewer } from "@/app/ReviewerChip";
import { MAX_FOOTER_CHARS, footerParts } from "@/lib/emailFooter";
import { errorMessage, getJson, postJson } from "@/lib/getJson";

type Profile = { name: string; email_footer: string };

/** Each user's own settings. Today: the footer that email drafts put under
 *  their name. */
export default function SettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [footer, setFooter] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson<Profile>(`/api/profile?reviewer=${encodeURIComponent(readReviewer())}`)
      .then((p) => { setProfile(p); setFooter(p.email_footer); })
      .catch((e) => setErr(errorMessage(e)));
  }, []);

  const save = async () => {
    setBusy(true); setErr(null); setSaved(false);
    try {
      const p = await postJson<Profile>("/api/profile", { reviewer: readReviewer(), email_footer: footer });
      setProfile(p); setFooter(p.email_footer); setSaved(true);
    } catch (e) { setErr(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const preview = footerParts(footer);
  const dirty = profile !== null && footer !== profile.email_footer;
  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: 20, margin: "0 0 6px" }}>Settings</h1>
      {!profile && !err && <p className="muted">Loading…</p>}
      {err && <p role="alert" style={{ color: "var(--sev-impossible)" }}>{err}</p>}
      {profile && (
        <section className="settings-section">
          <h2 style={{ fontSize: 15, margin: "10px 0 4px" }}>Email footer</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Added under your name ({profile.name || "not set"}) in the emails you draft. Write{" "}
            <code>[link text](https://…)</code> for a link; it shows as a link when you use
            &ldquo;Copy formatted email&rdquo;.
          </p>
          <textarea value={footer} onChange={(e) => { setFooter(e.target.value); setSaved(false); }}
                    rows={4} maxLength={MAX_FOOTER_CHARS} aria-label="Email footer"
                    placeholder="Your title, [Your organisation](https://example.org)"
                    style={{ width: "100%", font: "13px/1.5 ui-monospace, monospace", padding: 8 }} />
          {preview.plain.length > 0 && (
            <div className="settings-preview" aria-label="Footer preview">
              <div className="muted" style={{ fontSize: 11 }}>Preview, under your signature:</div>
              <div>{profile.name}</div>
              {/* Built by footerParts from escaped text and http(s) links only. */}
              {preview.html.map((h, i) => <div key={i} dangerouslySetInnerHTML={{ __html: h }} />)}
            </div>
          )}
          <p style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button className="primary" onClick={save} disabled={!dirty || busy}>{busy ? "Saving…" : "Save"}</button>
            {saved && !dirty && <span className="muted" role="status">Saved. New drafts use it.</span>}
          </p>
        </section>
      )}
    </div>
  );
}
