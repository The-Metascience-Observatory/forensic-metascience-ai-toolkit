import Link from "next/link";

import { displayName, sev9Color, sev9Label } from "@/lib/constants.gen";

export const dynamic = "force-dynamic";

type TechRow = {
  technique: string; computed_by: string; n_papers_ran: number;
  n_papers_fired: number; fire_rate: number | null;
  n_findings: { problem: number; pass: number; undecided: number };
  n_impossible: number; by_severity: Record<string, number>;
  n_discarded_by_adjudicator: number; n_screen_flags: number;
};

async function loadStats(project: string) {
  const { promises: fsp } = await import("node:fs");
  const path = await import("node:path");
  const { loadSettings } = await import("@/lib/settings");
  const p = path.join(loadSettings().papers_root, project, "corpus_stats.json");
  try {
    return JSON.parse(await fsp.readFile(p, "utf8"));
  } catch {
    return null;
  }
}

async function loadFindings(project: string, technique: string, offset: number) {
  const { workbench } = await import("@/lib/workbench");
  try {return await workbench("findings",{project,technique,offset,limit:50});}
  catch {return null;}
}

export default async function StatsPage(
  { params, searchParams }: {
    params: { project: string };
    searchParams?: { technique?: string; offset?:string };
  },
) {
  const project = decodeURIComponent(params.project);
  const technique = searchParams?.technique || "";
  const offset=Math.max(0,Number(searchParams?.offset)||0);
  const result = technique ? await loadFindings(project, technique,offset) : null;
  const drill=result?.rows as {finding_id:string;paper_id:string;run_id:string;severity:number|null;impossible:boolean;title:string;producer:string;journal:string;year:number|null}[] | undefined;
  const stats = await loadStats(project);
  if (!stats) {
    return (
      <main style={{ padding: 24 }}>
        <h1>{project} — statistics</h1>
        <p>
          No <code>corpus_stats.json</code> yet. Compute it with{" "}
          <code>metascience corpus-stats &lt;corpus-root&gt;</code>.
        </p>
      </main>
    );
  }
  const techs: TechRow[] = stats.per_technique ?? [];
  const channels = stats.channel_status ?? {};
  return (
    <main style={{ padding: 24, maxWidth: 1100 }}>
      <h1>{project} — statistics</h1>
      <p>
        {stats.n_papers_with_v2}/{stats.n_papers} papers carry findings-v2
        documents (generated {stats.generated_at}). Every rate below names its
        denominator; “ran” includes runs whose result was discarded — a check
        that ran and retained nothing still ran.
      </p>

      <h2>Fires per technique</h2>
      <table>
        <thead>
          <tr>
            <th>technique</th><th>computed by</th><th>papers ran</th>
            <th>papers fired</th><th>rate</th><th>impossible</th>
            <th>discarded by adjudicator</th><th>severity spread</th>
          </tr>
        </thead>
        <tbody>
          {techs.map((r) => (
            <tr key={`${r.technique}:${r.computed_by}`}>
              <td>
                <Link href={`/project/${encodeURIComponent(project)}/stats?technique=${encodeURIComponent(r.technique)}`}
                      style={r.technique === technique
                        ? { fontWeight: 700 } : undefined}>
                  {r.technique}
                </Link>
              </td>
              <td>{r.computed_by}</td>
              <td>{r.n_papers_ran}</td>
              <td>{r.n_papers_fired}</td>
              <td>{r.fire_rate == null ? "—" : `${(r.fire_rate * 100).toFixed(1)}%`}</td>
              <td>{r.n_impossible}</td>
              <td>{r.n_discarded_by_adjudicator}</td>
              <td>
                {Object.entries(r.by_severity).sort().map(([sev, n]) => (
                  <span key={sev} title={sev9Label(Number(sev))}
                        style={{ background: sev9Color(Number(sev)),
                                 color: "white", borderRadius: 3,
                                 padding: "0 5px", marginRight: 4 }}>
                    S{sev}×{n}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {technique && (
        <>
          <h2>
            Findings — {technique}{" "}
            <Link href={`/project/${encodeURIComponent(project)}/stats`}
                  style={{ fontSize: 13, fontWeight: 400 }}>clear</Link>
          </h2>
          {drill == null ? (
            <p>The findings query failed; run it from the CLI:{" "}
              <code>metascience findings-query &lt;root&gt; --technique {technique}</code>
            </p>
          ) : drill.length === 0 ? (
            <p>No kept problem findings carry this technique — fires shown in
               the table above may all be discarded or belong to other runs.</p>
          ) : (
            <table>
              <thead>
                <tr><th>severity</th><th>title</th><th>paper</th>
                    <th>producer</th><th>journal</th><th>year</th></tr>
              </thead>
              <tbody>
                {drill.slice(0, 200).map((f) => (
                  <tr key={`${f.run_id}:${f.finding_id}`}>
                    <td>
                      {f.severity == null ? "—" : (
                        <span title={sev9Label(f.severity)}
                              style={{ background: sev9Color(f.severity),
                                       color: "white", borderRadius: 3,
                                       padding: "0 5px" }}>
                          S{f.severity}{f.impossible ? " ⚠" : ""}
                        </span>
                      )}
                    </td>
                    <td>{f.title}</td>
                    <td>
                      <Link href={`/project/${encodeURIComponent(project)}/review/${encodeURIComponent(f.paper_id)}?run=${encodeURIComponent(f.run_id)}`}>
                        {f.paper_id}
                      </Link>
                    </td>
                    <td>{displayName(f.producer)}</td>
                    <td>{f.journal}</td>
                    <td>{f.year ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result && <p>Showing {offset+1}–{offset+(drill?.length || 0)} of {result.pagination.total}.{" "}
            {offset>0 && <Link href={`?technique=${encodeURIComponent(technique)}&offset=${Math.max(0,offset-50)}`}>Previous 50</Link>}{" "}
            {result.pagination.next_offset!==null && <Link href={`?technique=${encodeURIComponent(technique)}&offset=${result.pagination.next_offset}`}>Next 50</Link>}
          </p>}
        </>
      )}

      <h2>Channels</h2>
      <table>
        <thead>
          <tr><th>channel</th><th>ran</th><th>ran, result discarded</th>
              <th>refused</th><th>did not run</th><th>unknown</th></tr>
        </thead>
        <tbody>
          {Object.entries(channels).map(([name, st]) => {
            const s = st as Record<string, number>;
            return (
              <tr key={name}>
                <td>{displayName(name)}</td><td>{s.ran}</td>
                <td>{s.ran_result_discarded}</td><td>{s.refused}</td>
                <td>{s.did_not_run}</td><td>{s.unknown}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h2>By journal</h2>
      <table>
        <thead>
          <tr><th>journal</th><th>papers</th><th>papers fired</th>
              <th>problem findings</th><th>impossible</th><th>worst</th></tr>
        </thead>
        <tbody>
          {(stats.by_journal ?? []).slice(0, 40).map(
            (j: Record<string, unknown>) => (
            <tr key={String(j.journal_normalized)}>
              <td>{String(j.journal_normalized)}</td>
              <td>{Number(j.n_papers)}</td>
              <td>{Number(j.n_papers_fired)}</td>
              <td>{Number(j.n_findings_problem)}</td>
              <td>{Number(j.n_impossible)}</td>
              <td>{j.worst_severity == null ? "—"
                   : sev9Label(Number(j.worst_severity))}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>By year</h2>
      <table>
        <thead>
          <tr><th>year</th><th>papers</th><th>papers fired</th>
              <th>problem findings</th><th>impossible</th></tr>
        </thead>
        <tbody>
          {(stats.by_year ?? []).map((y: Record<string, unknown>) => (
            <tr key={String(y.year)}>
              <td>{String(y.year)}</td>
              <td>{Number(y.n_papers)}</td>
              <td>{Number(y.n_papers_fired)}</td>
              <td>{Number(y.n_findings_problem)}</td>
              <td>{Number(y.n_impossible)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
