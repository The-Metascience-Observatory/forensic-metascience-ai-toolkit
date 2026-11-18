"""Drafts of an email to the journal and authors, and of a PubPeer comment.

The review page's "Draft email" and "Draft PubPeer comment" buttons each
run `run()` as a background job (the model calls take minutes; a request
through the tunnel may not):

1. author addresses -- handed in by the webapp, which reads them from the
   paper's XML (`webapp/lib/emails.ts`); the JATS XML is read here only when
   none are given (the CLI). An email copies them; a PubPeer comment offers
   them for PubPeer's "notify authors" field;
2. journal contacts (email only) -- found by `claude -p` with web search,
   cached per journal in `JOURNAL_CONTACTS.json` at the project root. Every
   address must come with the page it was read from, and that page is
   fetched here (a GET, nothing else) to check the address is really on it:
   a model without that check fills in plausible addresses from memory;
3. the draft -- `claude -p` (Opus by default) from the paper's metadata,
   findings, triage note and reproduction repository README.

Progress is written to `<paper>/drafts/job-<kind>.json`, the result to
`<paper>/drafts/<kind>-<stamp>.json`. NOTHING IS SENT OR POSTED: the
reviewer sends the email from their own mail program and pastes the comment
into PubPeer.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DRAFTS_DIRNAME = "drafts"
KINDS = ("email", "pubpeer")


def _is_partial(doc: dict) -> bool:
    pipeline = doc.get("pipeline")
    return isinstance(pipeline, dict) and pipeline.get("complete_review") is False


def _findings_payload(paper_dir: Path, finding_ids: list[str] | None) -> dict | None:
    docs = sorted(paper_dir.glob("forensic_review*/findings.v2.json")) \
        + list(paper_dir.glob("findings.v2.json"))
    if not docs:
        return None
    loaded = []
    for p in docs:
        # One unreadable historical document must not block drafting from a
        # valid review beside it.
        try:
            d = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            loaded.append(d)
    if not loaded:
        return None
    # A COMPLETE REVIEW BY DEFAULT. A partial pipeline (one tool, no
    # adjudicator) is drafted from only when the caller names its findings,
    # and then its scope travels in the payload so the draft can say it.
    complete = [d for d in loaded if not _is_partial(d)]
    if complete:
        doc = complete[-1]
    elif finding_ids:
        doc = loaded[-1]
    else:
        return {"paper_id": None, "findings": [], "partial_only": True}
    if finding_ids and not any(
            f.get("finding_id") in finding_ids or f.get("slug") in finding_ids
            for f in doc.get("findings") or [] if isinstance(f, dict)):
        # Named findings may live in a partial experiment.
        doc = next((d for d in reversed(loaded) if any(
            f.get("finding_id") in finding_ids or f.get("slug") in finding_ids
            for f in d.get("findings") or [] if isinstance(f, dict))), doc)
    rows = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
    if finding_ids:
        wanted = {i.strip() for i in finding_ids if i.strip()}
        rows = [f for f in rows
                if f.get("finding_id") in wanted or f.get("slug") in wanted]
    else:
        rows = [f for f in rows
                if f.get("outcome") == "problem"
                and (f.get("adjudication") or {}).get("action") != "discarded"]
    keep = ("finding_id", "slug", "title", "description", "location",
            "severity", "severity_is_provisional", "impossible", "quote",
            "reproduction", "technique", "producer")
    return {"paper_id": doc.get("paper_id"),
            "paper_metadata": doc.get("paper_metadata") or {},
            "adjudication_summary": (doc.get("adjudication") or {}).get("summary"),
            **({"pipeline_scope": (
                f"PARTIAL PIPELINE {doc['pipeline'].get('name')!r}: not a "
                "complete review; modules run: "
                + ", ".join(str(m.get("use")) for m in doc["pipeline"].get(
                    "modules") or [] if isinstance(m, dict))
                + ". Say so in the draft.")} if _is_partial(doc) else {}),
            "findings": [{k: f.get(k) for k in keep if f.get(k) is not None}
                         for f in rows]}

CONTACTS_FILE = "JOURNAL_CONTACTS.json"
LOOKUP_MODEL = "sonnet"
DRAFT_MODEL = "opus"
CONTACTS_MAX_AGE = timedelta(days=180)
_LOOKUP_TIMEOUT_S = 900
_DRAFT_TIMEOUT_S = 420
_README_CHARS = 14_000
_FINDINGS_CHARS = 16_000
STEPS = {"email": ("authors", "contacts", "draft"), "pubpeer": ("authors", "draft")}

ADDRESS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


# ---------------------------------------------------------------- the paper

def _xml_path(paper_dir: Path) -> Path | None:
    own = paper_dir / f"{paper_dir.name}.xml"
    if own.is_file():
        return own
    found = sorted(paper_dir.glob("*.xml"))
    return found[0] if found else None


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def paper_facts(paper_dir: Path) -> dict:
    """Title, DOI, journal, ISSNs, publisher, authors, the handling editor
    the XML names, and the addresses it marks as corresponding."""
    meta = _read_json(paper_dir / "metadata.json") or {}
    facts = {
        "title": meta.get("title") or "",
        "doi": meta.get("doi") or "",
        "journal": meta.get("journal_normalized") or meta.get("journal") or "",
        "authors": meta.get("authors") or "",
        "year": meta.get("year"),
        "issns": [], "publisher": "", "handling_editor": "",
        "xml_emails": [], "corresponding": [],
    }
    xml_file = _xml_path(paper_dir)
    if xml_file is None:
        return facts
    xml = xml_file.read_text(encoding="utf-8", errors="replace")
    if not facts["journal"]:
        m = re.search(r"<journal-title>(.*?)</journal-title>", xml, re.S)
        facts["journal"] = _strip(m.group(1)) if m else ""
    if not facts["title"]:
        m = re.search(r"<article-title>(.*?)</article-title>", xml, re.S)
        facts["title"] = _strip(m.group(1)) if m else ""
    if not facts["doi"]:
        m = re.search(r'<article-id pub-id-type="doi">(.*?)</article-id>', xml)
        facts["doi"] = _strip(m.group(1)) if m else ""
    facts["issns"] = list(dict.fromkeys(_strip(i) for i in re.findall(r"<issn\b[^>]*>(.*?)</issn>", xml, re.S)))
    m = re.search(r"<publisher-name>(.*?)</publisher-name>", xml, re.S)
    facts["publisher"] = _strip(m.group(1)) if m else ""
    m = re.search(r'<contrib\b[^>]*contrib-type="editor"[^>]*>(.*?)</contrib>', xml, re.S)
    if m:
        given = re.search(r"<given-names>(.*?)</given-names>", m.group(1), re.S)
        surname = re.search(r"<surname>(.*?)</surname>", m.group(1), re.S)
        name = " ".join(_strip(x.group(1)) for x in (given, surname) if x)
        facts["handling_editor"] = name or _strip(m.group(1)).replace(" Editor", "").strip()
    facts["xml_emails"] = list(dict.fromkeys(
        _strip(e).lower() for e in re.findall(r"<email\b[^>]*>(.*?)</email>", xml, re.S) if "@" in e))
    # A corresponding author: <contrib corresp="yes"> with its own <email>, or
    # the address inside a <corresp> note.
    corr = []
    for c in re.findall(r'<contrib\b[^>]*corresp="yes"[^>]*>(.*?)</contrib>', xml, re.S):
        corr += re.findall(r"<email\b[^>]*>(.*?)</email>", c, re.S)
    for c in re.findall(r"<corresp\b[^>]*>(.*?)</corresp>", xml, re.S):
        corr += re.findall(r"<email\b[^>]*>(.*?)</email>", c, re.S)
    facts["corresponding"] = list(dict.fromkeys(_strip(e).lower() for e in corr))
    return facts


# ---------------------------------------------------------- the model calls

def _run_claude(prompt: str, system: str, model: str, tools: str, schema: dict,
                timeout_s: int, budget_usd: float, run_cli=None) -> tuple[dict | None, str | None]:
    """One `claude -p` call returning a JSON object, or `(None, reason)`."""
    argv = ["claude", "-p", "--model", model, "--tools", tools,
            "--append-system-prompt", system,
            "--permission-mode", "bypassPermissions",
            "--output-format", "json",
            "--json-schema", json.dumps(schema),
            "--max-budget-usd", str(budget_usd)]

    def default(a, text):
        # A scratch folder: no project CLAUDE.md or settings is read into it.
        with tempfile.TemporaryDirectory(prefix="email-draft-") as cwd:
            return subprocess.run(a, input=text, capture_output=True, text=True,
                                  timeout=timeout_s, cwd=cwd)

    try:
        proc = (run_cli or default)(argv, prompt)
    except FileNotFoundError:
        return None, "the claude CLI is not on PATH"
    except subprocess.TimeoutExpired:
        return None, f"the model call timed out ({timeout_s}s)"
    if proc.returncode != 0:
        return None, f"claude exited {proc.returncode}: {(proc.stderr or proc.stdout or '')[:300]}"
    try:
        envelope = json.loads(proc.stdout)
    except ValueError:
        envelope = {"result": proc.stdout}
    if isinstance(envelope, dict) and envelope.get("is_error"):
        return None, f"the model call failed: {str(envelope.get('result') or envelope.get('subtype'))[:300]}"
    out = envelope.get("structured_output") if isinstance(envelope, dict) else None
    if not isinstance(out, dict):
        text = str(envelope.get("result") if isinstance(envelope, dict) else envelope or "")
        m = re.search(r"\{.*\}", text, re.S)
        try:
            out = json.loads(m.group(0)) if m else None
        except ValueError:
            out = None
    if not isinstance(out, dict):
        return None, "the model did not return the JSON asked for"
    return out, None


_LOOKUP_SYSTEM = """You find the email addresses to write to about a
concern with a published article. Use web search and fetch pages to read
them. Rules, non-negotiable:
- Only report an address you have READ on a web page, and give that page's
  URL as source_url. The address must appear on that page as written.
