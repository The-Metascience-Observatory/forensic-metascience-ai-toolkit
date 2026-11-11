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

Needs Node.js 20.9 or newer (Next 16). This machine's `/usr/bin/node` is 18,
which Next 16 refuses by name: use the nvm one (`nvm use 22`) or put it first
on `PATH`.

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

## RNG findings (and other detector tracks)

A separately distributed detector files its run beside the paper's review as a
component run (`forensic_review_rng/`, producer and run kind `rng_track`), and
the webapp reviews it with the same page and the same storage as any finding:

- **Queue:** `/project/<project>/detector/rng_track` (`/project/<project>/rng`
  redirects there) lists every kept row of that producer, strongest first
  (tier, then excess bits), with its paper, title and review state; filter
  `undecided` / `decided`. Clicking a row opens the paper review page on the
  page that holds that finding (`?finding=<id>`). The route is keyed by the
  stored producer value so a spectra or copy-paste track plugs in by name.
- **Paper page:** an `rng_track` row shows the detector's own evidence under
  its description: generator, seed, stream position, tier, excess bits,
  observed vs generated values (table values are checked against their
  printed precision; figure coordinates report max |Δ|, the fit residual being
  the criterion), the matched blocks, the table grid with matched cells shaded
  (Europe PMC hits), and the replay snippet with a copy button. The PDF pane
  highlights the detector's `page_bbox` anchors; an XML-only paper highlights
  the `table_cell` anchors in the rendered article.
- **Decisions:** the vocabulary is the producer's own
  (`review_io.DECISIONS_BY_PRODUCER`, generated into `lib/constants.gen.ts`):
  true issue, disclosed / legitimate simulation, legitimate random algorithm,
  parse artefact, unsure. Saved like every other decision (run-scoped, outbox,
  shared database).
- **Getting runs in:** from the detector checkout,
  `rngdetect export-workbench RUN_DIR PROJECT --push` (per-paper PDF/figure
  screens) or `rngdetect export-workbench --europepmc RUN_DIR PROJECT_ROOT
  --pmcids FILE [--verdicts CSV] --push` (Europe PMC table hits, one XML-only
  paper folder per article), with the toolkit's `src` on `PYTHONPATH`; then
  **Sync records** here. Register the project folder under **Local files** so
  the PDF or XML can be shown.

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

Offline, no server, no database (`npm test` runs Vitest):

- `npm test` — unit tests (`test/*.test.mjs`: helpers, byte ranges, filter
  restore, infinite-queue paging, serve ports, review sync, decision
  vocabularies, RNG evidence) and component tests under jsdom with Testing
  Library (`test/components/*.test.tsx`: projects table, text support, video
  generation, cache status). `test/python.test.mjs` exercises the Python
  bridge and skips itself where the toolkit interpreter is absent.
- `npm run lint` — ESLint (`eslint.config.mjs`: Next's rules, plus `lib/`
  may not import `app/`). The React Compiler hook rules and `no-explicit-any`
  are warnings until the component splits burn them down; errors must stay
  at zero. `npm run format` / `format:check` run Prettier.
- `npm run typecheck` — `tsc --noEmit`. `npm run build` includes it too.
- `npm run test:components` — the Playwright component scripts that need a
  real browser: canvas drawing, image decoding, pdf.js and GIF encoding
  (`cloneComparatorBrowser`, `clonePdfBrowser`, `gifGenerationBrowser`,
  `imageHoverBrowser`, `imageQueueSummaryBrowser`, `textRegionAuditBrowser`,
  `xmlPaperBrowser`). Install Chromium once with `npx playwright install
  chromium`. A script without its opt-in fixture prints `SKIPPED` and the
  runner (`test/run-scripts.mjs`) counts it as skipped, never as a pass.
- `npm run test:security` — `auditSecurity.mjs`: cross-origin refusal on every
  mutation route, sandboxed HTML evidence, ranges and cache headers.

Live scripts need a running app and a named corpus; they are not part of the
offline set: `npm run test:live` (or singly `test:browser`, `test:history`,
`test:infinite-scroll`, `test:performance`), plus `node test/workbench.mjs`
and `test/workbench-browser.mjs` (documented in the storage guide). GitHub
Actions runs lint, typecheck, the offline tests and the build on every
webapp change (`.github/workflows/webapp.yml`).

For browser verification, start the app, then run:

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

### Layout

`lib/` is the layer `app/` builds on and never imports `app/` (enforced by
lint). Record types shared by both live in `lib/types/` (`images.ts`,
`runs.ts`, `catalog.ts`); `app/images/lib.ts` re-exports the image ones.
Server-only modules (`lib/python.ts`, `workbench.ts`, `reveal.ts`,
`settings.ts`, `store.ts`, `paths.ts`) carry `import "server-only"`, so a
client component that imports one fails the build instead of shipping Node
code. `METASCIENCE_TOOLKIT_ROOT` names the toolkit checkout the Python bridge
runs against; by default it is the parent of this folder.

