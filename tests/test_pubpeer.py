"""PubPeer is GROUND TRUTH, so its failure modes corrupt measurement itself.

Everywhere else in this codebase a refusal that reads as an empty result costs
us a finding. Here it costs us the SCORE: a paper we failed to look up, scored
as a paper with nothing to find, silently inflates every recall number we
report. These tests pin that the two are distinguishable, and that the parser
works on a real page with no network.

The fixture is a trimmed region of the live
`10.1002/acn3.321` publication page (15 comments, 14 comment images), captured
2026-08-17.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import pubpeer as PP

FIXTURE = Path(__file__).parent / "data" / "pubpeer_publication_page.html"


@pytest.fixture(scope="module")
def page() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class TestTheParserNeedsNoNetwork:
    def test_it_recovers_every_comment(self, page):
        assert len(PP.parse_comments(page)) == 15

    def test_it_recovers_the_comment_images(self, page):
        urls = PP.comment_images(PP.parse_comments(page))
        assert len(urls) == 14
        assert all(u.startswith("https://pubpeer.com/storage/") for u in urls)
        # GIFs matter: a blink comparison is the most direct statement a
        # sleuth makes about what they found.
        assert any(u.endswith(".gif") for u in urls)

    def test_a_comment_carries_readable_text(self, page):
        texts = [c["text"] for c in PP.parse_comments(page)]
        assert any("overlap" in t.lower() for t in texts)
        assert all("<" not in t for t in texts), "markup leaked into text"

    def test_an_empty_page_yields_no_comments_and_does_not_raise(self):
        assert PP.parse_comments("<html><body>nothing</body></html>") == []


class TestFigureLabelsAgreeSoftly:
    """`Figure 1C` and `Figure 1` are the same claim. `Figure 1C` and
    `Figure 2` are not. Exact-string scoring understated agreement on
    Masliah because the harvest drops the panel letter."""

    def test_panel_letter_agrees_with_the_bare_figure(self):
        assert PP.figures_agree(["Figure 1C"], ["Figure 1"])
        assert PP.figures_agree(["Fig. 1c"], ["Figure 1"])

    def test_the_same_panel_agrees_with_itself(self):
        assert PP.figures_agree(["Figure 3A"], ["Figure 3A"])

    def test_different_figures_do_not_agree(self):
        assert not PP.figures_agree(["Figure 1C"], ["Figure 2"])
        assert not PP.figures_agree(["Figure 1C"], ["Figure 1A"])

    def test_empty_either_side_is_unscorable_not_a_hit(self):
        assert not PP.figures_agree([], ["Figure 1"])
        assert not PP.figures_agree(["Figure 1"], [])
        assert not PP.figures_agree(["methods"], ["results"])


class TestARefusalIsNeverAnEmptyResult:
    """The distinction this whole module exists to preserve."""

    def test_a_403_is_a_named_refusal_not_zero_comments(self, monkeypatch):
        monkeypatch.setattr(PP, "_request",
                            lambda *a, **k: (None, PP._refusal(
                                "http_403", "blocked")))
        out = PP.fetch_comments("https://pubpeer.com/publications/X",
                                delay_s=0)
        assert out["ok"] is False
        assert out["refusal"] == "http_403"
        assert "comments" not in out
        assert "UNKNOWN, not empty" in out["warning"]

    def test_a_failed_lookup_batch_is_reported_not_dropped(self, monkeypatch):
        monkeypatch.setattr(PP, "_request",
                            lambda *a, **k: (None, PP._refusal(
                                "unreachable", "dns")))
        out = PP.lookup(["10.1/a", "10.1/b"], delay_s=0)
        assert out["records"] == {}
        assert out["refusals"] and out["refusals"][0]["dois"] == \
            ["10.1/a", "10.1/b"]

    def test_no_entry_and_could_not_ask_are_different(self, monkeypatch):
        """PubPeer answering "we have nothing on this" is a RESULT."""
        monkeypatch.setattr(PP, "_request", lambda *a, **k: (
            json.dumps({"status": "good", "feedbacks": []}).encode(), None))
        out = PP.lookup(["10.1/a"], delay_s=0)
        assert out["records"] == {} and out["refusals"] == []

    def test_unparseable_json_is_a_refusal(self, monkeypatch):
        monkeypatch.setattr(PP, "_request",
                            lambda *a, **k: (b"<html>cloudflare</html>", None))
        out = PP.lookup(["10.1/a"], delay_s=0)
        assert out["refusals"] and out["refusals"][0]["refusal"] == \
            "unparseable"


class TestTheCacheMakesItReplayable:
    def test_a_cached_lookup_makes_no_request(self, tmp_path, monkeypatch):
        cache = PP.Cache(tmp_path)
        payload = json.dumps({"status": "good", "feedbacks": [
            {"id": "10.1/a", "total_comments": 3}]}).encode()
        monkeypatch.setattr(PP, "_request", lambda *a, **k: (payload, None))
        first = PP.lookup(["10.1/a"], cache=cache, delay_s=0)
        assert first["records"]["10.1/a"]["total_comments"] == 3

        def _boom(*a, **k):
            raise AssertionError("the cache was not used")

        monkeypatch.setattr(PP, "_request", _boom)
        again = PP.lookup(["10.1/a"], cache=cache, delay_s=0)
        assert again["records"]["10.1/a"]["total_comments"] == 3

    def test_a_cached_page_makes_no_request(self, tmp_path, monkeypatch,
                                            page):
        cache = PP.Cache(tmp_path)
        monkeypatch.setattr(PP, "_request",
                            lambda *a, **k: (page.encode(), None))
        assert len(PP.fetch_comments("u", cache=cache,
                                     delay_s=0)["comments"]) == 15

        def _boom(*a, **k):
            raise AssertionError("the cache was not used")

        monkeypatch.setattr(PP, "_request", _boom)
        assert len(PP.fetch_comments("u", cache=cache,
                                     delay_s=0)["comments"]) == 15


class TestTheLabelIsAboutIMAGES:
    """PubPeer carries plenty of ordinary post-publication discussion.
    Counting that as a positive label would make the measured recall
    meaningless -- we would be scoring an image detector against comments
    about statistics."""

    def _c(self, text):
        return [{"inner_id": 1, "text": text, "images": []}]

    def test_an_image_comment_is_labelled(self):
        out = PP.image_integrity_labels(
            self._c("The panels in Figure 3A appear duplicated."))
        assert out["is_image_integrity"] is True
        assert out["figures"] == ["Figure 3A"]

    def test_an_ordinary_comment_is_not(self):
        out = PP.image_integrity_labels(
            self._c("The statistics in Figure 2 use the wrong test."))
        assert out["is_image_integrity"] is False
        assert out["figures"] == []

    def test_a_panel_letter_must_be_adjacent_to_its_number(self):
        """MEASURED on the real page: allowing whitespace read "Figure 5
        Western blot" as panel 5W, inventing a panel the paper has no such
        thing as -- and a figure-level score is only worth having if the
        figure labels are right."""
        out = PP.image_integrity_labels(
            self._c("Figure 5 Western blot bands look duplicated"))
        assert out["figures"] == ["Figure 5"]

    def test_it_reads_the_forms_sleuths_actually_write(self):
        for text, want in (("Fig. 2b overlaps", "Figure 2B"),
                           ("Fig 4 (C) is spliced", "Figure 4C"),
                           ("the blot in Fig 7 is reused", "Figure 7")):
            assert PP.image_integrity_labels(self._c(text))["figures"] == [want]

    def test_the_real_page_labels_the_figures_the_sleuths_named(self, page):
        out = PP.image_integrity_labels(PP.parse_comments(page))
        assert out["is_image_integrity"] is True
        assert "Figure 3A" in out["figures"]

    def test_it_records_an_allegation_and_nothing_more(self):
        """No severity, no verdict. A PubPeer comment is somebody else's
        claim, and restating it as our finding is the substitution this
        toolkit exists to catch."""
        out = PP.image_integrity_labels(self._c("Figure 1 is duplicated"))
        assert "severity" not in out and "verdict" not in out


class TestTheLookupIsNotTruncated:
    """MEASURED 2026-09-28: the v3 endpoint returns AT MOST 10 feedbacks per
    request (asking 1/5/10/20/50 DOIs that all have threads returned
    1/5/10/10/10). With the Zotero plugin's batch of 50, a corpus lookup
    silently lost every entry past the tenth in each batch -- 52 of 106
    known threads on the Berrio 2025 set -- and each loss read as "no PubPeer
    entry"."""

    @staticmethod
    def _capped_endpoint(calls):
        def fake(url, data=None, timeout=60):
            batch = json.loads(data)["dois"]
            calls.append(len(batch))
            fb = [{"id": d, "url": f"https://pubpeer.com/publications/{i}"}
                  for i, d in enumerate(batch)][:PP.V3_MAX_FEEDBACKS]
            return json.dumps({"feedbacks": fb}).encode(), None
        return fake

    def test_every_entry_is_found_when_every_doi_has_one(self, monkeypatch):
        calls: list[int] = []
        monkeypatch.setattr(PP, "_request", self._capped_endpoint(calls))
        dois = [f"10.1/{i}" for i in range(37)]
        out = PP.lookup(dois, delay_s=0)
        assert len(out["records"]) == 37
        assert max(calls) <= PP.V3_MAX_FEEDBACKS

    def test_a_saturated_oversized_batch_is_split_not_trusted(self, monkeypatch, tmp_path):
        calls: list[int] = []
        monkeypatch.setattr(PP, "_request", self._capped_endpoint(calls))
        monkeypatch.setattr(PP, "BATCH", 50)
        cache = PP.Cache(tmp_path)
        out = PP.lookup([f"10.1/{i}" for i in range(50)], cache=cache, delay_s=0)
        assert len(out["records"]) == 50
        # Halved until no answer is saturated (50 -> 25 -> 12/13 -> 6/7):
        # the unsaturated leaf requests partition the 50 DOIs exactly.
        assert calls[0] == 50
        assert sum(c for c in calls if c <= PP.V3_MAX_FEEDBACKS) == 50
        # The saturated answer was never cached as if it were complete.
        assert cache.get("lookup:" + "|".join(f"10.1/{i}" for i in range(50)), "json") is None