- Never construct, guess or complete an address from a name or a domain
  pattern. An address you did not read is left out.
- Prefer the journal's and publisher's own pages (editorial board, contact,
  "publication ethics" / "research integrity" pages) and the editor's
  institutional page.
- At most 6 contacts. Fewer is fine; none is fine."""

_CONTACT_SCHEMA = {
    "type": "object",
    "properties": {
        "contacts": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string", "enum": [
                    "handling editor", "editor-in-chief", "editorial office",
                    "research integrity", "other"]},
                "email": {"type": "string"},
                "source_url": {"type": "string"},
            },
            "required": ["name", "role", "email", "source_url"]}},
        "notes": {"type": "string"},
    },
    "required": ["contacts"],
}


def _lookup_prompt(facts: dict, want_journal: bool) -> str:
    asks = []
    if facts.get("handling_editor"):
        asks.append(f"- the handling (academic) editor of this article, {facts['handling_editor']}, "
                    "as named in the article: their email address (role \"handling editor\");")
    if want_journal:
        asks += ["- the journal's editor-in-chief (or chief editors) and the editorial office "
                 "(roles \"editor-in-chief\", \"editorial office\");",
                 "- the publisher's research-integrity / publication-ethics contact for this "
                 "journal (role \"research integrity\")."]
    return "\n".join([
        "Find these contacts:",
        *asks,
        "",
        "The article:",
        f"- title: {facts.get('title')}",
        f"- DOI: {facts.get('doi')} (https://doi.org/{facts.get('doi')})",
        f"- journal: {facts.get('journal')}",
        f"- ISSN: {', '.join(facts.get('issns') or []) or 'unknown'}",
        f"- publisher: {facts.get('publisher') or 'unknown'}",
        f"- year: {facts.get('year') or 'unknown'}",
    ])


# ------------------------------------------------- checking an address's page

_CF_EMAIL = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')


def _cf_decode(hexstr: str) -> str:
    """Cloudflare's email protection: the first byte is the XOR key."""
    try:
        data = bytes.fromhex(hexstr)
        return "".join(chr(b ^ data[0]) for b in data[1:])
    except ValueError:
        return ""