### Versioned run history

The image and copy/paste review pages have a **Version / run** selector, with
latest per paper as the default. Saved candidates, screening and human decisions
retain their original run identity. [Storage, migration and commands](../docs/analysis_history.md).

With the app running and Masliah history imported, `npm run test:history` checks
selection races, historical media and PDF rendering, range requests, CSV and
summary exports, and run-scoped review writes (the writes are mocked). Set
`METASCIENCE_TEST_URL` or `METASCIENCE_TEST_PROJECT` to use another instance or
an imported project with two recoverable image runs.

## Hosting

One codebase, one build, two modes. With no hosted variables set the app is
the local workbench described above: loopback bind, a free-text reviewer name
in the header, every route available, no sign-in. Set
`METASCIENCE_ACCESS_TEAM` and `METASCIENCE_ACCESS_AUD` and it runs in
**hosted mode**: Cloudflare Access decides who gets in, `proxy.ts` verifies
the Access token Cloudflare attaches to every request (`jose`, RS256 against
`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`, audience and
issuer checked) and forwards the verified email to the handlers in
`x-ms-reviewer-email` (a client-supplied copy is stripped in both modes).
Without a valid token every `/api/*` request is `401 {error}` and every page
is a minimal "Sign in through Cloudflare Access" page, so a misconfigured
Access application fails closed. The server still binds 127.0.0.1; only the
tunnel reaches it.

**Users and roles.** The **user directory** is a `reviewers` array in the
settings file (`lib/settings.ts` names its location per platform), edited on
the admin **Users** page (`/admin/users`):

```json
"reviewers": [
  { "email": "you@example.org", "name": "Your Name", "role": "admin" },
  { "email": "colleague@example.org", "name": "A. Colleague", "role": "reviewer",
    "projects": ["rng_detector_cases"] }
]
```

- **admin**: every project, the admin pages, and every admin-only route.
- **reviewer**: only the listed `projects`: see papers and findings, record
  decisions, mark papers complete, record PubPeer posts. No deleting,
  rescanning, paid drafts or website publishing.
- **anyone else** Cloudflare Access admits is refused with "your account is
  not set up yet" (deny by default). Two gates, by design: Access decides who
  may reach the app, the directory decides what they may do there.

`GET /api/me` returns `{mode, email, name, role, projects}`; the header chip
shows "Reviewing as <name>". Every write records the signed-in user's
display `name` and ignores any `reviewer` in the body. That name is what the
Python service stores as `reviewer` (Postgres `users.legacy_name`), so
renaming someone who has already reviewed splits their history; the Users
page warns. A settings file without the array starts from
`METASCIENCE_ADMIN_EMAIL` (and `METASCIENCE_ADMIN_NAME`) as the one admin,
else from nobody: no address is written into this public source.

**Adding a reviewer:** add them on Users (email, display name, role, tick
their projects), then admit the same email in Cloudflare Access (Zero Trust →
Access → Applications → this app → its policy → Include). Either step alone
does not let them in.

**Enforcement** happens in three places, sharing one rule set:

- `proxy.ts` refuses unknown users, any `/project/<p>` page or `?project=<p>`
  request for a project the reviewer is not assigned, and the admin pages
  (`/admin/*`, `/files`).
- Every API route calls `await guard(req, {project})` (`lib/routeGuard.ts`)
  with the project it is about to touch, including projects read from a POST
  body. A test fails if a route handler does not call it.
- Server-rendered pages check through `app/project/[project]/layout.tsx` and
  the home page filters its list (`lib/pageAccess.ts`).

Admin-only routes (`lib/routeGuard.ts`, one table): `/api/projects`
(deletion and its job list), `/api/settings` POST, `/api/workbench` POST with
`register_root`, `map_paper`, `register_file` or `sync`, workbench reads
`projects` and `roots`, `/api/index` POST, `/api/metadata` POST,
`/api/images/reference` POST, `/api/images/sync` POST, `/api/stats` POST,
`/api/draft` POST (a paid model call), `/api/images/website` POST, and
`/api/admin/*`. Refused for everyone in hosted mode: `/api/reveal` (it opens
a file manager on the server). A reviewer's sync status has its error details
removed, `image_status` loses its all-projects list, and a bulk-decision job
can be polled only by whoever started it.

**Projects.** A project is a name: the catalog's corpus name, which keys
records, reviews and image tables. The admin **Projects** page
(`/admin/projects`) decides which names exist for the app
(`project_sources` in the settings file, `lib/projectSources.ts`):