class TestFigureReferencesAreReadWhole:
    """MEASURED 2026-09-28 while building the Berrio 2025 set: the old single
    regex returned NOTHING for `Figure S4` / `Fig. S3B`, read `Supplementary
    Figure 4a` as main-text `Figure 4A`, and kept only the first item of
    `Figs. 2c, 2d` / `Fig. 3B-D` / `Figures 2 and 3`. A supplementary
    allegation therefore either vanished or was scored against the wrong
    picture, and every list lost all but its first figure."""

    @pytest.mark.parametrize("text,want", [
        ("Figure S4", ["Figure S4"]),
        ("Fig. S3B", ["Figure S3B"]),
        ("Figs S1 and S2", ["Figure S1", "Figure S2"]),
        ("Supplementary Figure 4a", ["Figure S4A"]),
        ("Suppl. Fig. 2 shows", ["Figure S2"]),
        ("Supplementary Figures 2 and 3", ["Figure S2", "Figure S3"]),
        ("Figure 4 and Supplementary Figure 2", ["Figure 4", "Figure S2"]),
        ("Figs. 2c, 2d", ["Figure 2C", "Figure 2D"]),
        ("Fig. 3B-D", ["Figure 3B", "Figure 3C", "Figure 3D"]),
        ("Fig. 3B–D overlap", ["Figure 3B", "Figure 3C", "Figure 3D"]),
        ("Fig. 4a-4c", ["Figure 4A", "Figure 4B", "Figure 4C"]),
        ("Figure 3(B-D)", ["Figure 3B", "Figure 3C", "Figure 3D"]),
        ("Fig. 3 (A and B)", ["Figure 3A", "Figure 3B"]),
        ("Fig. 2A,B", ["Figure 2A", "Figure 2B"]),
        ("Figure 3B and C.", ["Figure 3B", "Figure 3C"]),
        ("Figures 2 and 3", ["Figure 2", "Figure 3"]),
        ("Figures 2-4", ["Figure 2", "Figure 3", "Figure 4"]),
        ("Figure 2 and 3.", ["Figure 2", "Figure 3"]),
        # Extended Data keeps a plain number, as the caption parser does.
        ("Extended Data Fig. 3", ["Figure 3"]),
    ])
    def test_it_reads_supplements_lists_and_ranges(self, text, want):
        assert PP.figure_refs(text) == want

    @pytest.mark.parametrize("text,want", [
        # A bare letter after `and` must END the phrase to be a panel.
        ("Figure 3A and I think", ["Figure 3A"]),
        ("Figure 1, I think", ["Figure 1"]),
        # A bare number after `and` under a SINGULAR head must end the phrase.
        ("Figure 2 and 3 years later", ["Figure 2"]),
        ("Figure 5 Western blot", ["Figure 5"]),
        ("Figure 2019", []),
        ("fighting 3 times", []),
    ])
    def test_it_does_not_invent_figures(self, text, want):
        assert PP.figure_refs(text) == want

    def test_a_supplementary_figure_never_agrees_with_the_main_one(self):
        assert not PP.figures_agree(["Figure S4"], ["Figure 4"])
        assert not PP.figures_agree(["Supplementary Figure 4a"], ["Figure 4"])
        assert PP.figures_agree(["Figure S4A"], ["Figure S4"])
        assert PP.figures_agree(["Supplementary Figure 4a"], ["Figure S4"])

    def test_a_list_labels_every_figure_it_names(self):
        out = PP.image_integrity_labels(
            [{"inner_id": 1, "images": [],
              "text": "The blots in Figs. 2c, 2d and Supplementary Figure 3 are duplicated."}])
        assert out["figures"] == ["Figure 2C", "Figure 2D", "Figure S3"]