def page_addresses(page: str) -> set[str]:
    """Every address a page shows, including `name [at] host [dot] org`
    spellings, HTML entities, mailto links and Cloudflare-protected ones."""
    text = html.unescape(page)
    text = re.sub(r"\s*(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\})\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\})\s*", ".", text, flags=re.I)
    found = {a.lower().rstrip(".") for a in ADDRESS.findall(text)}
    found |= {_cf_decode(h).lower() for h in _CF_EMAIL.findall(page)}
    return {a for a in found if a}


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) metascience-email-check/1.0",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read(4_000_000).decode("utf-8", errors="replace")


def check_contacts(contacts: list[dict], fetch=None) -> list[dict]:
    """Mark each contact `verified` when its address is on its source page."""
    fetch = fetch or fetch_page
    pages: dict[str, set[str] | str] = {}
    out = []
    for c in contacts:
        email = str(c.get("email") or "").strip().lower()
        url = str(c.get("source_url") or "").strip()
        row = {"name": str(c.get("name") or "").strip(), "role": str(c.get("role") or "other"),
               "email": email, "source_url": url, "verified": False, "check": ""}
        if not ADDRESS.fullmatch(email):
            continue
        if not re.match(r"https?://", url):
            row["check"] = "no source page given"
        else:
            if url not in pages:
                try:
                    pages[url] = page_addresses(fetch(url))
                except Exception as e:  # noqa: BLE001 -- any fetch failure is "unchecked"
                    pages[url] = f"the source page could not be read ({str(e)[:120]})"
            got = pages[url]
            if isinstance(got, str):
                row["check"] = got
            elif not got:
                # A bot wall (a CAPTCHA page, a 'checking your browser' page)
                # shows no address at all: that is unchecked, not absent.
                row["check"] = "the source page could not be checked (it shows no addresses; it may be blocked)"
            elif email in got:
                row["verified"] = True
                row["check"] = "address found on the source page"
            else:
                row["check"] = "address NOT found on the source page"
        out.append(row)
    return out


