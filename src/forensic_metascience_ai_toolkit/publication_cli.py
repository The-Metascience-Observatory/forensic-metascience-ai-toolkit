"""`metascience publish ...` and `metascience outreach ...`: the public findings site's data.

See publication.py. Every command writes to the local findings database only; `publish
snapshot` writes JSON files and never pushes or deploys anything.
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
from pathlib import Path
from typing import Optional

import typer

publish_app = typer.Typer(help="Public findings site: projects, the publish gate, the snapshot.",
                          no_args_is_help=True)
outreach_app = typer.Typer(help="Status events of a paper (PubPeer, emails, responses).",
                           no_args_is_help=True)


def _run(fn):
    from . import db_push, publication as P
    try:
        with P._connect() as conn:
            return fn(conn, P)
    except (ValueError, db_push.DbUnavailable) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


@publish_app.command("project")
def project_cmd(
    slug: str = typer.Argument(..., help="URL name, e.g. europepmc-tables-rng"),
    title: str = typer.Option(..., "--title"),
    tool: str = typer.Option(..., "--tool", help="The tool behind it, e.g. rngdetect"),
    policy: str = typer.Option(..., "--policy", help="ai_triaged or human_approved"),
    description: Optional[str] = typer.Option(None, "--description"),
    corpus: Optional[str] = typer.Option(None, "--corpus", help="What was screened, in words"),
    papers_screened: Optional[int] = typer.Option(None, "--papers-screened"),
    sort_order: int = typer.Option(0, "--sort-order"),
):
    """Create or update a screening project (one card on the site)."""
    _run(lambda conn, P: P.upsert_project(
        conn, slug=slug, title=title, tool=tool, policy=policy, description=description,
        corpus=corpus, papers_screened=papers_screened, sort_order=sort_order))
    typer.echo(f"project {slug} saved")


@publish_app.command("import")
def import_cmd(
    project: str = typer.Argument(..., help="Project slug"),
    candidates: Path = typer.Argument(..., help="JSON file: the project's full list of candidates"),
):
    """Load a tool's candidates (content and AI eligibility). Never changes a person's decision."""
    rows = json.loads(candidates.read_text())
    typer.echo(json.dumps(_run(lambda conn, P: P.import_candidates(conn, project, rows))))


def _decide(doi: str, project: str, state: str, note: Optional[str]) -> None:
    _run(lambda conn, P: P.set_state(conn, doi, project, state, by=getpass.getuser(), note=note))
    typer.echo(f"{doi} in {project}: {state}")


@publish_app.command("approve")
def approve_cmd(doi: str, project: str = typer.Option(..., "--project"),
                note: Optional[str] = typer.Option(None, "--note")):
    """Show this paper on the site (a person's decision; recorded as reviewed by a human)."""
    _decide(doi, project, "published", note)


@publish_app.command("withdraw")
def withdraw_cmd(doi: str, project: str = typer.Option(..., "--project"),
                 note: Optional[str] = typer.Option(None, "--note")):
    """Hide this paper from the site, whatever the AI triage says."""
    _decide(doi, project, "withdrawn", note)


@publish_app.command("reset")
def reset_cmd(doi: str, project: str = typer.Option(..., "--project"),
              note: Optional[str] = typer.Option(None, "--note")):
    """Undo an approve or withdraw: the project's policy decides again."""
    _decide(doi, project, "draft", note)


@publish_app.command("snapshot")
def snapshot_cmd(out: Path = typer.Option(..., "--out", help="The site repo's data folder")):
    """Write the site's JSON files. Prints what changed. Does not commit, push or deploy."""
    from . import db_push, publication as P
    try:
        typer.echo(json.dumps(P.write_snapshot(out), indent=1))
    except db_push.DbUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


@outreach_app.command("add")
def outreach_add_cmd(
    doi: str,
    kind: str = typer.Argument(..., help="e.g. pubpeer_submitted, authors_emailed (see `outreach kinds`)"),
    date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD (default: today)"),
    url: Optional[str] = typer.Option(None, "--url"),
    note: Optional[str] = typer.Option(None, "--note", help="Shown on the public page"),
    project: Optional[str] = typer.Option(None, "--project", help="Only when it concerns one project"),
):
    """Record a status event for a paper."""
    day = date or dt.date.today().isoformat()
    _run(lambda conn, P: P.add_event(conn, doi, kind, day, project=project, url=url, note=note,
                                     actor=getpass.getuser()))
    typer.echo(f"{doi}: {kind} on {day}")


@outreach_app.command("list")
def outreach_list_cmd(doi: str):
    """A paper's events, with the ids `outreach void` takes."""
    def go(conn, P):
        return conn.execute(
            "select id, occurred_on, kind, coalesce(url,''), coalesce(note,''), voided_at is not null "
            "from outreach_events where doi=%s order by occurred_on, id", (P.norm_doi(doi),)).fetchall()
    for i, day, kind, url, note, void in _run(go):
        voided = "\t(void)" if void else ""
        typer.echo(f"{i}\t{day}\t{kind}\t{url}\t{note}{voided}")


@outreach_app.command("void")
def outreach_void_cmd(event_id: int):
    """Take a mistaken event off the timeline (the row is kept)."""
    ok = _run(lambda conn, P: P.void_event(conn, event_id))
    typer.echo("voided" if ok else "no such live event")
    raise typer.Exit(0 if ok else 1)


@outreach_app.command("kinds")
def outreach_kinds_cmd():
    """The event kinds and the labels the site shows."""
    from . import publication as P
    for k, label in P.KINDS.items():
        typer.echo(f"{k}\t{label}")