- a **watched folder** makes each subfolder a project named after it, and a
  new subfolder appears by itself. Scaffolding folders (`_x`, `.x`, `done`,
  `logs`, ...: `SCAFFOLDING_DIRS`, generated from `discovery._NOT_A_PAPER`)
  are skipped. A catalog project registered at a folder deeper inside (the
  `<author>__pubpeer_checked_*` session corpora) counts too, and a folder that
  only holds such projects is not one itself;
- a **single folder** can be added as a project under a name;
- a name with findings in the **database** but no folder here can be adopted.

Every other catalog name (test corpora such as `pytest-600`, scratch copies,
folders that moved) is listed under "Not in any source" for the admin and is
404 for everyone, admins included. Nothing is deleted. Without
`project_sources` every catalog name is listed, as before. Stats, drafts and
metadata find a project's folders through the catalog's registered roots,
not through `papers_root/<name>`.

**Origin.** Behind the tunnel the browser sends `Origin: https://<public
host>` while Node sees `http://<host>`, so `METASCIENCE_PUBLIC_ORIGIN` names
the public origin and counts as same-origin, and `x-forwarded-proto` is
honoured for that host only. Local-mode rules (loopback aliases, no trust in
`Host`) are unchanged.

### Operator steps

The example hostname is `review.metascienceobservatory.org`; substitute your
own. This machine already runs a tunnel (`~/.cloudflared/config.yml`), so the
app is one more ingress rule on it.

1. Add the ingress rule before the catch-all in `~/.cloudflared/config.yml`:

   ```yaml
   ingress:
     - hostname: review.metascienceobservatory.org
       service: http://127.0.0.1:3101
     # ... existing rules ...
     - service: http_status:404
   ```

   and route the name to the tunnel:

   ```bash
   cloudflared tunnel route dns <tunnel-name> review.metascienceobservatory.org
   ```

2. Run cloudflared as a user service so it survives logouts and reboots:

   ```bash
   mkdir -p ~/.config/systemd/user
   cat > ~/.config/systemd/user/cloudflared.service <<'UNIT'
   [Unit]
   Description=Cloudflare Tunnel
   After=network-online.target

   [Service]
   ExecStart=/usr/bin/cloudflared tunnel run
   Restart=on-failure

   [Install]
   WantedBy=default.target
   UNIT
   systemctl --user enable --now cloudflared
   loginctl enable-linger "$USER"
   ```

3. In Cloudflare Zero Trust (`https://one.dash.cloudflare.com`): **Access →
   Applications → Add an application → Self-hosted**, application domain
   `review.metascienceobservatory.org`. Add an **Allow** policy whose
   include rule lists the invited emails (or an email list), with
   **One-time PIN** and/or **Google** as login methods. Save, open the
   application's **Overview** and copy its **Application Audience (AUD)
   Tag**. The team name is the `<team>` in `<team>.cloudflareaccess.com`
   (Settings → Custom Pages → Team domain).

4. Build once, then start in hosted mode with the three variables set.
   `start:hosted` refuses to start if any is missing, because a hosted
   deployment that fell back to local mode would be an open server behind
   the tunnel; `start` prints the mode it detected either way.

   ```bash
   cd webapp && npm run build
   METASCIENCE_ACCESS_TEAM=<team> \
   METASCIENCE_ACCESS_AUD=<aud-tag> \
   METASCIENCE_PUBLIC_ORIGIN=https://review.metascienceobservatory.org \
   METASCIENCE_ADMIN_EMAIL=you@example.org METASCIENCE_ADMIN_NAME="Your Name" \
   npm run start:hosted
   ```

   Keep the variables out of the Dropbox checkout (a systemd user unit's
   `Environment=` lines, or a file under `~/.config` read with
   `EnvironmentFile=`), the same way the settings file stays local.

5. Add each invited reviewer to the Access policy **and** to the
   `reviewers` directory in the settings file with the display name their
   decisions should carry. Check `https://review.metascienceobservatory.org/api/me`
   after signing in: it should name you and your role.

Checks: `test/auth.test.mjs` mints tokens against a stubbed JWKS (valid,
missing, expired, wrong audience, wrong issuer, unknown key, header
stripping), `test/routeGuard.test.mjs` runs the route × role × mode matrix,
and `npm run test:security` exercises the hosted rules through the real route
handlers (no token → 401, body `reviewer` ignored, `/api/reveal` → 403,
admin routes → 403 for a reviewer, the public origin accepted with
`x-forwarded-proto: https`).

**Guard rails.** `npm run start` (local mode: every caller is the admin) refuses to
listen on a port that a `~/.cloudflared/*.yml` on this machine forwards to; use
`npm run start:hosted`, another `PORT`, or `METASCIENCE_LOCAL_MODE=1` when the tunnel is
down. Setting only one of the two Access variables is an error. A new API route is
admin-only until it is added to `REVIEWER_ROUTES` in `lib/routeGuard.ts`. Responses carry
a Content-Security-Policy that limits pages to this origin; if a page needs an outside
resource, add it in `next.config.mjs`.