# ------------------------------------------------------ the journal contacts

def journal_key(facts: dict) -> str:
    issns = sorted(i for i in facts.get("issns") or [] if i)
    if issns:
        return "issn:" + issns[0]
    return "journal:" + re.sub(r"[^a-z0-9]+", " ", str(facts.get("journal") or "").lower()).strip()


def cached_contacts(contacts_file: Path, key: str, now: datetime | None = None) -> dict | None:
    entry = (_read_json(contacts_file) or {}).get(key)
    if not isinstance(entry, dict):
        return None
    try:
        at = datetime.strptime(str(entry.get("looked_up_at")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return entry if (now or _now()) - at < CONTACTS_MAX_AGE else None


def store_contacts(contacts_file: Path, key: str, entry: dict) -> None:
    data = _read_json(contacts_file) or {}
    data[key] = entry
    _write_json(contacts_file, data)


def find_contacts(facts: dict, contacts_file: Path, model: str = LOOKUP_MODEL,
                  run_cli=None, fetch=None) -> tuple[list[dict], str]:
    """The journal's contacts (cached) plus the article's handling editor.
    Returns `(contacts, note)`; raises nothing."""
    key = journal_key(facts)
    hit = cached_contacts(contacts_file, key)
    want_journal = hit is None
    want_editor = bool(facts.get("handling_editor"))
    journal_rows = list(hit["contacts"]) if hit else []
    editor_rows: list[dict] = []
    note = f"journal contacts from the cache ({hit['looked_up_at'][:10]})" if hit else ""
    if want_journal or want_editor:
        out, err = _run_claude(_lookup_prompt(facts, want_journal), _LOOKUP_SYSTEM, model,
                               "WebSearch,WebFetch", _CONTACT_SCHEMA, _LOOKUP_TIMEOUT_S, 3.0, run_cli)
        if err:
            return journal_rows, (note + "; " if note else "") + f"lookup failed: {err}"
        rows = check_contacts([c for c in out.get("contacts") or [] if isinstance(c, dict)], fetch)
        editor_rows = [r for r in rows if r["role"] == "handling editor"]
        if want_journal:
            journal_rows = [r for r in rows if r["role"] != "handling editor"]
            store_contacts(contacts_file, key, {
                "journal": facts.get("journal"), "issns": facts.get("issns"),
                "looked_up_at": _iso(_now()), "model": model,
                "contacts": journal_rows, "notes": str(out.get("notes") or "")[:600]})
            note = f"journal contacts looked up now ({len(journal_rows)} found)"
        if want_editor:
            note += f"; handling editor {facts['handling_editor']}: " + (
                "address found" if editor_rows else "no address found")
    seen, merged = set(), []
    for r in editor_rows + journal_rows:
        if r["email"] not in seen:
            seen.add(r["email"])
            merged.append(r)
    return merged, note


# --------------------------------------------------------------- the draft

_RULES = """- Describe inconsistencies, never intent. Banned words: fabricated,
  fabrication, fraud, fraudulent, manipulated, manipulation, misconduct,
  fake. Keep the strength of language within what the findings state;
  provisional findings stay provisional, and an innocent explanation the
  notes give (e.g. simulated data disclosed elsewhere) is mentioned.
- State what was found with its numbers (which figure or table, how many
  values, what they match). Quote the paper only where a few words settle a
  point.
- When a reproduction repository URL is given, point to it in one line. When
  none is given, say the reproduction code is available on request.
The reviewer's notes (triage note, repository README) are the reviewed
account: where they and the raw findings differ, follow the notes."""

_SYSTEM = {
    "email": """You draft one short email from a research-integrity
reviewer to a journal's editors, with the article's authors in copy.
Rules, non-negotiable:
- Very concise and to the point: 120-200 words in the body. No filler, no
  flattery, no background on what the reviewer's project is.
- Name the article by title, journal and DOI in the first sentence.
- Ask the editors to assess the matter and the authors to clarify (for
  instance, to share the raw data).
- Greet the editors (by name when given) and the authors (the corresponding
  author by name when known). Sign with the reviewer's name only.
- Plain text, no markdown. The subject line is short and factual, without
  accusations.
""" + _RULES,
    "pubpeer": """You draft one short PubPeer comment for a
research-integrity reviewer. PubPeer readers know the article (the comment
is posted on its page), so do not restate its title or DOI.
Rules, non-negotiable:
- Very concise and to the point: 80-180 words. No greeting, no sign-off, no
  filler, no background on what the reviewer's project is.
- Lead with the observation; then the evidence with its numbers; then a
  one-line invitation to the authors to clarify (for instance, to share the
  raw data).
- PubPeer markdown is fine: short paragraphs or a short bullet list. The
  subject field is unused: return an empty string for it.
""" + _RULES,
}

_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"],
}


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "\n[... truncated]"


def draft_prompt(kind: str, facts: dict, to: list[dict], cc: list[str], who: str,
                 findings: dict | None, triage: str, readme: str, repo_url: str) -> str:
    parts = [
        "Draft the email." if kind == "email" else "Draft the PubPeer comment.",
        "",
        "ARTICLE",
        json.dumps({k: facts.get(k) for k in ("title", "journal", "doi", "authors", "year",
                                              "handling_editor")}, ensure_ascii=False, indent=1),
        "",
    ]
    if kind == "email":
        parts += [
            "TO (editors): " + ("; ".join(f"{c.get('name') or '?'} ({c.get('role')})" for c in to) or "the editors"),
            "CC (authors): " + (", ".join(cc) or "none found")
            + (f"; corresponding: {', '.join(facts.get('corresponding') or [])}" if facts.get("corresponding") else ""),
            f"REVIEWER (sign as): {who}" if who
            else "REVIEWER (sign as): unknown -- end with the placeholder [Your name]",
        ]
    parts.append(f"REPRODUCTION REPOSITORY: {repo_url}" if repo_url
                 else "REPRODUCTION REPOSITORY: none public -- say the code is available on request")
    if triage.strip():
        parts += ["", "TRIAGE NOTE", _clip(triage.strip(), 8000)]
    if readme.strip():
        parts += ["", "REPOSITORY README", _clip(readme.strip(), _README_CHARS)]
    if findings and findings.get("findings"):
        parts += ["", "FINDINGS (structured)", _clip(json.dumps(findings, indent=1, default=str), _FINDINGS_CHARS)]
    return "\n".join(parts)


def _repo_readme(paper_dir: Path) -> str:
    for sub in sorted(paper_dir.iterdir()):
        if sub.is_dir() and not sub.is_symlink() and (sub / ".git").exists():
            f = sub / "README.md"
            if f.is_file() and not f.is_symlink():
                return f.read_text(encoding="utf-8", errors="replace")
    return ""


# ----------------------------------------------------------------- the job

def job_file(paper_dir: Path, kind: str) -> Path:
    return paper_dir / DRAFTS_DIRNAME / f"job-{kind}.json"


class Job:
    def __init__(self, paper_dir: Path, kind: str):
        self.file = job_file(paper_dir, kind)
        self.state = {"kind": kind, "state": "running", "pid": os.getpid(), "started_at": _iso(_now()),
                      "steps": [{"name": s, "status": "pending", "detail": ""} for s in STEPS[kind]]}

    def step(self, name: str, status: str, detail: str = "") -> None:
        for s in self.state["steps"]:
            if s["name"] == name:
                s["status"], s["detail"] = status, detail
        _write_json(self.file, self.state)

    def finish(self, state: str, **extra) -> None:
        self.state.update(state=state, finished_at=_iso(_now()), **extra)
        _write_json(self.file, self.state)


def running_job(paper_dir: Path, kind: str) -> dict | None:
    """The job of this kind under way for this paper (by another process)."""
    job = _read_json(job_file(paper_dir, kind))
    if (isinstance(job, dict) and job.get("state") == "running"
            and job.get("pid") != os.getpid() and pid_alive(job.get("pid"))):
        return job
    return None


def _excluding(payload: dict | None, exclude: list[str]) -> dict | None:
    """The findings payload without the findings a reviewer ruled out."""
    if not payload or not exclude:
        return payload
    out = set(exclude)
    return {**payload, "findings": [f for f in payload.get("findings") or []
                                    if f.get("finding_id") not in out and f.get("slug") not in out]}


def run(paper_dir: str | Path, kind: str = "email", authors: list[str] | None = None, who: str = "",
        repo_url: str = "", repo_visibility: str = "", contacts_dir: str | Path | None = None,
        exclude: list[str] | None = None, draft_model: str = DRAFT_MODEL,
        lookup_model: str = LOOKUP_MODEL, run_cli=None, fetch=None) -> dict:
    """The whole workflow. Returns `{ok, path, draft}` or `{ok: False, error}`;
    never raises, never sends or posts."""
    paper_dir = Path(paper_dir)
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown draft kind {kind!r}"}
    if not paper_dir.is_dir():
        return {"ok": False, "error": f"no paper folder {paper_dir}"}
    other = running_job(paper_dir, kind)
    if other:
        return {"ok": False, "error": f"this {kind} draft is already being made (pid {other.get('pid')})"}
    job = Job(paper_dir, kind)

    def refuse(msg: str) -> dict:
        # The pane polls the job file, so a refusal is written there too.
        job.finish("error", error=msg)
        return {"ok": False, "error": msg}

    triage = (paper_dir / "rng_triage.md").read_text(encoding="utf-8", errors="replace") \
        if (paper_dir / "rng_triage.md").is_file() else ""
    readme = _repo_readme(paper_dir)
    findings = _findings_payload(paper_dir, None)
    if findings and findings.get("partial_only"):
        findings = None
        if not (triage.strip() or readme.strip()):
            return refuse("this paper has only partial-pipeline runs and no triage note "
                          "or repository README to draft from")
    findings = _excluding(findings, exclude or [])
    if not ((findings and findings.get("findings")) or triage.strip() or readme.strip()):
        return refuse("nothing to draft from: no findings.v2.json problems, "
                      "triage note or repository README")
    job.step("authors", "running")
    try:
        facts = paper_facts(paper_dir)
        cc = list(dict.fromkeys(a.strip().lower() for a in (authors or facts["xml_emails"]) if "@" in a))
        job.step("authors", "done", f"{len(cc)} address(es)" if cc else "no address found in the paper")

        to, note = [], ""
        if kind == "email":
            job.step("contacts", "running", "looking up the journal's editors (web search)")
            contacts_file = Path(contacts_dir or paper_dir.parent) / CONTACTS_FILE
            to, note = find_contacts(facts, contacts_file, lookup_model, run_cli, fetch)
            verified = sum(1 for c in to if c["verified"])
            job.step("contacts", "done" if to else "warning",
                     f"{len(to)} contact(s), {verified} verified on their source page" + (f" -- {note}" if note else ""))

        job.step("draft", "running", f"drafting with {draft_model}")
        public_url = repo_url if repo_url and repo_visibility.upper() == "PUBLIC" else ""
        prompt = draft_prompt(kind, facts, [c for c in to if c["verified"]] or to, cc, who,
                              findings, triage, readme, public_url)
        out, err = _run_claude(prompt, _SYSTEM[kind], draft_model, "", _DRAFT_SCHEMA,
                               _DRAFT_TIMEOUT_S, 3.0, run_cli)
        if err:
            job.step("draft", "error", err)
            job.finish("error", error=err)
            return {"ok": False, "error": err}
        stamp = _now().strftime("%Y%m%d-%H%M%S")
        draft = {
            "kind": kind, "created_at": _iso(_now()), "who": who, "model": draft_model,
            "paper": {k: facts.get(k) for k in ("title", "doi", "journal", "handling_editor")},
            "to": [{**c, "selected": c["verified"]} for c in to],
            "cc": [{"email": a, "selected": True, "corresponding": a in (facts.get("corresponding") or [])} for a in cc],
            "subject": str(out.get("subject") or "").strip() if kind == "email" else "",
            "body": str(out.get("body") or "").strip(),
            "repo_url": repo_url, "repo_visibility": repo_visibility,
            "contacts_note": note, "sent": None,
        }
        path = paper_dir / DRAFTS_DIRNAME / f"{kind}-{stamp}.json"
        _write_json(path, draft)
        job.step("draft", "done", path.name)
        job.finish("done", result=path.name)
        return {"ok": True, "path": str(path), "draft": draft}
    except Exception as e:  # noqa: BLE001 -- the job file must say why it stopped
        msg = f"{type(e).__name__}: {e}"[:500]
        for s in job.state["steps"]:
            if s["status"] == "running":
                s["status"], s["detail"] = "error", msg
        job.finish("error", error=msg)
        return {"ok": False, "error": msg}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paper_dir")
    ap.add_argument("--kind", choices=KINDS, default="email")
    ap.add_argument("--authors", default="", help="comma-separated author addresses (default: the paper XML's)")
    ap.add_argument("--who", default="")
    ap.add_argument("--repo-url", default="")
    ap.add_argument("--repo-visibility", default="")
    ap.add_argument("--contacts-dir", default=None, help=f"folder of {CONTACTS_FILE} (default: the paper's parent)")
    ap.add_argument("--exclude", default="", help="comma-separated finding ids or slugs to leave out")
    ap.add_argument("--model", default=DRAFT_MODEL, help="drafting model")
    ap.add_argument("--lookup-model", default=LOOKUP_MODEL)
    a = ap.parse_args(argv)
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    rec = run(a.paper_dir, a.kind, split(a.authors) or None, a.who, a.repo_url, a.repo_visibility,
              a.contacts_dir, split(a.exclude), a.model, a.lookup_model)
    print(json.dumps({k: v for k, v in rec.items() if k != "draft"}, default=str))
    return 0 if rec.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
