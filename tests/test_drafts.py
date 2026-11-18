"""drafts: the email / PubPeer workflow with the model and the web faked.

Nothing here reaches a model or the network: `run_cli` and `fetch` are
injected. The checks: refusals are named and written to the job file, the
contact cache is used, an address is "verified" only when its source page
shows it, a private repository is never linked, and nothing is ever sent.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from forensic_metascience_ai_toolkit import drafts as D

XML = """<article><front><journal-meta><journal-title>Journal of Tests</journal-title>
<issn pub-type="epub">1234-5678</issn><publisher><publisher-name>Testpub</publisher-name></publisher>
</journal-meta><article-meta><article-id pub-id-type="doi">10.1234/x</article-id>
<pub-date pub-type="epub"><day>4</day><month>7</month><year>2022</year></pub-date>
<volume>13</volume><elocation-id>3853</elocation-id>
<contrib-group><contrib contrib-type="author" corresp="yes"><name><surname>Yan</surname>
<given-names>Li</given-names></name><email>yan@uni.edu</email></contrib>
<contrib contrib-type="author"><name><surname>Zhu</surname></name></contrib></contrib-group>
<contrib-group><contrib contrib-type="editor"><name><surname>Rivera</surname>
<given-names>Ana</given-names></name><role>Editor</role></contrib></contrib-group>
<author-notes><fn><p>Contact: <email>zhu@uni.edu</email></p></fn></author-notes>
</article-meta></front><back><ref-list><ref><volume>99</volume><fpage>1</fpage></ref></ref-list></back></article>"""


def _paper(tmp_path, readme="# Repo\n\n**Summary**\n\n- Figure 5 matches set.seed(1).\n", triage=""):
    paper = tmp_path / "proj" / "10.1234--x"
    run = paper / "forensic_review"
    run.mkdir(parents=True)
    (paper / "10.1234--x.xml").write_text(XML)
    (paper / "metadata.json").write_text(json.dumps({
        "title": "A trial", "doi": "10.1234/x", "journal_normalized": "Journal of Tests",
        "authors": "Li Yan, Q Zhu"}))
    (run / "findings.v2.json").write_text(json.dumps({
        "schema_version": "2.0", "paper_id": "10.1234--x",
        "findings": [
            {"finding_id": "f_keep", "slug": "rng1", "title": "Figure 5 values are R draws",
             "outcome": "problem", "description": "30 values equal set.seed(1) draws"},
            {"finding_id": "f_fp", "slug": "rng2", "title": "a false positive",
             "outcome": "problem", "description": "ruled out by the reviewer"},
            {"finding_id": "f_gone", "slug": "x", "title": "discarded", "outcome": "problem",
             "adjudication": {"action": "discarded"}},
        ]}))
    if readme:
        repo = paper / "Journal-2023-repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "README.md").write_text(readme)
    if triage:
        (paper / "rng_triage.md").write_text(triage)
    return paper


class FakeCli:
    """Answers the lookup call and the draft call; records the prompts."""

    def __init__(self, contacts=None, draft=None, fail=None):
        self.calls = []
        self.contacts = contacts if contacts is not None else [
            {"name": "Ana Rivera", "role": "handling editor", "email": "a.rivera@uni.es",
             "source_url": "https://uni.es/rivera"},
            {"name": "Editorial office", "role": "editorial office", "email": "jot@testpub.org",
             "source_url": "https://testpub.org/contact"},
            {"name": "Made up", "role": "editor-in-chief", "email": "guess@testpub.org",
             "source_url": "https://testpub.org/contact"},
        ]
        self.draft = draft or {"subject": "Figure 5 in 'A trial'", "body": "Dear Editors, ..."}
        self.fail = fail

    def __call__(self, argv, text):
        tools = argv[argv.index("--tools") + 1]
        self.calls.append({"argv": argv, "prompt": text, "tools": tools,
                           "model": argv[argv.index("--model") + 1]})
        if self.fail:
            return SimpleNamespace(returncode=3, stderr=self.fail, stdout="")
        out = {"contacts": self.contacts} if tools else self.draft
        return SimpleNamespace(returncode=0, stderr="",
                               stdout=json.dumps({"result": "", "structured_output": out}))


PAGES = {
    "https://uni.es/rivera": "<p>Ana Rivera, a.rivera [at] uni [dot] es</p>",
    "https://testpub.org/contact": '<a href="mailto:jot@testpub.org">write to us</a>',
}


def fetch(url):
    if url not in PAGES:
        raise OSError("404")
    return PAGES[url]


class TestPaperFacts:
    def test_reads_journal_editor_and_corresponding_author(self, tmp_path):
        f = D.paper_facts(_paper(tmp_path))
        assert f["issns"] == ["1234-5678"] and f["publisher"] == "Testpub"
        assert f["handling_editor"] == "Ana Rivera"
        assert f["xml_emails"] == ["yan@uni.edu", "zhu@uni.edu"]
        assert f["corresponding"] == ["yan@uni.edu"]


class TestCitation:
    def test_opening_sentence_plain_and_html(self, tmp_path):
        f = D.paper_facts(_paper(tmp_path))
        assert (f["volume"], f["pages"], f["year"]) == ("13", "3853", "2022"), "the article's, not a reference's"
        c = D.citation(f)
        assert c["plain"] == 'I am writing about "A trial", Journal of Tests 13, 3853 (2022), doi:10.1234/x.'
        assert c["html"] == ('I am writing about "<a href="https://doi.org/10.1234/x">A trial</a>", '
                             '<i>Journal of Tests</i> <b>13</b>, 3853 (2022), '
                             'doi:<a href="https://doi.org/10.1234/x">10.1234/x</a>.')

    def test_page_ranges_and_missing_parts(self):
        f = {"title": "T <b>", "journal": "J", "doi": "", "volume": "10", "pages": "1186\u20131199", "year": "2023"}
        assert D.citation(f)["plain"] == 'I am writing about "T <b>", J 10, 1186\u20131199 (2023).'
        assert "T &lt;b&gt;" in D.citation(f)["html"], "escaped"
        assert D.citation({"title": "T"})["plain"] == 'I am writing about "T".'
        assert D.citation({}) == {}

    def test_the_sentence_is_put_after_the_greeting_when_missing(self):
        s = 'I am writing about "T", J 1, 2 (2020), doi:10.1/x.'
        body = "Dear Editors,\n\nDear authors,\n\nI am writing about T in J.\n\nIn Figure 5 ..."
        assert D.place_citation(body, s) == f"Dear Editors,\n\nDear authors,\n\n{s}\n\nIn Figure 5 ..."
        assert D.place_citation(f"Dear Editors,\n\n{s}\n\nRest", s) == f"Dear Editors,\n\n{s}\n\nRest"


class TestAddressCheck:
    def test_spellings_entities_and_cloudflare_are_read(self):
        key = 0x42
        enc = bytes([key]) + bytes(ord(c) ^ key for c in "ed@j.org")
        page = (f'x &#97;&#64;b.org <span data-cfemail="{enc.hex()}"></span> '
                "c (at) d (dot) com")
        assert {"a@b.org", "ed@j.org", "c@d.com"} <= D.page_addresses(page)

    def test_only_an_address_on_its_page_is_verified(self):
        rows = D.check_contacts(FakeCli().contacts, fetch)
        by = {r["email"]: r for r in rows}
        assert by["a.rivera@uni.es"]["verified"] and by["jot@testpub.org"]["verified"]
        assert not by["guess@testpub.org"]["verified"]
        assert "NOT found" in by["guess@testpub.org"]["check"]

    def test_an_unreadable_page_is_unverified_not_an_error(self):
        rows = D.check_contacts([{"name": "x", "role": "other", "email": "x@y.org",
                                  "source_url": "https://nowhere.example"}], fetch)
        assert rows[0]["verified"] is False and "could not be read" in rows[0]["check"]

    def test_a_page_with_no_addresses_is_unchecked_not_absent(self):
        rows = D.check_contacts([{"name": "x", "role": "other", "email": "x@y.org",
                                  "source_url": "https://captcha.example"}],
                                lambda url: "<html>recaptcha challenge</html>")
        assert rows[0]["verified"] is False and "could not be checked" in rows[0]["check"]

    def test_a_malformed_address_is_dropped(self):
        assert D.check_contacts([{"email": "not an address", "source_url": "https://a"}], fetch) == []


class TestEmail:
    def test_the_whole_workflow(self, tmp_path):
        paper = _paper(tmp_path)
        cli = FakeCli()
        rec = D.run(paper, "email", who="Dan", run_cli=cli, fetch=fetch, exclude=["f_fp"])
        assert rec["ok"], rec
        d = rec["draft"]
        assert [c["email"] for c in d["to"]][0] == "a.rivera@uni.es", "the handling editor comes first"
        assert {c["email"]: c["selected"] for c in d["to"]} == {
            "a.rivera@uni.es": True, "jot@testpub.org": True, "guess@testpub.org": False}
        assert [c["email"] for c in d["cc"]] == ["yan@uni.edu", "zhu@uni.edu"]
        assert d["cc"][0]["corresponding"] and d["subject"] and d["sent"] is None
        lookup, draft = cli.calls
        assert lookup["tools"] == "WebSearch,WebFetch" and lookup["model"] == "sonnet"
        assert draft["tools"] == "" and draft["model"] == "opus"
        assert "Figure 5 values are R draws" in draft["prompt"]
        assert "a false positive" not in draft["prompt"], "excluded findings stay out"
        assert "discarded" not in draft["prompt"]
        assert "set.seed(1)" in draft["prompt"], "the README is in the context"
        assert "REVIEWER (sign as): Dan" in draft["prompt"]
        job = json.loads(D.job_file(paper, "email").read_text())
        assert job["state"] == "done" and [s["status"] for s in job["steps"]] == ["done"] * 3
        saved = json.loads(Path(rec["path"]).read_text())
        assert saved["body"].startswith('Dear Editors, ...\n\nI am writing about "A trial", Journal of Tests 13, 3853 (2022)')
        assert saved["citation"]["html"].startswith('I am writing about "<a href="https://doi.org/10.1234/x">')
        assert "OPENING SENTENCE (verbatim" in draft["prompt"]

    def test_journal_contacts_are_cached_per_journal(self, tmp_path):
        paper = _paper(tmp_path)
        D.run(paper, "email", run_cli=FakeCli(), fetch=fetch)
        cache = json.loads((paper.parent / D.CONTACTS_FILE).read_text())
        entry = cache["issn:1234-5678"]
        assert [c["email"] for c in entry["contacts"]] == ["jot@testpub.org", "guess@testpub.org"], \
            "the handling editor is the article's, not the journal's"
        cli = FakeCli(contacts=[])
        rec = D.run(paper, "email", run_cli=cli, fetch=fetch)
        assert "the cache" in rec["draft"]["contacts_note"]
        # The cache spares the journal search: only the handling editor is asked for.
        assert "editor-in-chief" not in cli.calls[0]["prompt"]
        assert "Ana Rivera" in cli.calls[0]["prompt"]

    def test_an_old_cache_entry_is_looked_up_again(self, tmp_path):
        f = tmp_path / D.CONTACTS_FILE
        old = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%SZ")
        f.write_text(json.dumps({"issn:1": {"looked_up_at": old, "contacts": []}}))
        assert D.cached_contacts(f, "issn:1") is None

    def test_the_repo_is_linked_even_while_private(self, tmp_path):
        cli = FakeCli()
        D.run(_paper(tmp_path), "email", repo_url="https://github.com/o/r",
              repo_visibility="PRIVATE", run_cli=cli, fetch=fetch)
        assert "REPRODUCTION REPOSITORY: https://github.com/o/r" in cli.calls[-1]["prompt"]
        cli = FakeCli()
        D.run(_paper(tmp_path / "b"), "email", run_cli=cli, fetch=fetch)
        assert "available on request" in cli.calls[-1]["prompt"], "no repository: code on request"
        assert "[Your name]" in cli.calls[-1]["prompt"], "no reviewer name: a placeholder, not a made-up one"

    def test_short_replay_scripts_are_in_the_context_long_ones_are_not(self, tmp_path):
        paper = _paper(tmp_path)
        repo = paper / "Journal-2023-repo"
        (repo / "replay.R").write_text("set.seed(1); z <- rnorm(270)\nround(23.26 + 5.38 * z[121:150], 2)\n")
        (repo / "replay.py").write_text("x = 1\n" * 3000)
        (repo / "analysis.R").write_text("not a replay script")
        cli = FakeCli()
        D.run(paper, "pubpeer", run_cli=cli)
        prompt = cli.calls[-1]["prompt"]
        assert "REPRODUCTION SCRIPT replay.R" in prompt and "rnorm(270)" in prompt
        assert "replay.py" not in prompt and "analysis.R" not in prompt
        assert "at most about 6" in cli.calls[-1]["argv"][cli.calls[-1]["argv"].index("--append-system-prompt") + 1]

    def test_a_failed_lookup_still_drafts(self, tmp_path):
        def cli(argv, text):
            if argv[argv.index("--tools") + 1]:
                return SimpleNamespace(returncode=1, stderr="no network", stdout="")
            return FakeCli()(argv, text)
        rec = D.run(_paper(tmp_path), "email", run_cli=cli, fetch=fetch)
        assert rec["ok"] and rec["draft"]["to"] == []
        assert "lookup failed" in rec["draft"]["contacts_note"]


class TestPubPeer:
    def test_no_contact_lookup_and_no_subject(self, tmp_path):
        paper = _paper(tmp_path)
        cli = FakeCli()
        rec = D.run(paper, "pubpeer", run_cli=cli, fetch=fetch)
        assert rec["ok"] and len(cli.calls) == 1 and cli.calls[0]["tools"] == ""
        assert rec["draft"]["subject"] == "" and rec["draft"]["to"] == []
        assert [c["email"] for c in rec["draft"]["cc"]] == ["yan@uni.edu", "zhu@uni.edu"]
        job = json.loads(D.job_file(paper, "pubpeer").read_text())
        assert [s["name"] for s in job["steps"]] == ["authors", "draft"]
        assert Path(rec["path"]).name.startswith("pubpeer-")


class TestRefusals:
    def test_model_failure_is_named_and_in_the_job_file(self, tmp_path):
        paper = _paper(tmp_path)
        rec = D.run(paper, "pubpeer", run_cli=FakeCli(fail="boom"), fetch=fetch)
        assert rec["ok"] is False and "exited 3" in rec["error"]
        job = json.loads(D.job_file(paper, "pubpeer").read_text())
        assert job["state"] == "error" and job["steps"][-1]["status"] == "error"

    def test_bad_model_json_is_a_refusal(self, tmp_path):
        def cli(argv, text):
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({"result": "sorry"}))
        rec = D.run(_paper(tmp_path), "pubpeer", run_cli=cli)
        assert rec["ok"] is False and "JSON" in rec["error"]

    def test_nothing_to_draft_from(self, tmp_path):
        (tmp_path / "p").mkdir()
        rec = D.run(tmp_path / "p", "pubpeer", run_cli=FakeCli())
        assert rec["ok"] is False and "nothing to draft from" in rec["error"]
        assert json.loads(D.job_file(tmp_path / "p", "pubpeer").read_text())["state"] == "error"

    def test_a_running_job_refuses_a_second(self, tmp_path):
        paper = _paper(tmp_path)
        D.job_file(paper, "email").parent.mkdir(parents=True, exist_ok=True)
        D.job_file(paper, "email").write_text(json.dumps({"state": "running", "pid": os.getppid()}))
        rec = D.run(paper, "email", run_cli=FakeCli(), fetch=fetch)
        assert rec["ok"] is False and "already" in rec["error"]
        assert D.run(paper, "pubpeer", run_cli=FakeCli())["ok"], "the other kind is independent"

    def test_a_dead_job_does_not_block(self, tmp_path):
        paper = _paper(tmp_path)
        D.job_file(paper, "email").parent.mkdir(parents=True, exist_ok=True)
        D.job_file(paper, "email").write_text(json.dumps({"state": "running", "pid": 999_999_999}))
        assert D.run(paper, "email", run_cli=FakeCli(), fetch=fetch)["ok"]

    def test_unknown_kind(self, tmp_path):
        assert "unknown" in D.run(tmp_path, "letter")["error"]


def test_the_module_never_sends_or_posts():
    import inspect
    src = inspect.getsource(D)
    for banned in ("smtplib", "import requests", "httpx", "pubpeer.com/api", "method=\"POST\""):
        assert banned not in src, banned
    # The one network call is the GET that reads an address's source page.
    assert len(re.findall(r"urllib\.request\.urlopen", src)) == 1
