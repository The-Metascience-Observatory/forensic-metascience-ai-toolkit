# Rapid-review workbench

Local Next.js app for triaging pipeline output. The HTML bundle
(`metascience bundle`) stays the detailed, offline letter you send an
editor. This is the multi-paper surface: brief findings, the PDF (or XML
when there is no PDF), and human labels that feed the next calibration.

Internal. Nothing here publishes anything. A decision commits to the local
outbox and syncs to the shared database; it is not a write of `review.json`
beside the paper. Opening a review page records a view through the same
service, which is how the `Viewed?` column knows. Anyone counts there, named
or not — but `no` in that column means *nothing is on file*, never *nobody
has read this paper*: view tracking is younger than the corpora, and a
bundle or a PDF opened outside this app cannot report back.

Normal navigation reads a private SQLite cache through the workbench
service. `webapp/data/index.json` is a bootstrap/import snapshot, not the
live project list. See [storage](../docs/workbench_storage.md).

## Run

```bash
# from the repo root
# use the interpreter the metascience CLI runs under (machine-specific)
PY=$(metascience python)
$PY -m forensic_metascience_ai_toolkit.workbench.service --migrate
$PY -m forensic_metascience_ai_toolkit.workbench.service --sync --index webapp/data/index.json

cd webapp && npm install && npm run dev      # http://localhost:3100 (or the next free port if 3100 is taken)
```

`metascience webapp-index --projects-root <root> -o webapp/data/index.json`
rebuilds the compatibility index the service can import. It does not replace
daily sync.

For daily review, use the production build to avoid development compilation:

```bash
cd webapp
npm run build
npm start
```

Home and project counts come from the synchronized catalog. **Sync records**
pulls changed shared findings, reviews and runs; it does not re-run analysis.
Image feeds validate published evidence on each read and refresh discovery in
the background. Changed evidence is withheld during refresh, with a visible
explanation. PDFs render the target and nearby pages; text search indexes the
document separately. Repaired media is revalidated before reuse.

Or set the papers root in the UI and click **Set root and scan**.

`METASCIENCE_PAPERS_ROOT` overrides the root; `METASCIENCE_PYTHON` overrides
the interpreter the API shells out to.

Settings are saved outside the checkout: macOS uses
`~/Library/Application Support/metascience/webapp/settings.json`, Linux uses
`${XDG_CONFIG_HOME:-~/.config}/metascience/webapp/settings.json`, and Windows uses
`%LOCALAPPDATA%/metascience/webapp/settings.json`. The old `data/settings.json`
is migrated once; a papers root that does not exist locally is not imported.
Subsequent Dropbox updates cannot overwrite local settings. Set `python_bin`
in this local JSON file to select a machine-specific Python interpreter, or use
the environment override. UI saves preserve that interpreter setting.
Do not put machine-specific settings in a Dropbox-synchronized `.env.local`:
Git ignoring a file does not stop Dropbox syncing it.
The default papers folder is `agent_for_forensic_metascience_papers`
beside the repository. The Python bridge includes all three checkout source
folders; the selected interpreter still needs the workbench dependencies
(including Pillow and the `db` extra). Scanning cannot fix a Python startup error.

Set your name in the header before recording a decision. The stamp is
`reviewed by {name} on {date}`. Completing a paper is a separate button:
labelling one finding does not count it as reviewed.

Title, first author, journal, volume, issue and year come from
`metadata.json` beside the paper (DOI cascade: DataCite → Crossref →
Unpaywall → PubMed → …). Fill missing titles with
`metascience fetch-metadata --project-dir <project>`. Missing volume/issue is
left alone.

```bash
metascience fetch-metadata --project-dir /path/to/papers
```

## Image findings

Each image-duplication card prints the recorded PDF pages next to the
figure labels (`Figure 2 on p. 5 and p. 17`). **Open p. N** jumps the
PDF pane to that page. Pages come from harvest placements; a missing
page is omitted, never invented as page 1.

### Pane sizes

The image item page has two dividers: one between the notes column and the
evidence column, one between the panel comparison and the PDF. Drag either,
or focus it and use the arrow keys. Both sizes are kept in `sessionStorage`
(`metascience.images.split.left` / `.top`), so a posture chosen on one
finding holds for the rest of the tab. j/k and queue links now use client
navigation, retaining the feed and the reviewer’s position. It is session
state, not a standing preference: the next window starts at 30% / 46%.

Releasing a divider re-fits the comparison canvas and re-renders the PDF at
the new width. That is deliberately gesture-driven rather than a
`ResizeObserver` -- see the note on `PdfPane.refitNonce` for the flash loop
an observer closes here.

## Keyboard

Paper review pane:

| Key | Action |
|---|---|
| ← / → | previous / next paper |
| ↑ / ↓ | previous / next finding |

Image queue: ↑ / ↓ moves the loaded-row cursor; Enter opens the item.
Image item: `j` / `k` next/prev, `n` next undecided, `1`–`9` decide
(true issue / unsure / FP same condition / FP other / false positive /
chart / overlay / supplement / magnification). A successful decision
advances to the next undecided item. Esc returns to the queue.
Copy/paste: `j` / `k` next/prev in the loaded page; a decision also
advances to the next undecided item.

## Channels

Every check is a tri-state, never a boolean. See `webapp_index.py`.
Absence of a result is not a clean paper.

## XML-only papers

When a directory has publisher XML and no PDF, the right pane renders the
XML and shows: **PDF not available, using XML. Try downloading the PDF here:**
plus `https://doi.org/{doi}`. Clicking a finding card jumps to the highlighted
span. **Highlight 1** / **Highlight 2** appear only when one finding has two
distinct places to compare. XML has no pages, so a weak locate is still a
section scroll rather than a box.


## Checks

`npm test` is offline: `smoke.mjs` (helpers, byte ranges, filter restore,
infinite-queue paging, serve ports), `reviewSync.mjs`, and `python.mjs`.
`npm run build` includes the TypeScript check. Live scripts need a running
app and a named corpus; they are not part of `npm test`:

- `test:browser`, `test:history`, `test:infinite-scroll`, `test:performance`,
  `test:review-sync-browser`
- `node --experimental-strip-types test/workbench.mjs` and
  `test/workbench-browser.mjs` (documented in the storage guide)

For browser verification, install Chromium once with
`npx playwright install chromium`, start the app, then run:

```bash
METASCIENCE_TEST_URL=http://localhost:3100 \
METASCIENCE_TEST_PROJECT=image_discovery_2026-09 npm run test:browser
```

The selected corpus must contain at least two published image items with PDFs.
The browser test mocks decision POSTs: it never records test verdicts on papers.
It checks navigation without document reloads, PDF display, repeated decision
hotkeys, suffix ranges, conditional requests and browser errors. Override
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to use an existing Chromium installation.
`METASCIENCE_NEXT_DIST=.next-audit` isolates validation builds from a running
development server.

### Versioned run history

The image and copy/paste review pages have a **Version / run** selector, with
latest per paper as the default. Saved candidates, screening and human decisions
retain their original run identity. [Storage, migration and commands](../docs/analysis_history.md).

With the app running and Masliah history imported, `npm run test:history` checks
selection races, historical media and PDF rendering, range requests, CSV and
summary exports, and run-scoped review writes (the writes are mocked). Set
`METASCIENCE_TEST_URL` or `METASCIENCE_TEST_PROJECT` to use another instance or
an imported project with two recoverable image runs.