class TestItIsNotAForensicTool:
    def test_it_is_registered_nowhere(self):
        from forensic_metascience_ai_toolkit import registry
        names = {spec.name for spec in registry.SPECS}
        assert not any("pubpeer" in n for n in names)


class TestCommentTextIsDecoded:
    """The comment `html` is a JSON string. Left encoded, an en-dash range
    arrived as the six characters `\\u2013` and was never read as a range
    (82 of 489 Masliah comments carried escapes; panels lost on 3 papers,
    2026-09-28)."""
    def _page(self, body):
        q = "&quot;"
        return f'<div data="{{{q}inner_id{q}:1,{q}html{q}:{q}{body}{q},{q}x{q}:1}}">'

    def test_escapes_are_decoded_and_a_range_is_read(self):
        c = PP.parse_comments(self._page(r"Blots in Fig 7B–D are spliced.\nSee below."))[0]
        assert "\\u" not in c["text"] and "\\n" not in c["text"]
        assert PP.image_integrity_labels([c])["figures"] == ["Figure 7B", "Figure 7C", "Figure 7D"]

    def test_an_undecodable_body_is_kept_as_captured(self):
        c = PP.parse_comments(self._page(r"Figure 2 bad \x escape duplicated"))[0]
        assert "Figure 2" in c["text"]


