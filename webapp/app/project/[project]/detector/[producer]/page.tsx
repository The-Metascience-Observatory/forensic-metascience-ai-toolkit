import Link from "next/link";

import { displayName, sev9Color, sev9Label } from "@/lib/constants.gen";
import { reviewHref } from "@/lib/nav";

export const dynamic = "force-dynamic";

/** A detector track's cross-paper queue: every kept problem row of one
 *  STORED producer (`rng_track` first; spectra and copy-paste tracks plug in
 *  by producer), ordered by the track's own strength (tier, then excess
 *  bits), with its review state and a link that opens the paper review page
 *  focused on that finding. Reads the cached catalog only. */

type Row = {
  finding_id: string; paper_id: string; dir?: string | null; run_id: string;
  title: string; paper_title?: string | null; producer: string;
  severity: number | null; quarantined?: boolean; journal?: string | null; year?: number | null;
  track_basis?: { tier?: number; excess_bits?: number; log10_chance?: number; generator?: string;
                  seed?: number; n_values?: number; table?: string; column?: string; page?: number } | null;
  reviews?: { decision?: { decision?: string; reviewer?: string } | null; conflict?: boolean } | null;
};

async function load(project: string, producer: string, offset: number, decided: string) {
  const { workbench } = await import("@/lib/workbench");
  try {
    return await workbench("findings", {
      project, producer, sort: "track", offset, limit: 50,
      ...(decided === "0" || decided === "1" ? { decided } : {}),
    }) as { rows: Row[]; pagination: { total: number; next_offset: number | null; offset: number } };
  } catch (e) {
    return { error: String(e) };
  }
}

function where(b: Row["track_basis"]): string {
  if (!b) return "";
  const parts = [];
  if (b.table) parts.push(String(b.table));
  if (b.column) parts.push(`column ${b.column}`);
  if (b.page) parts.push(`p. ${b.page}`);
  return parts.join(" · ");
}

export default async function DetectorQueuePage(props: {
  params: Promise<{ project: string; producer: string }>;
  searchParams: Promise<{ offset?: string; decided?: string }>;
}) {
  const [params, searchParams] = await Promise.all([props.params, props.searchParams]);
  const project = decodeURIComponent(params.project);
  const producer = decodeURIComponent(params.producer);
  const offset = Math.max(0, Number(searchParams?.offset) || 0);
  const decided = searchParams?.decided || "";
  const result = await load(project, producer, offset, decided);
  const q = (o: number, d = decided) => `?offset=${o}${d ? `&decided=${d}` : ""}`;
  return (
    <main style={{ padding: 24, maxWidth: 1200 }}>
      <p><Link href={`/project/${encodeURIComponent(project)}`}>{project}</Link></p>
      <h1 style={{ fontSize: 20 }}>{displayName(producer)} — findings queue</h1>
      <p className="muted" style={{ fontSize: 12 }}>
        Every kept problem row filed by this detector in the latest runs, strongest first
        (tier, then evidence beyond the search size). A quarantined row is a lead to check, not a
        finding of record. Filter:{" "}
        <Link href={q(0, "")}>all</Link> · <Link href={q(0, "0")}>undecided</Link> ·{" "}
        <Link href={q(0, "1")}>decided</Link>
      </p>
      {"error" in result ? (
        <p style={{ color: "var(--sev-impossible)" }}>{result.error}</p>
      ) : result.rows.length === 0 ? (
        <p>No rows for this producer in the synchronized catalog for this project
           {decided ? " under this filter" : ""}. An absent row is not a clean paper: check the
           run's channel state on the paper page.</p>
      ) : (
        <>
          <table className="grid">
            <thead>
              <tr>
                <th>tier</th><th>bits</th><th>generator · seed</th><th>where</th>
                <th>finding</th><th>paper</th><th>decision</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((f) => {
                const b = f.track_basis || {};
                const base = reviewHref(project, f.paper_id, f.dir);
                const href = `${base}${base.includes("?") ? "&" : "?"}run=${encodeURIComponent(f.run_id)}&finding=${encodeURIComponent(f.finding_id)}`;
                const d = f.reviews?.decision?.decision;
                return (
                  <tr key={`${f.run_id}:${f.finding_id}`}>
                    <td>{b.tier ?? "—"}</td>
                    <td className="mono">{typeof b.excess_bits === "number" ? b.excess_bits.toFixed(0) : "—"}</td>
                    <td className="mono">{b.generator ? `${b.generator.split(":")[0]} · ${b.seed ?? "?"}` : "—"}</td>
                    <td>{where(f.track_basis)}</td>
                    <td>
                      <Link href={href}>{f.title}</Link>
                      {f.quarantined && <span className="pill" style={{ marginLeft: 6, color: "var(--muted)", borderStyle: "dashed" }}>quarantined</span>}
                      {f.severity != null && (
                        <span className="pill" title={sev9Label(f.severity)}
                              style={{ marginLeft: 6, color: sev9Color(f.severity) }}>S{f.severity}</span>
                      )}
                    </td>
                    <td>
                      <Link href={reviewHref(project, f.paper_id, f.dir)}>{f.paper_title || f.paper_id}</Link>
                      <span className="muted" style={{ fontSize: 11 }}>
                        {f.journal ? ` · ${f.journal}` : ""}{f.year ? ` ${f.year}` : ""}
                      </span>
                    </td>
                    <td>
                      {f.reviews?.conflict ? <span className="pill">reviewers disagree</span>
                        : d ? <span className="pill">{d.replace(/_/g, " ")}</span>
                        : <span className="muted">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p>
            Showing {result.pagination.offset + 1}–{result.pagination.offset + result.rows.length} of {result.pagination.total}.{" "}
            {offset > 0 && <Link href={q(Math.max(0, offset - 50))}>Previous 50</Link>}{" "}
            {result.pagination.next_offset !== null && <Link href={q(result.pagination.next_offset)}>Next 50</Link>}
          </p>
        </>
      )}
    </main>
  );
}
