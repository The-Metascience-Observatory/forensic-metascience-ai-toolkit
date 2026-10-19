"""PubPeer as a source of GROUND TRUTH, not as a source of findings.

Every number the image track has produced is a fire *rate*. None of it is a
measured *recall*, because no corpus told us what was actually there to find.
PubPeer does: its comments are where image sleuths -- Elisabeth Bik, Matthew
Schrag and others -- have already recorded, figure by figure, what they found.
Scoring against them is the only way to learn what the detector MISSES, which
no amount of calibrating false positives can tell us.

What is actually reachable (measured 2026-08-17, not taken from documentation):

  * `api.pubpeer.com/v1/publications/dump/...` -- **DEAD**. The host does not
    resolve. Every blog post and notebook citing it is stale, which is why
    this module does not offer it even as a fallback.
  * `POST pubpeer.com/v3/publications?devkey=...` with `{"dois": [...]}` --
    LIVE. Returns per-DOI METADATA ONLY: `total_comments`, `users`,
    `last_commented_at`, `url`. No comment text, no images.
  * `GET pubpeer.com/publications/{hash}` -- LIVE, and the comments are
    server-rendered into the page as an HTML-entity-encoded JSON blob. Each
    comment carries an `html` field with any `<img>` inline.
  * `GET pubpeer.com/storage/image-{epoch_ms}.{png,jpg,gif}` -- LIVE, no auth.
    This is where comment images live, and where marked-up figures and blink
    GIFs posted by sleuths can be read.

The v3 contract comes from PubPeer's own open-source Zotero plugin
(`pubpeer_zotero_plugin/content/pubpeer.ts`), which ships the public devkey
below. **If this is ever used for more than occasional research sweeps, ask
PubPeer for a key of our own** -- their FAQ invites contact, and a shared
plugin key is not a licence for bulk traffic.

Cloudflare rejects a default `urllib` User-Agent with 403. A browser UA is
required; that is the single non-obvious thing about the whole interface.

THE REFUSAL RULE, which matters more here than anywhere else in this codebase:
"PubPeer has no entry for this paper" and "we could not ask PubPeer" are
DIFFERENT FACTS. Collapsing the second into the first would silently inflate
every recall figure we report -- a paper we failed to look up would be scored
as a paper with nothing to find. Every failure path below returns a named
refusal and never an empty comment list.

Nothing here is a forensic tool. It carries no `severity`, is registered
nowhere, and is unreachable from either stage: a PubPeer allegation is
somebody else's claim, and restating it as our finding is exactly the
substitution this toolkit exists to catch.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Optional

#: The devkey PubPeer publishes in their own Zotero plugin. See the module
#: docstring: fine for a research sweep, ask for our own before anything more.
DEVKEY = "PubPeerZotero"

API_URL = "https://pubpeer.com/v3/publications"

#: Cloudflare 403s the urllib default. This is not evasion -- it is a real
#: browser string for a client that behaves like one: serial, rate-limited
#: and cached.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

#: The v3 endpoint answers AT MOST this many feedbacks per request, whatever
#: the batch size. MEASURED 2026-09-28 on DOIs that all have threads: asking
#: 1/5/10/20/50 returned 1/5/10/10/10. The Zotero plugin's 50 is safe for a
#: plugin looking up one library item at a time and silently lossy for a
#: corpus: on the Berrio 2025 set, 50-DOI batches found 54 of 106 papers
#: whose threads are linked in the review's own spreadsheet. Every dropped
#: entry read as "no PubPeer entry" -- absence read as evidence.
V3_MAX_FEEDBACKS = 10

#: DOIs per lookup call. At the cap, so a full answer is never ambiguous.
BATCH = V3_MAX_FEEDBACKS

#: Seconds between network calls. 117 pages is a trivial load if we are
#: careful and a rude one if we are not, so this is deliberately unhurried
#: and the fetches are deliberately serial.
DELAY_S = 1.5

_STORAGE_RE = re.compile(r"https://pubpeer\.com/storage/[A-Za-z0-9._-]+")


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def _refusal(kind: str, detail: str, **extra: Any) -> dict:
    """A failure that says what it is. NEVER an empty result."""
    return {
        "ok": False,
        "refusal": kind,
        "detail": detail,
        "warning": (
            f"PubPeer could not be read ({kind}): {detail}. This paper's "
            "PubPeer status is UNKNOWN, not empty -- do not score it as a "
            "paper with nothing to find."),
        **extra,
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class Cache:
    """Content-addressed disk cache. The eval suite must be able to replay a
    whole corpus offline, and we must never re-fetch a page we already hold."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, key: str, suffix: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.root / suffix.lstrip(".") / f"{digest}.{suffix.lstrip('.')}"

    def get(self, key: str, suffix: str) -> Optional[bytes]:
        path = self._path(key, suffix)
        try:
            return path.read_bytes()
        except OSError:
            return None

    def put(self, key: str, suffix: str, data: bytes) -> Path:
        path = self._path(key, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

def _request(url: str, data: Optional[bytes] = None,
             timeout: int = 60) -> tuple[Optional[bytes], Optional[dict]]:
    """(body, refusal). Exactly one is None."""
    headers = {"User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as exc:
        # 403 is the Cloudflare bot wall and 429 is rate limiting: both mean
        # "ask again later", never "there is nothing here".
        return None, _refusal(f"http_{exc.code}", f"{url} returned {exc.code}")
    except urllib.error.URLError as exc:
        return None, _refusal("unreachable", f"{url}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001 -- named, never silent
        return None, _refusal("error", f"{url}: {type(exc).__name__}: {exc}")


def lookup(dois: Iterable[str], cache: Optional[Cache] = None,
           delay_s: float = DELAY_S, devkey: str = DEVKEY) -> dict:
    """Which of these DOIs PubPeer has an entry for.

    Returns `{"records": {doi: record}, "refusals": [...], "asked": n}`.
    A DOI absent from `records` with no refusal against it genuinely has no
    PubPeer entry; a DOI in a failed batch is UNKNOWN and appears in
    `refusals`, so a caller can tell the two apart -- which is the whole
    point of this module.
    """
    dois = [d for d in dois if d]
    records: dict[str, dict] = {}
    refusals: list[dict] = []
    queue = [dois[i:i + BATCH] for i in range(0, len(dois), BATCH)]
    n_requests = 0
    while queue:
        batch = queue.pop(0)
        key = "lookup:" + "|".join(batch)
        body = cache.get(key, "json") if cache else None
        fresh = body is None
        if fresh:
            if n_requests and delay_s:
                time.sleep(delay_s)
            n_requests += 1
            body, refusal = _request(
                f"{API_URL}?devkey={devkey}",
                data=json.dumps({"dois": batch}).encode())
            if refusal is not None:
                refusal["dois"] = batch
                refusals.append(refusal)
                continue
        try:
            payload = json.loads(body)
        except ValueError as exc:
            refusals.append(_refusal("unparseable", str(exc), dois=batch))
            continue
        feedbacks = payload.get("feedbacks") or []
        if len(feedbacks) >= V3_MAX_FEEDBACKS and len(batch) > V3_MAX_FEEDBACKS:
            # A SATURATED answer: the endpoint may have dropped entries. Never
            # cache it and never read it as complete -- ask again in halves.
            half = len(batch) // 2
            queue[:0] = [batch[:half], batch[half:]]
            continue
        if fresh and cache:
            cache.put(key, "json", body)
        for rec in feedbacks:
            if rec.get("id"):
                records[str(rec["id"]).lower()] = rec
    return {"records": records, "refusals": refusals, "asked": len(dois)}


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def parse_comments(page: str) -> list[dict]:
    """Comments out of a publication page's embedded JSON.

    The page is server-rendered with the comment payload HTML-entity-encoded
    into an attribute, and the JSON inside escapes its slashes. Undo both,
    then read each comment's `inner_id` and `html`. Kept separate from the
    fetching so the parser can be tested on a saved fixture with no network.

    `html` is a JSON string, so its other escapes are decoded too. Left
    encoded, "Fig 7B\\u2013D" never read as a range and every comment carried
    literal `\\n` -- 82 of 489 Masliah comments, panels lost on 3 papers
    (measured 2026-09-28). An undecodable body is kept as captured.
    """
    text = _html.unescape(page).replace("\\/", "/")
    out: list[dict] = []
    for match in re.finditer(r'"inner_id":(\d+),"html":"(.*?)","', text,
                             re.S):
        body = match.group(2)
        try:
            body = json.loads(f'"{body}"', strict=False)
        except ValueError:
            pass
        out.append({
            "inner_id": int(match.group(1)),
            "html": body,
            "text": " ".join(re.sub(r"<[^>]+>", " ", body).split()),
            "images": sorted(set(_STORAGE_RE.findall(body))),
        })
    return out


def comment_images(comments: Iterable[dict]) -> list[str]:
    """Every distinct comment-image URL across these comments."""
    seen: list[str] = []
    for comment in comments:
        for url in comment.get("images") or []:
            if url not in seen:
                seen.append(url)
    return seen


def fetch_comments(url: str, cache: Optional[Cache] = None,
                   delay_s: float = DELAY_S) -> dict:
    """One publication page's comments, cached.

    Returns `{"ok": True, "url":..., "comments": [...], "images": [...]}` or
    a named refusal.
    """
    page = cache.get("page:" + url, "html") if cache else None
    if page is None:
        if delay_s:
            time.sleep(delay_s)
        body, refusal = _request(url)
        if refusal is not None:
            refusal["url"] = url
            return refusal
        page = body
        if cache:
            cache.put("page:" + url, "html", page)
    comments = parse_comments(page.decode("utf-8", "replace"))
    return {"ok": True, "url": url, "comments": comments,
            "images": comment_images(comments)}


def fetch_image(url: str, cache: Cache,
                delay_s: float = DELAY_S) -> dict:
    """One comment image, cached to disk. Marked-up figures and blink GIFs
    posted by sleuths are the most direct statement of what they found."""
    suffix = (url.rsplit(".", 1)[-1] or "png").lower()[:4]
    existing = cache.get("img:" + url, suffix)
    if existing is None:
        if delay_s:
            time.sleep(delay_s)
        body, refusal = _request(url)
        if refusal is not None:
            refusal["url"] = url
            return refusal
        existing = body
        cache.put("img:" + url, suffix, existing)
    return {"ok": True, "url": url, "bytes": len(existing),
            "path": str(cache._path("img:" + url, suffix))}


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

#: Words that put a figure reference in the SUPPLEMENT. In step with
#: `extraction.figures.SUPPLEMENTARY_PREFIX`, so `Supplementary Figure 4`
#: here and in a caption both become `Figure S4`; plus `Suppl.`, which
#: sleuths write and captions do not. `Extended Data` is deliberately NOT a
#: supplement word, matching the caption parser (prefix consumed, plain
#: number) until a corpus case shows otherwise.
_SUPP_WORD = r"(?:supplement(?:al|ary)?|suppl?\.?|supporting)"

#: The start of a figure reference: optional supplement word, then the
#: figure word. `plural` decides how freely a bare number after `and` may be
#: read as a second figure (see `figure_refs`).
_FIG_HEAD_RE = re.compile(
    r"(?P<supp>\b" + _SUPP_WORD + r"\s*)?"
    r"\bfig(?:ure)?(?P<plural>s)?\.?\s*",
    re.I)

#: One figure: an optional `S` glued to the number (`Figure S4`), the number,
#: and a panel spec. The panel letter must be ADJACENT to the number (or
#: parenthesised): allowing whitespace read "Figure 5 Western blot" as panel
#: 5W -- measured on a real page, which is how that rule was made. A panel
#: spec may be a list or range (`3B-D`, `2A,B`, `3(B and C)`).
_FIG_ITEM_RE = re.compile(
    r"(?P<s>[Ss](?=\d))?(?P<num>\d{1,3})(?!\d)"
    r"(?:\s*\((?P<pp>[A-Za-z](?:\s*(?:[-–—,/&]|and)\s*[A-Za-z])*)\)"
    r"|(?P<pb>[A-Za-z](?![A-Za-z])(?:\s*[-–—/]\s*[A-Za-z](?![A-Za-z])"
    r"|,[A-Za-z](?![A-Za-z]))*))?")

#: Kept for callers that only need WHERE a figure reference starts
#: (`build_discovery_corpus.py` in the sibling author_corpora/ folder
#: windows text around it). Labels
#: come from `figure_refs`, never from this pattern's groups.
_FIGURE_RE = re.compile(_FIG_HEAD_RE.pattern + _FIG_ITEM_RE.pattern, re.I)

_LIST_SEP_RE = re.compile(r"\s*(?:,\s*(?:and\b|&)?|\band\b|&|/)\s*", re.I)
_RANGE_SEP_RE = re.compile(r"\s*(?:[-–—]|\bto\b)\s*", re.I)
#: A bare panel letter continuing a list (`Figure 3B and C.`) must END the
#: phrase; otherwise "Figure 3A and I think" would read panel I.
_BARE_PANEL_RE = re.compile(r"([A-Za-z])(?![A-Za-z])(?=\s*(?:[,.;:)\]]|\band\b|&|$))")
_MAX_RANGE = 8


class FigureRef(NamedTuple):
    supplementary: bool
    number: int
    panel: str          # "" when no panel letter

    @property
    def label(self) -> str:
        return f"Figure {'S' if self.supplementary else ''}{self.number}{self.panel}"


def _letters(spec: str) -> list[str]:
    """Panel letters from a spec: `B-D` -> B C D; `A,B` / `B and C` -> A B."""
    out: list[str] = []
    toks = re.findall(r"[A-Za-z]|[-–—]", re.sub(r"\band\b", ",", spec))
    i = 0
    while i < len(toks):
        t = toks[i]
        if i + 2 < len(toks) and toks[i + 1] in "-–—" and toks[i + 2].isalpha():
            lo, hi = ord(t.upper()), ord(toks[i + 2].upper())
            if 0 <= hi - lo <= _MAX_RANGE:
                out += [chr(c) for c in range(lo, hi + 1)]
            else:
                out += [t.upper(), toks[i + 2].upper()]
            i += 3
            continue
        if t.isalpha():
            out.append(t.upper())
        i += 1
    return out


def parse_figure_refs(text: str) -> list[FigureRef]:
    """Every figure a piece of prose names, in order, without duplicates.

    Handles what sleuths actually write: `Fig. S3B`, `Supplementary Figure
    4a` (-> S4A), `Figs. 2c, 2d`, `Fig. 3B-D`, `Fig. 2A,B`, `Figures 2 and
    3`, `Figures 2-4`, `Figure 4 and Supplementary Figure 2`.

    The previous single regex read `Supplementary Figure 4a` as main-text
    `Figure 4A`, returned nothing at all for `Figure S4`, and kept only the
    first item of every list or range -- so a supplementary allegation either
    vanished or was scored against the wrong figure (measured 2026-09-28).
    """
    text = text or ""
    refs: list[FigureRef] = []

    def add(supp: bool, num: int, panels: list[str]) -> None:
        for p in panels or [""]:
            ref = FigureRef(supp, num, p)
            if ref not in refs:
                refs.append(ref)

    for head in _FIG_HEAD_RE.finditer(text):
        supp_head = bool(head.group("supp"))
        plural = bool(head.group("plural"))
        m = _FIG_ITEM_RE.match(text, head.end())
        if not m:
            continue
        prev_supp = supp_head or bool(m.group("s"))
        prev_num = int(m.group("num"))
        prev_panels = _letters(m.group("pp") or m.group("pb") or "")
        add(prev_supp, prev_num, prev_panels)
        pos = m.end()
        while True:
            rng = _RANGE_SEP_RE.match(text, pos)
            lst = None if rng else _LIST_SEP_RE.match(text, pos)
            sep = rng or lst
            if not sep:
                break
            nxt = _FIG_ITEM_RE.match(text, sep.end())
            if nxt:
                supp = supp_head or bool(nxt.group("s"))
                num = int(nxt.group("num"))
                panels = _letters(nxt.group("pp") or nxt.group("pb") or "")
                tail = text[nxt.end():nxt.end() + 2]
                ends_phrase = not re.match(r"\s*[A-Za-z]", tail)
                if rng and num == prev_num and prev_panels and panels:
                    # `4a-4c`: a panel range written with the number twice.
                    add(supp, num, _letters(f"{prev_panels[-1]}-{panels[-1]}"))
                elif rng and not prev_panels and not panels and plural and \
                        0 < num - prev_num <= _MAX_RANGE:
                    for n in range(prev_num + 1, num + 1):
                        add(supp, n, [])
                elif panels or plural or nxt.group("s") or ends_phrase:
                    # A bare number after `and` under a SINGULAR head is only
                    # a figure if it ends the phrase: "Figure 2 and 3 years
                    # later" is one figure, "Figure 2 and 3." is two.
                    add(supp, num, panels)
                else:
                    break
                prev_supp, prev_num, prev_panels = supp, num, panels
                pos = nxt.end()
                continue
            bare = _BARE_PANEL_RE.match(text, sep.end())
            if bare and prev_panels and bare.group(1).isupper() == prev_panels[-1].isupper() \
                    and (text[sep.start():sep.end()].strip() or "x") not in ("or",):
                letter = bare.group(1).upper()
                new = (_letters(f"{prev_panels[-1]}-{letter}") if rng else [letter])
                add(prev_supp, prev_num, new)
                prev_panels = new
                pos = bare.end()
                continue
            break
    return refs


def figure_refs(text: str) -> list[str]:
    """`parse_figure_refs` as labels: `Figure 3B`, `Figure S4`."""
    return [r.label for r in parse_figure_refs(text)]

#: Words that make a comment an IMAGE-INTEGRITY comment rather than any other
#: kind of post-publication remark. PubPeer carries plenty of ordinary
#: scientific discussion, and counting that as a positive label would make
#: our measured recall meaningless.
#:
#: The second group was added 2026-09-28 after reading every Masliah thread
#: the first group left out (48 of 122) plus every flip on the 122 cached
#: image_discovery_2026-09 threads: 9 Masliah and 24 discovery flips, all
#: read as image allegations except one discovery "re-use the material"
#: after a retraction. Measured and REJECTED on the same threads:
#: "background" (a staining complaint, and no gain over "vertical"), bare
#: "similar" ("a phenotype similar to"), "image"/"panel"/"copy" (a Seahorse
#: arrow erratum, a methods critique), and "same field" (no hits).
#: The larger gap is not words: most of those 48 Masliah threads are an
#: annotated image with a signature and no text, which no term can label.
_IMAGE_TERMS = (
    "duplicat", "overlap", "identical", "spliced", "splice", "manipulat",
    "cloned", "clone", "mirror", "rotated", "flipped", "reuse", "re-use",
    "same image", "same panel", "band", "blot", "unexpected similarit",
    "similar than", "remarkably similar", "unexpectedly similar",
    "high similarit", "mix-up", "mixed up", "vertical line", "vertical change",
    "vertical, straight", "vertical discontinu", "vertical irregular",
    "vertical flip",
)


def image_integrity_labels(comments: Iterable[dict]) -> dict:
    """Which figures these comments allege an IMAGE problem in.

    A coarse, paper-and-figure-level label, and stored as one on purpose: the
    goal is to learn whether we fired on the right PAPER and named the right
    FIGURE, not to claim pixel agreement with a human's marked-up JPEG.

    An allegation is somebody else's claim. This function records what was
    alleged and by that fact alone; it never converts it into a finding.
    """
    figures: set[str] = set()
    matched: list[int] = []
    n_images = 0
    for comment in comments:
        text = (comment.get("text") or "").lower()
        if not any(term in text for term in _IMAGE_TERMS):
            continue
        matched.append(comment.get("inner_id", -1))
        n_images += len(comment.get("images") or [])
        figures.update(figure_refs(comment.get("text") or ""))
    return {
        "is_image_integrity": bool(matched),
        "figures": sorted(figures),
        "n_comments_matched": len(matched),
        "comment_ids": matched,
        "n_comment_images": n_images,
    }


def figure_stem(label: str) -> Optional[FigureRef]:
    """`FigureRef(supplementary, number, panel_or_empty)` for a figure label.

    `Figure 1C` / `Fig. 1c` / `figure 1` / `Figure S4` all parse. Returns
    None when the string is not a figure reference at all. A label naming
    several figures yields its FIRST; labels are single figures by contract.
    """
    refs = parse_figure_refs(str(label))
    return refs[0] if refs else None


def figures_agree(alleged: Iterable[str], detected: Iterable[str]) -> bool:
    """Soft figure-level agreement: `Figure 1C` agrees with `Figure 1`.

    The harvest often drops the panel letter, so requiring an exact string
    match (`Figure 1C` vs `Figure 1`) understates agreement -- measured
    2026-08-19 on the segmented Masliah sweep, 5/21 exact vs many more
    same-number hits. A paper-level fire on Figure 4 when PubPeer named
    Figure 1 is still NOT agreement.

    Both sides must name a figure. Empty alleged is unscorable, not a hit:
    the caller has to exclude that paper from the figure-level denominator.

    `Figure S4` never agrees with `Figure 4`: a supplementary figure and the
    main-text figure of the same number are different pictures.
    """
    a = {s for s in (figure_stem(x) for x in alleged) if s}
    d = {s for s in (figure_stem(x) for x in detected) if s}
    if not a or not d:
        return False
    for supp, num, panel in a:
        for dsupp, dnum, dpanel in d:
            if num != dnum or supp != dsupp:
                continue
            if not panel or not dpanel or panel == dpanel:
                return True
    return False
