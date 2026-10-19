"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { RunSelector } from "@/app/RunSelector";
import { useFeed, updateFeed, useItem } from "@/app/images/useFeed";
import { mediaUrl, evidenceLabel, DECISIONS, type Item, cycleQueueSort, queueSortMark, type Filter, nextUndecidedIn } from "@/app/images/lib";
import { readReviewer } from "@/app/ReviewerChip";
import { SpreadsheetPane } from "@/app/project/[project]/review/[slug]/SpreadsheetPane";

type CopyItem = Item & {
  group: Record<string, unknown>; input_file: string | null; highlight_file?: string;
  result_counts: Record<string, number>;
  input_files?: {name: string; path: string}[];
  copy_judgment?: {decision: string; reason: string; enforced_reason?: string; citations?: {source_id: string; quote: string}[]};
  coverage?: Record<string, unknown>;
  ai_status?: string;
};

export function CopyQueue({ project }: { project: string }) {
  const router = useRouter(), params = useSearchParams();
  const run = params.get("run") || "latest";
  const offset=Number(params.get("offset") || 0);
  const filter=params.get("status") || "published";
  const [q,setQ]=useState(params.get("q") || "");
  const [sort,setSort]=useState<Pick<Filter,"sort"|"direction">>({sort:"score",direction:"desc"});
  const {feed,error}=useFeed(project,run,"copy_paste",{offset,verdict:filter==="published"?"unexplained":filter,q,
    sort:sort.sort,direction:sort.direction});
  const detail=useItem(project,run,"copy_paste",params.get("item") || undefined,params.get("owner") || undefined);
  const [message, setMessage] = useState("");
  const activeSelection = useRef(run); activeSelection.current = run;
  const all = (feed?.items || []) as CopyItem[];

  const items = all.filter(i => filter === "all" || i.publication_status === filter);
  const item=detail.item as CopyItem | null;
  function select(i?: CopyItem) {
    const next = new URLSearchParams(params);
    next.set("run", run);
    if (i) { next.set("item", i.id); next.set("owner", i.run_id); }
    else { next.delete("item"); next.delete("owner"); }
    router.push(`?${next}`);
  }
  useEffect(() => { setMessage(""); }, [run, project]);
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if ((event.target as HTMLElement)?.matches("input,select,textarea")) return;
      if (!["j", "k"].includes(event.key) || !items.length) return;
      event.preventDefault();
      const at = item ? items.findIndex(i => i.id === item.id && i.run_id === item.run_id) : -1;
      select(items[Math.max(0, Math.min(items.length - 1, at + (event.key === "j" ? 1 : -1)))]);
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [item, items, run]);
  async function decide(value: string) {
    if (!item) return;
    const selectedItem = item, selection = run;
    const reviewer = readReviewer();
    if (!reviewer) { setMessage("Set your name before saving a decision."); return; }
    const advanceTo = nextUndecidedIn(items, selectedItem.id);
    try {
      const response = await fetch("/api/images", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ component: "copy_paste", project, run: item.run_id, item: item.id, decision: value, reviewer }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || response.statusText);
      updateFeed(project, f => ({ ...f, items: f.items.map(i => i.id === selectedItem.id && i.run_id === selectedItem.run_id
        ? { ...i, decision: body.decision } : i) }), selection, "copy_paste");
      if (advanceTo && activeSelection.current === selection) select(advanceTo);
    } catch (err) { if (activeSelection.current === selection) setMessage(String(err)); }
  }
  return <div style={{ padding: 12, overflow: "auto" }}>
    <Link href={`/project/${encodeURIComponent(project)}`}>← {project}</Link><h2>Copy/paste review</h2>
    <p><button disabled={!offset} onClick={()=>router.push(`?run=${encodeURIComponent(run)}&status=${filter}&q=${encodeURIComponent(q)}&offset=${Math.max(0,offset-50)}`)}>Previous 50</button> {offset+1}–{offset+items.length} of {feed?.pagination?.total ?? "…"} <button disabled={feed?.pagination?.next_offset==null} onClick={()=>router.push(`?run=${encodeURIComponent(run)}&status=${filter}&q=${encodeURIComponent(q)}&offset=${offset+50}`)}>Next 50</button></p>
    <RunSelector project={project} component="copy_paste" value={run} options={feed?.runs || []} onChange={s => router.push(`?run=${encodeURIComponent(s)}`)} />
    <p>Saved detector candidates. Human decisions are recorded separately from publication.</p>
    <label>Results <select value={filter} onChange={e => {
      const next = new URLSearchParams(params); next.set("status", e.target.value); next.set("run", run); next.set("q", q); next.set("offset","0"); router.push(`?${next}`);
    }}><option value="all">All saved results</option><option value="unscreened">Unresolved candidates</option>
      <option value="cleared">Cleared / rejected</option><option value="published">Published findings</option></select></label>{" · "}
    <label title="Matches the paper folder. A DOI with a slash also matches the -- folder name.">Paper folder{" "}
      <input className="mono" value={q} onChange={e => {
        const value=e.target.value; setQ(value);
        if(offset){const next=new URLSearchParams(params); next.set("q",value); next.set("run",run); next.set("status",filter); next.set("offset","0"); router.push(`?${next}`);}
      }} placeholder="10.1007--s004010050748" aria-label="Search by paper folder name" style={{minWidth:220}} /></label>{" · "}
    <a href={`/api/images?${new URLSearchParams({ project, run, component: "copy_paste", format: "csv" })}`}>Export CSV</a>
    {(error || message) && <p role="alert">{error || message}</p>}
    {!!feed?.notes.length && <details><summary>Run coverage and unavailable outputs</summary>
      <div style={{ maxHeight: 200, overflow: "auto" }}>{feed.notes.map((s, i) => <p key={i}>{s}</p>)}</div></details>}
    {feed && !items.length && <p>{all.length ? "The selected filters hide all saved results."
      : feed.empty_reason || "No copy/paste run is recorded. Import saved output or use metascience copy-paste."}</p>}
    <table style={{ width: "100%" }}><thead><tr>
      <th aria-sort={sort.sort==="paper"?(sort.direction==="asc"?"ascending":"descending"):"none"}>
        <button type="button" className="sort-th" onClick={()=>setSort(cycleQueueSort(sort, "paper", "score"))}
                title="Sort by paper folder. First click A to Z, second Z to A, third restores score.">
          Paper / file{queueSortMark(sort, "paper")}
        </button>
      </th>
      <th>Kind</th><th>Version / run</th><th>Human decision</th></tr></thead>
      <tbody>{items.map(i => <tr key={`${i.run_id}:${i.id}`}><td><button onClick={() => select(i)}>{i.paper.dir} · {i.paper.title}</button></td>
        <td>{i.detector_kind}</td><td>{i.provenance?.version || "unknown"} · {i.run_id}</td><td>{i.decision?.decision || "undecided"}</td></tr>)}</tbody></table>
    {detail.error && <p>{detail.error}</p>}
    {item && <section><h3>{item.sentence || item.source_id}</h3>
      <p>Evidence: {evidenceLabel(item.evidence_source)} · {item.publication_status}</p>
      <p>Counts for the selected analysis. Groups, row pairs, and implicated rows measure different quantities.</p>
      {item.coverage && <p>Coverage: {JSON.stringify(item.coverage)}</p>}
      {item.ai_status && <p>AI processing: {item.ai_status}</p>}
      {item.copy_judgment && <div><h4>Saved Grok judgment: {item.copy_judgment.decision}</h4>
        <p>{item.copy_judgment.reason} {item.copy_judgment.enforced_reason}</p>
        {item.copy_judgment.citations?.map((c, i) => <blockquote key={i}>{c.source_id}: {c.quote}</blockquote>)}</div>}
      <pre>{JSON.stringify(item.result_counts, null, 2)}</pre><details open><summary>Saved group and cell references</summary><pre>{JSON.stringify(item.group, null, 2)}</pre></details>
      {item.input_files?.length ? item.input_files.map(f => <p key={f.path}><a href={mediaUrl(project, item.paper.dir, f.path, "copy_paste")}>{f.name}</a></p>)
        : item.input_file ? <a href={mediaUrl(project, item.paper.dir, item.input_file, "copy_paste")}>Saved input</a> : <p>Historical input evidence unavailable.</p>}{" "}
      {item.highlight_file && <a href={mediaUrl(project, item.paper.dir, item.highlight_file, "copy_paste")}>Highlighted workbook</a>}
      <p>{DECISIONS.map(([v, , label]) => <button key={v} onClick={() => void decide(v)}>{label}</button>)}</p>
      {item.input_files?.map(f => {
        const refs = [item.group.cells, item.group.cells_a, item.group.cells_b].flatMap(v => Array.isArray(v) ? v : []).filter(c => c.file === f.name);
        return <div key={`${item.run_id}:${item.id}:${f.path}`} style={{height: 500}}>
          <SpreadsheetPane project={project} slug="" dir={item.paper.dir} label="Saved source evidence"
            artefact={{relpath: f.path, basename: f.name, cells: refs, sheet: refs[0]?.sheet || ""}} /></div>;
      })}
      {!item.input_files?.length && item.input_file && /\.(xlsx?|xlsm|csv|tsv)$/i.test(item.input_file) && <div style={{ height: 500 }}>
        <SpreadsheetPane key={`${item.run_id}:${item.id}`} project={project} slug="" dir={item.paper.dir} label="Saved input evidence"
          artefact={{ relpath: item.input_file, basename: item.input_file.split("/").pop() || item.input_file, cells: item.group.cells || [], sheet: item.group.sheet || "" }} /></div>}
    </section>}
  </div>;
}