class TestImageTermsFromTheMasliahThreads:
    """Phrasings found on real threads the first term list read as
    non-image (2026-09-28); each is an allegation, and each rejected term is
    a measured false positive that must stay out."""
    def _img(self, text):
        comment = {"inner_id": 1, "text": text, "images": []}
        return PP.image_integrity_labels([comment])["is_image_integrity"]

    @pytest.mark.parametrize("text", [
        "Figure 5A. Much more similar than expected.",
        "it looks remarkably similar to the left panel of Figure 4C in Crews et al.",
        "Figure 2E and F : These images are supposed to be derived from different mice. "
        "They are unexpectedly similar.",
        "concerns were raised regarding areas of high similarity in the Fig. 3b image.",
        "There appears to be a mix-up of the panels between the second and fourth rows.",
        "Figure 3k. Vertical, straight changes in background between samples.",
        "discovering an image re-use between Figures 3P and 4L.",
    ])
    def test_real_allegations_are_labelled(self, text):
        assert self._img(text)

    @pytest.mark.parametrize("text", [
        "iTSC1-KO mice had a phenotype similar to the one seen in the other model.",
        "it just looks like unspecific background, without discernable neurons.",
        "we inadvertently committed a copyediting error positioning the arrows in Figure 2A.",
    ])
    def test_measured_false_positives_stay_out(self, text):
        assert not self._img(text)
