"""Public metadata discovery, version-checked local imports and frozen sampling.

No authenticated downloads: users supply files through their normal browser.
Metadata snapshots are retained so later corrections cannot relabel older data.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

from .paper import FORMATS
from .storage import atomic_json, digest, file_hash, now

ABOUT = "https://www.sciencedetective.org/about/"
DRYAD = "https://datadryad.org"
SEEDS = {
    "10.1016/j.cell.2016.11.018": "10.5061/dryad.4mp6h",
    "10.1038/ncomms15361": "10.5061/dryad.td3sj",
    "10.1371/journal.pgen.1010323": "10.5061/dryad.sqv9s4n68",
}


def doi(value):
    match = re.search(r"10\.\d{4,9}/[^\s?#<>]+", urllib.parse.unquote(value), re.I)
    return match.group(0).rstrip(".,;)").lower() if match else None


class IssueList(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items, self.current = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.current = {"text": [], "links": []}
        if tag == "a" and self.current is not None:
            self.current["links"].append(dict(attrs).get("href", ""))

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "li" and self.current is not None:
            if any("pubpeer.com/publications/" in link for link in self.current["links"]):
                self.items.append(self.current)
            self.current = None


class Metadata:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, url, *, text=False):
        if url.startswith("/"):
            url = DRYAD + url
        cache = self.directory / (digest(url) + ".json")
        if cache.exists():
            return json.loads(cache.read_text())["body"]
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "copy-paste-detector/0.2 metadata research"}
                )
                with urllib.request.urlopen(req, timeout=20) as response:
                    raw = response.read().decode("utf-8")
                body = raw if text else json.loads(raw)
                atomic_json(cache, {"url": url, "retrieved_at": now(), "body": body})
                return body
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(float(exc.headers.get("Retry-After", 30 * (attempt + 1))))

    def pages(self, url, embedded):
        seen = set()
        while url and url not in seen:
            seen.add(url)
            page = self.get(url)
            yield from page.get("_embedded", {}).get(embedded, [])
            url = page.get("_links", {}).get("next", {}).get("href")

    def versions(self, dataset_doi):
        identifier = urllib.parse.quote("doi:" + dataset_doi, safe="")
        versions = list(self.pages(f"/api/v2/datasets/{identifier}/versions", "stash:versions"))
        out = []
        for version in versions:
            files = list(self.pages(version["_links"]["stash:files"]["href"], "stash:files"))
            out.append(
                {
                    "version_id": version["_links"]["self"]["href"].rsplit("/", 1)[-1],
                    "version_number": version.get("versionNumber"),
                    "publication_date": version.get("publicationDate"),
                    "status": version.get("curationStatus"),
                    "license": version.get("license", "not_recorded_in_metadata"),
                    "files": [
                        {
                            "filename": f["path"],
                            "file_id": f["_links"]["self"]["href"].rsplit("/", 1)[-1],
                            "size": f.get("size"),
                            "digest": f.get("digest"),
                            "digest_type": f.get("digestType"),
                            "download_url": (DRYAD + f["_links"]["stash:download"]["href"])
                            if f["_links"].get("stash:download")
                            else None,
                            "supported": Path(f["path"]).suffix.lower() in FORMATS,
                        }
                        for f in files
                    ],
                }
            )
        return out


def discover(output):
    out = Path(output)
    client = Metadata(out / "metadata")
    parser = IssueList()
    parser.feed(client.get(ABOUT, text=True))
    if not parser.items:
        raise ValueError("No Science Detective issue entries parsed; discovery instrument failed")
    cases = []
    for priority, item in enumerate(parser.items, 1):
        article = next(
            (link for link in item["links"] if "pubpeer.com" not in link and doi(link)), None
        )
        # Nature article URLs sometimes omit the DOI prefix.
        if article is None:
            article = next((link for link in item["links"] if "/articles/" in link), "")
            paper_doi = (
                "10.1038/" + article.split("/articles/")[-1].split("?")[0] if article else None
            )
        else:
            paper_doi = doi(article)
        case = {
            "case_id": "sd-" + digest(paper_doi or item)[0:12],
            "priority": priority,
            "family_id": paper_doi,
            "paper_doi": paper_doi,
            "title": " ".join("".join(item["text"]).split()).split("Pubpeer")[0].rstrip(" |-"),
            "issue_url": next(link for link in item["links"] if "pubpeer.com" in link),
            "article_url": article,
            "verification_status": "unresolved_concern",
            "issues": [],
            "datasets": [],
            "acquisition_status": "unresolved",
        }
        try:
            dataset_dois = [SEEDS[paper_doi]] if paper_doi in SEEDS else []
            if paper_doi and not dataset_dois:
                found = client.get(
                    "/api/v2/search?" + urllib.parse.urlencode({"q": paper_doi, "per_page": 100})
                )
                for dataset in found.get("_embedded", {}).get("stash:datasets", []):
                    if any(
                        doi(w.get("identifier", "")) == paper_doi
                        for w in dataset.get("relatedWorks", [])
                    ):
                        dataset_dois.append(
                            doi(dataset.get("identifier", "") or dataset["_links"]["self"]["href"])
                        )
            for dataset_doi in sorted(set(dataset_dois)):
                case["datasets"].append(
                    {
                        "doi": dataset_doi,
                        "url": DRYAD + "/dataset/doi:" + dataset_doi,
                        "versions": client.versions(dataset_doi),
                    }
                )
            if case["datasets"]:
                case["acquisition_status"] = "awaiting_local_files"
        except (OSError, ValueError, KeyError) as exc:
            case["acquisition_error"] = f"{type(exc).__name__}: {exc}"
        cases.append(case)
        atomic_json(out / "catalog.json", {"source": ABOUT, "retrieved_at": now(), "cases": cases})
    render_downloads(out / "DOWNLOADS.md", cases)
    return {"cases": len(cases), "datasets_resolved": sum(bool(c["datasets"]) for c in cases)}


def render_downloads(path, cases):
    lines = [
        "# Copy-paste benchmark downloads",
        "",
        "Keep original filenames. Versions are separate benchmark inputs; never combine original and corrected data in one detection job.",
        "",
        "Labels remain unverified until the actual cells and source explanations have been inspected.",
        "",
    ]
    for case in cases:
        lines += [
            f"## {case['priority']}. {case['title']}",
            "",
            f"Paper: {case['paper_doi']} · [Reported issue]({case['issue_url']})",
            "",
        ]
        if not case["datasets"]:
            lines += [
                "Dataset unresolved; source resolution is still required. "
                + case.get("acquisition_error", ""),
                "",
            ]
        for dataset in case["datasets"]:
            lines += [f"[Dryad dataset]({dataset['url']})", ""]
            for v in dataset["versions"]:
                lines += [
                    f"Version {v['version_number']} (ID {v['version_id']}), {v['publication_date']}; repository status: {v['status']}",
                    "",
                ]
                lines += [
                    f"- `{f['filename']}` — file ID {f['file_id']}; {f['size']} bytes; {f['digest_type']}: `{f['digest']}`"
                    for f in v["files"]
                    if f["supported"]
                ]
                if not any(f["supported"] for f in v["files"]):
                    lines += ["No supported structured files listed for this version."]
                lines += [""]
    Path(path).write_text("\n".join(lines))


def import_local(catalog, incoming, output):
    """Hash-match local files; filename alone is never version evidence."""
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    candidates = defaultdict(list)
    for path in Path(incoming).rglob("*"):
        if path.is_file() and path.suffix.lower() in FORMATS:
            candidates[path.name].append(path)
    receipts, manifests = [], []
    for case in json.loads(Path(catalog).read_text())["cases"]:
        for dataset in case["datasets"]:
            for version in dataset["versions"]:
                paper_id = f"{case['case_id']}-v{version['version_id']}"
                files = []
                basenames = [Path(f["filename"]).name for f in version["files"] if f["supported"]]
                if len(basenames) != len(set(basenames)):
                    raise ValueError(f"Ambiguous duplicate basenames in dataset version {paper_id}")
                for f in version["files"]:
                    if not f["supported"]:
                        continue
                    record = {"paper_id": paper_id, **f, "status": "missing"}
                    matches = []
                    if f.get("digest") and f.get("digest_type"):
                        matches = [
                            p
                            for p in candidates[Path(f["filename"]).name]
                            if file_hash(p, f["digest_type"]) == f["digest"]
                        ]
                    existing = out / "inputs" / paper_id / Path(f["filename"]).name
                    if existing.exists():
                        if (
                            not f.get("digest")
                            or file_hash(existing, f["digest_type"]) != f["digest"]
                        ):
                            raise ValueError(f"Existing import does not match catalog: {existing}")
                        matches.append(existing)
                    if matches:
                        src = matches[0]
                        target = out / "inputs" / paper_id / Path(f["filename"]).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if target.exists() and file_hash(target) != file_hash(src):
                            raise ValueError(
                                f"Refusing to replace different imported bytes: {target}"
                            )
                        if not target.exists():
                            shutil.copyfile(src, target)
                        record.update(
                            status="verified", sha256=file_hash(target), local_path=str(target)
                        )
                    elif candidates[Path(f["filename"]).name]:
                        record["status"] = (
                            "checksum_mismatch" if f.get("digest") else "checksum_unavailable"
                        )
                    receipts.append(record)
                    # Missing requested files stay in the manifest: partial coverage
                    # must not become a complete review of only the files obtained.
                    target = out / "inputs" / paper_id / Path(f["filename"]).name
                    files.append(
                        {
                            "path": str(target),
                            "name": f["filename"],
                            "expected_digest": f.get("digest"),
                            "digest_type": f.get("digest_type"),
                        }
                    )
                if files:
                    manifests.append(
                        {
                            "paper_id": paper_id,
                            "family_id": case["family_id"],
                            "doi": case["paper_doi"],
                            "dataset_doi": dataset["doi"],
                            "version_id": version["version_id"],
                            "files": files,
                            "context_files": [],
                            "data_context": "unknown",
                        }
                    )
    atomic_json(
        out / "import_receipt.json",
        {"imported_at": now(), "catalog_sha256": file_hash(catalog), "files": receipts},
    )
    (out / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in manifests))
    return {
        "papers": len(manifests),
        "verified_files": sum(r["status"] == "verified" for r in receipts),
        "files_requested": len(receipts),
    }


def sample_frame(frame, output, n=100, seed=20260910, exclude_families=()):
    """Stratified selection from an explicit eligible frame, not all of Dryad."""
    values = json.loads(Path(frame).read_text())
    rows = values["papers"]
    strata, seen = defaultdict(list), set()
    for row in sorted(rows, key=lambda r: r["paper_id"]):
        family = row.get("family_id") or row.get("doi") or row["paper_id"]
        if family in seen or family in exclude_families or not row.get("files"):
            continue
        formats = tuple(
            sorted(
                {Path(f.get("filename", f.get("path", ""))).suffix.lower() for f in row["files"]}
                & FORMATS
            )
        )
        if not formats:
            continue
        seen.add(family)
        strata[(row.get("domain") or "unclassified", formats)].append(row)
    if len(seen) < n:
        raise ValueError(
            f"Only {len(seen)} eligible independent papers in supplied frame; {n} requested"
        )
    rng = random.Random(seed)
    for group in strata.values():
        rng.shuffle(group)
    selected = []
    # Round-robin strata deliberately balances coverage, not prevalence.
    while len(selected) < n:
        for key in sorted(strata):
            if strata[key] and len(selected) < n:
                selected.append({**strata[key].pop(), "verification_status": "unlabelled"})
    result = {
        "seed": seed,
        "frame_sha256": file_hash(frame),
        "frame_description": values.get("description"),
        "eligible_families": len(seen),
        "requested": n,
        "papers": selected,
        "sampling": "Equal-stratum round robin after seeded shuffling; not a population prevalence sample",
    }
    atomic_json(output, result)
    return {"selected": len(selected), "eligible_families": len(seen)}


def split_families(cases, seed=20260910):
    families = sorted({c["family_id"] for c in cases})
    random.Random(seed).shuffle(families)
    count = max(1, round(len(families) * 0.3)) if len(families) > 1 else 0
    held = set(families[:count])
    return {f: "held_out" if f in held else "development" for f in families}


def build_frame(output, pages=5, retry_failed=False, cached_only=False):
    """Freeze a bounded, explicitly ordered public Dryad metadata frame."""
    out = Path(output)
    client = Metadata(out / "metadata")
    previous_path = out / "frame.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    failed = {
        r["version_id"]: r
        for r in previous.get("inventory", [])
        if r["status"] == "metadata_failed"
    }
    listings = []
    for page in range(1, pages + 1):
        response = client.get(f"/api/v2/datasets?per_page=100&page={page}")
        listings.extend(response.get("_embedded", {}).get("stash:datasets", []))

    def inspect(dataset):
        paper_doi = next(
            (
                doi(w.get("identifier", ""))
                for w in dataset.get("relatedWorks", [])
                if w.get("relationship") == "primary_article" and doi(w.get("identifier", ""))
            ),
            None,
        )
        item = {
            "paper_id": doi(dataset["identifier"]),
            "family_id": paper_doi or doi(dataset["identifier"]),
            "doi": paper_doi,
            "title": dataset["title"],
            "dataset_doi": doi(dataset["identifier"]),
            "version_id": dataset["_links"]["stash:version"]["href"].rsplit("/", 1)[-1],
            "license": dataset.get("license"),
            "keywords": dataset.get("keywords", []),
            "domain": "unclassified",
            "files": [],
        }
        try:
            url = dataset["_links"]["stash:version"]["href"] + "/files"
            cached = (client.directory / (digest(DRYAD + url) + ".json")).exists()
            if cached_only and not cached:
                return {
                    **item,
                    "status": "metadata_failed",
                    "error": "File inventory not acquired at frame freeze",
                }
            if not retry_failed and item["version_id"] in failed and not cached:
                return {
                    **item,
                    "status": "metadata_failed",
                    "error": failed[item["version_id"]]["error"],
                    "retry_deferred": True,
                }
            if not cached:
                time.sleep(1.1)
            files = list(client.pages(url, "stash:files"))
            item["files"] = [
                {
                    "filename": f["path"],
                    "size": f.get("size"),
                    "digest": f.get("digest"),
                    "digest_type": f.get("digestType"),
                    "file_id": f["_links"]["self"]["href"].rsplit("/", 1)[-1],
                    "download_url": (DRYAD + f["_links"]["stash:download"]["href"])
                    if f["_links"].get("stash:download")
                    else None,
                }
                for f in files
                if Path(f["path"]).suffix.lower() in FORMATS
            ]
            item["status"] = (
                "eligible" if item["files"] and paper_doi else "no_structured_files_or_article_doi"
            )
        except (OSError, ValueError, KeyError) as exc:
            item.update(status="metadata_failed", error=str(exc))
        return item

    with ThreadPoolExecutor(max_workers=1) as pool:
        inspected = list(pool.map(inspect, listings))
    frame = {
        "description": f"First {pages} public Dryad /datasets pages, 100 records per page, repository default order, frozen {now()}. Convenience frame, not a random sample of all Dryad.",
        "cached_only": cached_only,
        "domain_policy": "Unclassified unless externally annotated; sampling stratifies recorded formats and any supplied domain.",
        "papers": [r for r in inspected if r["status"] == "eligible"],
        "inventory": inspected,
    }
    atomic_json(out / "frame.json", frame)
    return {"inspected": len(inspected), "eligible": len(frame["papers"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--output", type=Path, required=True)
    f = sub.add_parser("frame")
    f.add_argument("--output", type=Path, required=True)
    f.add_argument("--pages", type=int, default=5)
    f.add_argument("--retry-failed", action="store_true")
    f.add_argument("--cached-only", action="store_true")
    i = sub.add_parser("import")
    i.add_argument("--catalog", type=Path, required=True)
    i.add_argument("--incoming", type=Path, required=True)
    i.add_argument("--output", type=Path, required=True)
    s = sub.add_parser("sample")
    s.add_argument("--frame", type=Path, required=True)
    s.add_argument("--output", type=Path, required=True)
    s.add_argument("--count", type=int, default=100)
    s.add_argument("--seed", type=int, default=20260910)
    s.add_argument("--exclude-catalog", type=Path)
    args = parser.parse_args(argv)
    if args.command == "discover":
        result = discover(args.output)
    elif args.command == "frame":
        result = build_frame(args.output, args.pages, args.retry_failed, args.cached_only)
    elif args.command == "import":
        result = import_local(args.catalog, args.incoming, args.output)
    else:
        excluded = (
            [c["family_id"] for c in json.loads(args.exclude_catalog.read_text())["cases"]]
            if args.exclude_catalog
            else []
        )
        result = sample_frame(args.frame, args.output, args.count, args.seed, excluded)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
