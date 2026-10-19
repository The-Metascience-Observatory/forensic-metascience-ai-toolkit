"""Local review output. Raw evidence, judgments, and coverage remain visible."""

from html import escape
from pathlib import Path
from urllib.parse import quote


def render_report(directory, manifest, result, adjudication):
    directory = Path(directory)

    def esc(value):
        return escape(str(value))

    judgments = {d["candidate_id"]: d for d in adjudication.get("decisions", [])}
    body = [
        f"<h1>Copy-paste review: {esc(manifest['paper_id'])}</h1>",
        "<p>Matches are candidates for investigation, not proof of fabrication.</p>",
        f"<p><b>Run:</b> {esc(manifest['id'])} · <b>Status:</b> {esc(manifest['status'])}</p>",
        f"<p>{esc(result.get('explanation', result.get('error', 'No detector result')))}</p>",
        f"<p><b>Coverage:</b> {esc(result.get('coverage'))}</p>",
        f"<p><b>Context read failures:</b> {esc(manifest.get('context_failures', []))}</p>",
        f"<p><b>AI status:</b> {esc(adjudication.get('status'))}</p>",
        '<p><a href="result.json">Complete detector JSON</a> · <a href="adjudication.json">AI judgments and receipts</a></p>',
        "<h2>Source files</h2><ul>",
    ]
    for source in result.get("sources", []):
        artifact = manifest.get("source_artifacts", {}).get(source["file"])
        label = esc(source["file"])
        if artifact:
            label = f'<a href="{quote(artifact["path"])}">{label}</a>'
        body.append(f"<li>{label}: {esc(source['status'])} {esc(source.get('error', ''))}</li>")
    body.append("</ul><h2>Limitations and exclusions</h2><ul>")
    for note in result.get("caveats", []) + result.get("excluded_columns", []):
        body.append(f"<li>{esc(note)}</li>")
    body.append("</ul><h2>Candidates</h2>")
    for g in result.get("duplicate_groups", []):
        judgment = judgments.get(
            g["id"], {"decision": "unreviewed", "reason": "No validated AI judgment"}
        )
        body.append(f'<section id="{esc(g["id"])}"><h3>{esc(g["id"])} · {esc(g["kind"])}</h3>')
        body.append(
            f"<p>Detector: <b>{esc(g['severity'])}</b> · AI: <b>{esc(judgment['decision'])}</b></p>"
        )
        body.append(f"<p>{esc(judgment['reason'])} {esc(judgment.get('enforced_reason', ''))}</p>")
        if judgment.get("citations"):
            body.append(
                "<ul>"
                + "".join(
                    f"<li>{esc(c['source_id'])}: {esc(c['quote'])}</li>"
                    for c in judgment["citations"]
                )
                + "</ul>"
            )
        refs = g.get("cells", []) + g.get("cells_a", []) + g.get("cells_b", [])
        body.append(
            "<table><thead><tr><th>File</th><th>Sheet/table</th><th>Cell</th><th>Column</th><th>Value</th></tr></thead><tbody>"
        )
        for ref in refs:
            body.append(
                "<tr>"
                + "".join(
                    f"<td>{esc(ref.get(k, ''))}</td>"
                    for k in ("file", "sheet", "cell", "column", "value")
                )
                + "</tr>"
            )
        body.append("</tbody></table></section>")
    document = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Copy-paste review</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#20252b}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:7px;text-align:left;border-bottom:1px solid #ddd}section{margin:32px 0}a{color:#175c9f}p,li{line-height:1.5}td{overflow-wrap:anywhere}</style>'
        + "".join(body)
        + "</html>"
    )
    (directory / "review.html").write_text(document, encoding="utf-8")


def render_index(directory, rows):
    links = []
    for row in rows:
        label = escape(f"{row['paper_id']} — {row['status']}")
        links.append(
            f'<li><a href="{quote(row["review"])}">{label}</a></li>'
            if row.get("review")
            else f"<li>{label}</li>"
        )
    Path(directory, "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Copy-paste batch</title><h1>Copy-paste batch</h1><ul>'
        + "".join(links)
        + "</ul>"
    )
