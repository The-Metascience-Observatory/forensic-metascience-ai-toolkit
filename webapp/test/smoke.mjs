#!/usr/bin/env node
import './reveal.mjs';
import './matchRegion.mjs';
import "./imagePreview.mjs";
import './imagePdfBoxes.mjs';
import './emails.mjs';
import './summaryFigure.mjs';
import './imageXmlBoxes.mjs';
import './xmlFigures.mjs';
import './imageLocator.mjs';
import './requestCache.mjs';
import './infiniteFeed.mjs';
import './servePort.mjs';
import { restoreFilter, DEFAULT_FILTER, DECISIONS,
  cycleQueueSort, paperColumn, nextUndecidedIn, judgmentDecision, verdictLabel } from '../app/images/lib.ts';
assert.deepEqual(restoreFilter({...DEFAULT_FILTER,adjudicator:'Saved AI judgment: issue · low',offset:100}),DEFAULT_FILTER);
assert.deepEqual(restoreFilter({judgments:[],undecided:true}),{...DEFAULT_FILTER,judgments:[],undecided:true});
assert.deepEqual(restoreFilter(null),DEFAULT_FILTER);
// The image-type choice survives a reload; an unknown or missing value is the absence of a filter.
assert.equal(restoreFilter({...DEFAULT_FILTER,image_type:'Blots'}).image_type,'Blots');
// So does the Figures choice; an unrecognised value is no filter at all.
assert.equal(restoreFilter({...DEFAULT_FILTER,figure_span:'different_figures'}).figure_span,'different_figures');
assert.equal(restoreFilter({...DEFAULT_FILTER,figure_span:'spread'}).figure_span,'all');
// Filtering itself is tested against the service (tests/test_workbench_figure_span.py,
// test_workbench_paper_folder_filter.py, test_workbench_match_region_filter.py).
assert.equal(restoreFilter({...DEFAULT_FILTER,image_type:''}).image_type,'all');
assert.equal(restoreFilter({...DEFAULT_FILTER,q:'10.1007--s004010050748'}).q,'10.1007--s004010050748');
assert.equal(restoreFilter({verdict:'all',kind:'all'}).q,'');
const folderItem={id:'a',kind:'within',detector_kind:'exact',paper:{dir:'10.1007--s004010050748'},
  papers:[{dir:'10.1007--s004010050748'}],panels:[],cleared:false,screening:{decision:'issue'},
  publication_status:'published',rank:{score:1,reasons:[]}};
const detectionOnly={...folderItem,paper:{dir:'10.1002--dvdy.646'},screening:null,adjudication:null};
assert.equal(judgmentDecision(detectionOnly),'missing');
assert.equal(verdictLabel(detectionOnly),'No saved AI judgment');
const legacyJudgment={...detectionOnly,screening:{decision:null},adjudication:{verdict:'explained',category:'source_alias'}};
assert.equal(judgmentDecision(legacyJudgment),'legacy');
assert.equal(verdictLabel(legacyJudgment),'explained · source_alias');
assert.equal(restoreFilter({verdict:'all',kind:'all'}).sort,'triage');
assert.equal(restoreFilter({verdict:'all',kind:'all'}).direction,'asc');
assert.equal(restoreFilter({...DEFAULT_FILTER,sort:'score',direction:'desc'}).sort,'score');
assert.equal(restoreFilter({...DEFAULT_FILTER,sort:'paper',direction:'asc'}).sort,'paper');
assert.deepEqual(cycleQueueSort(DEFAULT_FILTER,'paper'),{sort:'paper',direction:'asc'});
assert.deepEqual(cycleQueueSort({...DEFAULT_FILTER,sort:'paper',direction:'asc'},'paper'),{sort:'paper',direction:'desc'});
assert.deepEqual(cycleQueueSort({...DEFAULT_FILTER,sort:'paper',direction:'desc'},'paper'),{sort:'triage',direction:'asc'});
assert.deepEqual(cycleQueueSort({...DEFAULT_FILTER,sort:'paper',direction:'desc'},'paper','score'),{sort:'score',direction:'desc'});
assert.deepEqual(cycleQueueSort(DEFAULT_FILTER,'decision'),{sort:'decision',direction:'asc'});
// Year starts newest first, then oldest first, then back to score.
assert.deepEqual(cycleQueueSort(DEFAULT_FILTER,'year'),{sort:'year',direction:'desc'});
assert.deepEqual(cycleQueueSort({...DEFAULT_FILTER,sort:'year',direction:'desc'},'year'),{sort:'year',direction:'asc'});
assert.deepEqual(cycleQueueSort({...DEFAULT_FILTER,sort:'year',direction:'asc'},'year'),{sort:'triage',direction:'asc'});
assert.equal(restoreFilter({verdict:'all',sort:'decision'}).direction,'asc');
assert.equal(restoreFilter({...DEFAULT_FILTER,sort:'bogus'}).sort,'triage');
assert.equal(paperColumn({...folderItem,kind:'cross',papers:[{dir:'a'},{dir:'b'}]}),'a ~ b');
const undecidedQueue=[{id:'a',decision:null},{id:'b',decision:null},{id:'c',decision:{decision:'false_positive'}},{id:'d',decision:null}];
assert.equal(nextUndecidedIn(undecidedQueue,'a')?.id,'b');
assert.equal(nextUndecidedIn(undecidedQueue,'b')?.id,'d');
assert.equal(nextUndecidedIn(undecidedQueue,'d')?.id,'a');
assert.equal(nextUndecidedIn(undecidedQueue.map(i=>i.id==='a'?{...i,decision:{decision:'true_issue'}}:i),'d')?.id,'b');
assert.equal(nextUndecidedIn([{id:'a',decision:{decision:'unsure'}}],'a'),null);
assert.equal(DECISIONS[0].length, 3);
assert.equal(DECISIONS.find(([v]) => v === "false_positive")?.[2], "False positive");
assert.deepEqual(DECISIONS.find(([v]) => v === "false_positive_scale_bar"),
  ["false_positive_scale_bar", "0", "False positive: scale bar"]);
assert.deepEqual(DECISIONS.find(([v]) => v === "false_positive_channels"),
  ["false_positive_channels", "c", "False positive: different channels"]);
assert.deepEqual(DECISIONS.find(([v]) => v === "false_positive_logo"),
  ["false_positive_logo", "l", "False positive: logo"]);
// Every item-page shortcut is distinct.
assert.equal(new Set(DECISIONS.map(([, k]) => k)).size, DECISIONS.length);
assert.equal(DECISIONS.find(([v]) => v === "true_issue")?.[1], "1");
/** Path-containment rules the media/review routes must keep. */
import assert from "node:assert/strict";
import {
  badProject, badRel, contained, posixRel, sameRel,
  windowsAbsToWsl, wslAbsToWindows,
} from "../lib/paths.ts";
import { mediaBasename, mediaDisposition, mediaType } from "../lib/media.ts";
import {
  findingsNeighbors, lastFindingsIn, paperHasFindings, reviewHref, caughtUpHref,
} from "../lib/nav.ts";
import {
  comparisonGroups, highlightJumps, passageKey, pickTarget, primaryJumpTarget,
} from "../lib/targets.ts";
import { findQuoteSpans, fold } from "../lib/haystack.ts";
import { revealArgv } from "../lib/reveal.ts";
import { mergePdfBoxes } from "../lib/pdfBoxes.ts";
import { REVIEW_QUEUED_MESSAGE, reviewSyncCompleted } from "../lib/reviewSync.ts";
import {
  describeTransform, fromAffine, fromBoxes, invert, isAxisAligned, mirrorBox, quadThrough,
  toOriginalB, viewModes,
} from "../lib/affine.ts";
import {
  availableViews, canToggle, canZoomIn, canZoomOut, defaultView,
  parseStoredView, parseStoredZoom, unanchoredReason, zoomIn, zoomLabel,
  zoomOut, ZOOM_FIT, ZOOM_STEPS,
} from "../lib/sourceView.ts";
import { doiLink, normalizeDoi, pubpeerSearchLink } from "../lib/citation.ts";
import {
  compactRunAt,
  cycleSort,
  defaultSort,
  firstSortDir,
  sortPapers,
  nonImageFindings,
  pipelineVersionOf,
  viewState,
  viewedLabel,
  viewedTitle,
} from "../lib/projectTableSort.ts";

assert.match(REVIEW_QUEUED_MESSAGE, /synchronizing with database/);
assert.doesNotMatch(REVIEW_QUEUED_MESSAGE, /needs retry/);
assert.equal(reviewSyncCompleted(1, 0), true);
assert.equal(reviewSyncCompleted(2, 1), true);
assert.equal(reviewSyncCompleted(1, 1), false);
assert.equal(reviewSyncCompleted(0, 0), false);

assert.equal(badRel("/etc/passwd"), true);
assert.equal(badRel("..\\windows"), true);
assert.equal(badRel("../secret"), true);
assert.equal(badRel("paper.pdf"), false);
assert.equal(badRel("panels/review/x.mp4"), false);
assert.equal(badRel("done/10.1--x"), false);
assert.equal(badRel("..\\secret.xlsx"), true);
assert.equal(badRel("cars.xlsx"), false);
assert.equal(badRel("grok_run/10.1--x"), false);
assert.equal(badRel("grok_run\\10.1--x"), false);
assert.equal(badRel("C:\\Users\\greg\\secret.xlsx"), true);
assert.equal(badRel("C:/Users/greg/secret.xlsx"), true);
assert.equal(posixRel("grok_run\\10.1--x"), "grok_run/10.1--x");
assert.equal(sameRel("grok_run/10.x", "grok_run\\10.x"), true);
assert.equal(sameRel("done/10.x", "grok_run/10.x"), false);
assert.equal(
  windowsAbsToWsl("C:\\Users\\greg\\Dropbox\\papers"),
  "/mnt/c/Users/greg/Dropbox/papers",
);
assert.equal(
  windowsAbsToWsl("D:/data/masliah_papers"),
  "/mnt/d/data/masliah_papers",
);
assert.equal(
  wslAbsToWindows("/mnt/c/Users/greg/Dropbox/papers"),
  "C:\\Users\\greg\\Dropbox\\papers",
);
assert.equal(contained("/proj", "/proj/grok_run/10.x"), true);
assert.equal(contained("/proj", "/proj"), false);
assert.equal(contained("/proj", "/other/grok_run/10.x"), false);
assert.equal(badProject("masliah_papers"), false);
assert.equal(badProject("../etc"), true);
assert.equal(badProject("a/b"), true);
assert.equal(badProject("a\\b"), true);

assert.equal(
  mediaBasename("done/10.x/cars.xlsx"),
  "cars.xlsx",
);
assert.equal(
  mediaDisposition("10.3390--x_linked_data.xlsx"),
  'attachment; filename="10.3390--x_linked_data.xlsx"; filename*=UTF-8\'\'10.3390--x_linked_data.xlsx',
);
assert.match(mediaDisposition("paper.pdf"), /^inline;/);
assert.match(mediaDisposition("paper.pdf", true), /^attachment;/);
assert.match(mediaDisposition("si/tables.xlsx"), /\.xlsx"/);
assert.equal(
  mediaType("foo.xlsx"),
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
);

// Platform fallback commands. Linux's preferred FileManager1 path is tested
// in reveal.mjs; its xdg-open fallback opens the directory only.
assert.deepEqual(revealArgv("win32", "C:\\p\\10.x", "C:\\p\\10.x\\paper.pdf"),
                 ["explorer", "/select,C:\\p\\10.x\\paper.pdf"]);
assert.deepEqual(revealArgv("win32", "C:\\p\\10.x", null), ["explorer", "C:\\p\\10.x"]);
assert.deepEqual(revealArgv("darwin", "/p/10.x", "/p/10.x/paper.pdf"),
                 ["open", "-R", "/p/10.x/paper.pdf"]);
assert.deepEqual(revealArgv("darwin", "/p/10.x", null), ["open", "/p/10.x"]);
assert.deepEqual(revealArgv("linux", "/p/10.x", "/p/10.x/paper.pdf"),
                 ["xdg-open", "/p/10.x"]);

assert.equal(paperHasFindings({ n_findings: 2, n_image_findings: 0 }), true);
assert.equal(paperHasFindings({ n_findings: 0, n_image_findings: 3 }), true);
assert.equal(paperHasFindings({ n_findings: null, n_image_findings: null }), false);
assert.equal(paperHasFindings({ n_findings: 0, n_image_findings: 0 }), false);

const queue = [
  { paper_id: "a", dir: "a", n_findings: 0, n_image_findings: 0 },
  { paper_id: "b", dir: "b", n_findings: 2, n_image_findings: 0 },
  { paper_id: "c", dir: "c", n_findings: null, n_image_findings: null },
  { paper_id: "d", dir: "d", n_findings: 0, n_image_findings: 1 },
  { paper_id: "e", dir: "e", n_findings: 0, n_image_findings: 0 },
];
assert.deepEqual(findingsNeighbors(queue, "a", "a"), {
  prev: null, next: { slug: "b", dir: "b" },
});
assert.deepEqual(findingsNeighbors(queue, "b", "b"), {
  prev: null, next: { slug: "d", dir: "d" },
});
assert.deepEqual(findingsNeighbors(queue, "c", "c"), {
  prev: { slug: "b", dir: "b" }, next: { slug: "d", dir: "d" },
});
assert.deepEqual(findingsNeighbors(queue, "d", "d"), {
  prev: { slug: "b", dir: "b" }, next: null,
});
assert.deepEqual(
  findingsNeighbors([
    { paper_id: "x", dir: "top", n_findings: 1, n_image_findings: 0 },
    { paper_id: "x", dir: "grok_run/10.x", n_findings: 2, n_image_findings: 0 },
  ], "x", "grok_run\\10.x"),
  { prev: { slug: "x", dir: "top" }, next: null },
);
assert.deepEqual(lastFindingsIn(queue), { slug: "d", dir: "d" });
assert.equal(
  reviewHref("masliah_papers", "10.x", "done/10.x"),
  "/project/masliah_papers/review/10.x?dir=done%2F10.x",
);
assert.equal(caughtUpHref("masliah_papers"), "/project/masliah_papers/caught-up");

assert.equal(firstSortDir("title"), "asc");
assert.equal(firstSortDir("author"), "asc");
assert.equal(firstSortDir("journal"), "asc");
assert.equal(firstSortDir("folder"), "asc");
assert.equal(firstSortDir("year"), "desc");
assert.equal(firstSortDir("run"), "desc");
assert.equal(firstSortDir("verdict"), "desc");
assert.equal(firstSortDir("sev9"), "desc");
assert.equal(firstSortDir("findings"), "desc");
assert.equal(firstSortDir("image"), "desc");

assert.deepEqual(cycleSort(null, "title"), { key: "title", dir: "asc" });
assert.deepEqual(cycleSort({ key: "title", dir: "asc" }, "title"),
  { key: "title", dir: "desc" });
assert.equal(cycleSort({ key: "title", dir: "desc" }, "title"), null);
assert.deepEqual(cycleSort(null, "year"), { key: "year", dir: "desc" });
assert.deepEqual(cycleSort({ key: "year", dir: "desc" }, "year"),
  { key: "year", dir: "asc" });
assert.equal(cycleSort({ key: "year", dir: "asc" }, "year"), null);
assert.deepEqual(cycleSort({ key: "title", dir: "asc" }, "author"),
  { key: "author", dir: "asc" });

function paper(over) {
  return {
    paper_id: "p",
    dir: "p",
    doi: null,
    title: null,
    authors: null,
    first_author: null,
    journal: null,
    volume: null,
    issue: null,
    year: null,
    n_runs: 0,
    runs: [],
    latest_run: null,
    analysed_at: null,
    verdict: null,
    worst_severity_9: null,
    n_findings: null,
    n_image_findings: null,
    review: { reviewed: false, n_decisions: 0 },
    sources: { state: "ok", pdf: true, xml: false, body_md: false, landing_page_only: false },
    evidence: [],
    channels: {},
    ...over,
  };
}

function ids(rows) {
  return rows.map((p) => p.paper_id);
}

const byTitle = [
  paper({ paper_id: "c", dir: "c", title: "Zebrafish" }),
  paper({ paper_id: "a", dir: "a", title: "apple cider" }),
  paper({ paper_id: "b", dir: "b", title: "Banana" }),
  paper({ paper_id: "m", dir: "missing-folder", title: null }),
];
assert.deepEqual(ids(sortPapers(byTitle, { key: "title", dir: "asc" })),
  ["a", "b", "m", "c"]);
assert.deepEqual(ids(sortPapers(byTitle, { key: "title", dir: "desc" })),
  ["c", "m", "b", "a"]);
assert.equal(sortPapers(byTitle, null), byTitle);

const byTaggedTitle = [
  paper({ paper_id: "i", dir: "i", title: "<i>De Novo</i> Prion" }),
  paper({ paper_id: "a", dir: "a", title: "apple" }),
];
assert.deepEqual(ids(sortPapers(byTaggedTitle, { key: "title", dir: "asc" })),
  ["a", "i"]);

const byAuthor = [
  paper({ paper_id: "raw-first", dir: "raw-first",
          first_author: "Manson, Charles Darwin" }),
  paper({ paper_id: "display-kept", dir: "display-kept",
          first_author: "Manson, A" }),
];
// displayFirstAuthor("Manson, Charles Darwin") → "Manson"; raw would put
// "Manson, A" first. Sorted display puts the shortened name first.
assert.deepEqual(ids(sortPapers(byAuthor, { key: "author", dir: "asc" })),
  ["raw-first", "display-kept"]);

const byAuthorMissing = [
  paper({ paper_id: "named", dir: "named", first_author: "Ng" }),
  paper({ paper_id: "blank", dir: "blank", first_author: null }),
];
assert.deepEqual(ids(sortPapers(byAuthorMissing, { key: "author", dir: "asc" })),
  ["named", "blank"]);
assert.deepEqual(ids(sortPapers(byAuthorMissing, { key: "author", dir: "desc" })),
  ["named", "blank"]);

const byJournal = [
  paper({ paper_id: "n", dir: "n", journal: "Nature" }),
  paper({ paper_id: "c", dir: "c", journal: "cell" }),
  paper({ paper_id: "x", dir: "x", journal: null }),
];
assert.deepEqual(ids(sortPapers(byJournal, { key: "journal", dir: "asc" })),
  ["c", "n", "x"]);

const byYear = [
  paper({ paper_id: "old", dir: "old", year: "1999" }),
  paper({ paper_id: "new", dir: "new", year: 2020 }),
  paper({ paper_id: "none", dir: "none", year: null }),
];
assert.deepEqual(ids(sortPapers(byYear, { key: "year", dir: "desc" })),
  ["new", "old", "none"]);
assert.deepEqual(ids(sortPapers(byYear, { key: "year", dir: "asc" })),
  ["old", "new", "none"]);

const byFolder = [
  paper({ paper_id: "z", dir: "done/z" }),
  paper({ paper_id: "a", dir: "done/a" }),
];
assert.deepEqual(ids(sortPapers(byFolder, { key: "folder", dir: "asc" })),
  ["a", "z"]);

const byImage = [
  paper({ paper_id: "none", dir: "none", n_image_findings: null }),
  paper({ paper_id: "zero", dir: "zero", n_image_findings: 0 }),
  paper({ paper_id: "two", dir: "two", n_image_findings: 2 }),
];
assert.deepEqual(ids(sortPapers(byImage, { key: "image", dir: "desc" })),
  ["two", "zero", "none"]);
assert.deepEqual(defaultSort(byImage), { key: "run", dir: "desc" });
assert.deepEqual(defaultSort(byTitle), { key: "run", dir: "desc" });

const byVerdict = [
  paper({ paper_id: "ok", dir: "ok", verdict: "reconciles" }),
  paper({ paper_id: "bad", dir: "bad", verdict: "does_not_reconcile" }),
  paper({ paper_id: "mid", dir: "mid", verdict: "unresolved" }),
  paper({ paper_id: "legacy", dir: "legacy", verdict: "untrustworthy" }),
  paper({ paper_id: "none", dir: "none", verdict: null }),
];
assert.deepEqual(ids(sortPapers(byVerdict, { key: "verdict", dir: "desc" })),
  ["bad", "legacy", "mid", "ok", "none"]);
assert.deepEqual(ids(sortPapers(byVerdict, { key: "verdict", dir: "asc" })),
  ["ok", "mid", "bad", "legacy", "none"]);

const bySev9 = [
  paper({ paper_id: "low", dir: "low", worst_severity_9: 1 }),
  paper({ paper_id: "top", dir: "top", worst_severity_9: 9 }),
  paper({ paper_id: "mid", dir: "mid", worst_severity_9: 4 }),
  paper({ paper_id: "none", dir: "none", worst_severity_9: null }),
];
assert.deepEqual(ids(sortPapers(bySev9, { key: "sev9", dir: "desc" })),
  ["top", "mid", "low", "none"]);
assert.deepEqual(ids(sortPapers(bySev9, { key: "sev9", dir: "asc" })),
  ["low", "mid", "top", "none"]);

// The column counts findings the IMAGE track did not produce. `stale` is an
// index written before the field existed: it has a total and no non-image
// count, which is absence, not zero -- it sorts last in both directions and
// never borrows `n_findings`.
const byFindings = [
  paper({ paper_id: "none", dir: "none", n_findings: null }),
  paper({ paper_id: "zero", dir: "zero", n_findings: 4,
          n_non_image_findings: 0, n_image_findings: 4 }),
  paper({ paper_id: "two", dir: "two", n_findings: 2,
          n_non_image_findings: 2 }),
  paper({ paper_id: "stale", dir: "stale", n_findings: 9 }),
];
assert.deepEqual(ids(sortPapers(byFindings, { key: "findings", dir: "desc" })),
  ["two", "zero", "none", "stale"]);
assert.deepEqual(ids(sortPapers(byFindings, { key: "findings", dir: "asc" })),
  ["zero", "two", "none", "stale"]);
assert.equal(nonImageFindings(byFindings[3]), null);
assert.equal(nonImageFindings(byFindings[1]), 0);

const byVersion = [
  paper({ paper_id: "old", dir: "old", pipeline_version: "0.9.0" }),
  paper({ paper_id: "new", dir: "new", pipeline_version: "1.10.0" }),
  paper({ paper_id: "mid", dir: "mid", pipeline_version: "1.9.0" }),
  paper({ paper_id: "unversioned", dir: "unversioned" }),
];
assert.deepEqual(ids(sortPapers(byVersion, { key: "version", dir: "desc" })),
  ["new", "mid", "old", "unversioned"]);
assert.deepEqual(ids(sortPapers(byVersion, { key: "version", dir: "asc" })),
  ["old", "mid", "new", "unversioned"]);
assert.equal(pipelineVersionOf(byVersion[3]), "");
assert.equal(firstSortDir("version"), "desc");

// "Viewed?" — four states, and none of them may be spelled as another.
// The `paper()` factory has no `viewed` key on purpose, so every other row in
// this file exercises the unindexed path.
const seen = paper({
  paper_id: "seen", dir: "seen",
  viewed: { viewed: true, n_views: 2, first_at: "2026-08-22T10:00:00Z",
            last_at: "2026-08-22T18:00:00Z", viewers: ["Dan Elton"],
            source: "recorded" },
});
const inferred = paper({
  paper_id: "inferred", dir: "inferred",
  viewed: { viewed: true, n_views: 0, first_at: null,
            last_at: "2026-08-01T09:00:00Z", viewers: ["Dan Elton"],
            source: "inferred_from_review" },
});
const anon = paper({
  paper_id: "anon", dir: "anon",
  viewed: { viewed: true, n_views: 1, first_at: "2026-08-22T10:00:00Z",
            last_at: "2026-08-22T10:00:00Z", viewers: [null],
            source: "recorded" },
});
const unseen = paper({
  paper_id: "unseen", dir: "unseen",
  viewed: { viewed: false, n_views: 0, first_at: null, last_at: null,
            viewers: [], source: "none" },
});
const torn = paper({
  paper_id: "torn", dir: "torn",
  viewed: { viewed: null, n_views: null, first_at: null, last_at: null,
            viewers: [], source: "unreadable" },
});
const unindexed = paper({ paper_id: "unindexed", dir: "unindexed" });

assert.equal(viewedLabel(viewState(seen)), "yes");
// Inferred, not observed — the asterisk this table already uses for a mapped
// legacy severity.
assert.equal(viewedLabel(viewState(inferred)), "yes*");
assert.equal(viewedLabel(viewState(unseen)), "no");
assert.equal(viewedLabel(viewState(torn)), "?");
assert.equal(viewedLabel(viewState(unindexed)), "—");

// "no" must never be readable as "nobody has read this paper".
assert.match(viewedTitle(viewState(unseen)), /only been recorded since/);
assert.match(viewedTitle(viewState(unseen)), /not "nobody has read it"/);
assert.match(viewedTitle(viewState(torn)), /unknown/);
assert.match(viewedTitle(viewState(unindexed)), /predates view tracking/);
// A viewer who never set a name is not called "anonymous" — nobody chose it.
assert.match(viewedTitle(viewState(anon)), /had not set a name/);
assert.doesNotMatch(viewedTitle(viewState(anon)), /anonymous/);
assert.match(viewedTitle(viewState(inferred)), /recorded a review decision/);
assert.match(viewedTitle(viewState(seen)), /2 opens/);

// First click is ascending — un-opened first, because the table is a work
// queue. Unknown and unindexed sort last in BOTH directions.
assert.equal(firstSortDir("viewed"), "asc");
const byViewed = [seen, unseen, torn, unindexed];
assert.deepEqual(ids(sortPapers(byViewed, { key: "viewed", dir: "asc" })),
  ["unseen", "seen", "torn", "unindexed"]);
assert.deepEqual(ids(sortPapers(byViewed, { key: "viewed", dir: "desc" })),
  ["seen", "unseen", "torn", "unindexed"]);

assert.match(compactRunAt("2026-08-20T21:19:50"), /^\d+\/\d+/);

function t(over) {
  return {
    id: "a:pdf",
    kind: "pdf_text",
    confidence: "exact",
    boxes: [{ x0: 0, y0: 0, x1: 1, y1: 1, page: 1 }],
    ...over,
  };
}

const pdfA = t({ id: "a:pdf", kind: "pdf_text", label: "Results" });
const xmlA = t({
  id: "a:xml", kind: "xml_text", quote: "aged WTS glomerular paragraph here",
  boxes: undefined, label: "Results, aged WTS glomerular paragraph",
});
const pdfB = t({ id: "b:pdf", kind: "pdf_text", label: "Discussion" });
const xmlB = t({
  id: "b:xml", kind: "xml_text", quote: "second distinct quote of eight words here",
  boxes: undefined, label: "Discussion",
});
const pageOnly = t({
  id: "a:pdf", kind: "pdf_text", confidence: "page", boxes: [],
});

assert.equal(comparisonGroups([pdfA, xmlA]).length, 1);
assert.equal(highlightJumps([pdfA, xmlA]).length, 0);
assert.equal(primaryJumpTarget([pdfA, xmlA])?.id, "a:pdf");
assert.equal(pickTarget([pdfA, xmlA], "xml")?.id, "a:xml");

const two = highlightJumps([pdfA, xmlA, pdfB, xmlB]);
assert.deepEqual(two.map((j) => j.label), ["Highlight 1", "Highlight 2"]);
assert.equal(two[0].target.id, "a:pdf");
assert.equal(two[1].target.id, "b:pdf");
assert.equal(highlightJumps([pdfA, xmlA, pdfB, xmlB], "xml")[1].target.id, "b:xml");

assert.equal(comparisonGroups([pageOnly, xmlA]).length, 1);
assert.equal(highlightJumps([pageOnly, xmlA]).length, 0);
assert.equal(primaryJumpTarget([pageOnly, xmlA])?.id, "a:xml");

const imgP5 = t({
  id: "image:IMGDUP-1:page:5", kind: "pdf_bbox", confidence: "page",
  page: 5, boxes: [], label: "p. 5",
});
const imgP17 = t({
  id: "image:IMGDUP-1:page:17", kind: "pdf_bbox", confidence: "page",
  page: 17, boxes: [], label: "p. 17",
});
assert.equal(primaryJumpTarget([imgP5, imgP17])?.id, "image:IMGDUP-1:page:5");
// Legacy old-shape ids (no passage_key field) cut at the first colon, so two
// image pages stay one group and must not grow Highlight 1 / Highlight 2.
// Open p. N is the UI for archived runs.
assert.equal(highlightJumps([imgP5, imgP17]).length, 0);

// Persisted anchors carry passage_key as an explicit field, read before any
// id parsing (docs/specs/anchors.md §2/§9): same passage on two surfaces is
// still ONE comparison group.
const anchoredPdf = t({
  id: "f_9c1e22ab34cd56ef:a:pdf", passage_key: "f_9c1e22ab34cd56ef:a",
});
const anchoredXml = t({
  id: "f_9c1e22ab34cd56ef:a:xml", passage_key: "f_9c1e22ab34cd56ef:a",
  kind: "xml_text", quote: "mean 3.53 (SD 1.20), n = 30 in the treated group",
  boxes: undefined,
});
assert.equal(passageKey(anchoredPdf), "f_9c1e22ab34cd56ef:a");
assert.equal(passageKey({ id: "a:pdf" }), "a"); // legacy fallback unchanged
assert.equal(comparisonGroups([anchoredPdf, anchoredXml]).length, 1);

// The collision fix: one duplicated panel, two placements. Each placement
// page is its own passage (pg5 / pg17), so the pair a reviewer must blink
// between forms TWO comparison groups — the second highlight is reachable.
const placed5 = t({
  id: "f_1234567890abcdef:pg5:pdf", passage_key: "f_1234567890abcdef:pg5",
  kind: "pdf_bbox", confidence: "bbox", page: 5,
  boxes: [{ x0: 10, y0: 10, x1: 90, y1: 60, page: 5 }],
});
const placed17 = t({
  id: "f_1234567890abcdef:pg17:pdf", passage_key: "f_1234567890abcdef:pg17",
  kind: "pdf_bbox", confidence: "bbox", page: 17,
  boxes: [{ x0: 10, y0: 10, x1: 90, y1: 60, page: 17 }],
});
assert.equal(comparisonGroups([placed5, placed17]).length, 2);
assert.deepEqual(
  highlightJumps([placed5, placed17]).map((j) => j.target.id),
  ["f_1234567890abcdef:pg5:pdf", "f_1234567890abcdef:pg17:pdf"],
);

const mixed = [pdfA, xmlA, xmlB];
assert.equal(primaryJumpTarget(mixed)?.id, "a:xml");
assert.deepEqual(highlightJumps(mixed).map((j) => j.target.id), ["a:xml", "b:xml"]);
assert.equal(highlightJumps(mixed, "pdf")[0].target.id, "a:pdf");

assert.deepEqual(
  mergePdfBoxes([{ page: 1, x0: 0, y0: 0, x1: 1, y1: 1 }]),
  [],
);
assert.deepEqual(
  mergePdfBoxes([
    { page: 1, tid: "a", x0: 0, y0: 10, x1: 50, y1: 20 },
    { page: 1, tid: "a", x0: 52, y0: 10, x1: 100, y1: 20 },
  ]),
  [{ page: 1, tid: "a", x0: 0, y0: 10, x1: 100, y1: 20 }],
);
assert.equal(
  mergePdfBoxes([
    { page: 1, tid: "a", x0: 0, y0: 10, x1: 80, y1: 20 },
    { page: 1, tid: "a", x0: 0, y0: 30, x1: 80, y1: 40 },
  ]).length,
  2,
);
assert.equal(
  mergePdfBoxes([
    { page: 1, tid: "a", x0: 0, y0: 10, x1: 40, y1: 20 },
    { page: 1, tid: "b", x0: 41, y0: 10, x1: 80, y1: 20 },
  ]).length,
  2,
);

// HtmlArticlePane haystack (lib/haystack.ts): a quote spanning inline markup
// — here <i>cerebrolysin</i>, three text nodes — matches once and splits back
// into per-node spans in ORIGINAL offsets.
const nodesAcross = [
  { data: "The efficacy of " },
  { data: "cerebrolysin" },
  { data: " was 3.53 (SD 1.20), n = 30." },
];
const across = findQuoteSpans(nodesAcross, "efficacy of cerebrolysin was 3.53");
assert.equal(across.length, 1);
assert.deepEqual(across[0], [
  { node: 0, start: 4, end: 16 },
  { node: 1, start: 0, end: 12 },
  { node: 2, start: 0, end: 9 },
]);
// Absent quote: no spans, never a guess.
assert.equal(findQuoteSpans(nodesAcross, "not printed anywhere").length, 0);

// Typography folds (NBSP, spaced en dash, case) — renderer, not content.
const typo = [{ data: "Mean age was 42\u00a0–\u00a044 years" }];
assert.equal(findQuoteSpans(typo, "mean age was 42 - 44 years").length, 1);
assert.equal(findQuoteSpans(typo, "Mean age was 42-44 years").length, 1);
// Soft hyphen and ligature disappear under the fold (NFKC).
assert.equal(
  findQuoteSpans([{ data: "signiﬁ\u00adcant effect" }], "significant effect").length,
  1,
);
assert.equal(
  fold("Signiﬁcant ‘effect’ ≤ 0.05"),
  "significant 'effect' <= 0.05",
);

// Two occurrences are two matches; a whitespace-only node inside a match is
// dropped, never marked.
assert.equal(
  findQuoteSpans([{ data: "p < .05; " }, { data: "p < .05." }], "p < .05").length,
  2,
);
const sliver = findQuoteSpans(
  [{ data: "group A" }, { data: "\n  " }, { data: "versus group B" }],
  "group A versus group B",
);
assert.equal(sliver.length, 1);
assert.deepEqual(sliver[0].map((s) => s.node), [0, 2]);

console.log("ok");

// ---- source view: XML first when a paper ships both -------------------------
const BOTH = { has_xml: true, html: "<h1>x</h1>", pdf_relpath: "p.pdf" };
const PDF_ONLY = { has_xml: false, html: null, pdf_relpath: "p.pdf" };
const XML_ONLY = { has_xml: true, html: "<h1>x</h1>", pdf_relpath: null };
// mode "html"/"text" also carry `html` but are NOT xml -- must not offer a toggle.
const HTML_MODE = { mode: "html", has_xml: false, html: "<p>x</p>", pdf_relpath: null };
const TEXT_MODE = { mode: "text", has_xml: false, html: "<pre>x</pre>", pdf_relpath: null };

assert.deepEqual(availableViews(BOTH, false, false), ["pdf", "xml"]);
assert.deepEqual(availableViews(PDF_ONLY, false, false), ["pdf"]);
assert.deepEqual(availableViews(XML_ONLY, false, false), ["xml"]);
assert.deepEqual(availableViews(HTML_MODE, false, false), []);
assert.deepEqual(availableViews(TEXT_MODE, false, false), []);
assert.deepEqual(availableViews(BOTH, true, false), ["pdf", "xml", "sheet"]);
// a finding naming its own PDF counts even when the paper has no main PDF
assert.deepEqual(availableViews(XML_ONLY, false, true), ["pdf", "xml"]);

// XML wins with nothing stored; that is the whole point of the change.
assert.equal(defaultView(["pdf", "xml"], null), "xml");
assert.equal(defaultView(["pdf", "xml"], "pdf"), "pdf");
assert.equal(defaultView(["pdf", "xml"], "xml"), "xml");
// A stored choice the paper cannot draw must not win.
assert.equal(defaultView(["pdf"], "xml"), "pdf");
assert.equal(defaultView(["xml"], "pdf"), "xml");
// The finding names a spreadsheet: that is the evidence, whatever is stored.
assert.equal(defaultView(["pdf", "xml", "sheet"], "pdf"), "sheet");
assert.equal(defaultView([], null), "none");

assert.equal(canToggle(["pdf", "xml"]), true);
assert.equal(canToggle(["pdf"]), false);
assert.equal(canToggle(["xml"]), false);

assert.equal(parseStoredView("xml"), "xml");
assert.equal(parseStoredView("pdf"), "pdf");
assert.equal(parseStoredView("sheet"), null);   // never a sticky choice
assert.equal(parseStoredView(null), null);
assert.equal(parseStoredView("garbage"), null);

// ---- an absent mark must name its reason, never read as "nothing here" ------
const PDF_T = { kind: "pdf_text", confidence: "exact", boxes: [{ x0: 1, y0: 1, x1: 2, y1: 2 }] };
assert.equal(unanchoredReason("pdf", {}, [PDF_T], false), null);   // PdfPane speaks for itself
assert.equal(unanchoredReason("xml", {}, [PDF_T], true), null);    // a mark will be drawn
assert.deepEqual(unanchoredReason("xml", { kind: "numeric" }, [PDF_T], false), { code: "pdf_only" });
assert.deepEqual(unanchoredReason("xml", { kind: "image" }, [], false), { code: "image_finding" });
assert.deepEqual(
  unanchoredReason("xml", { kind: "numeric" }, [{ kind: "xml_text", section: "Results" }], false),
  { code: "section_only", section: "Results" },
);
assert.deepEqual(
  unanchoredReason("xml", { kind: "numeric", artefacts: [{ kind: "xlsx", basename: "S1.xlsx" }] }, [], false),
  { code: "supplement", file: "S1.xlsx" },
);
// An unlocated PDF target is not a PDF anchor -- do not promise a highlight.
assert.deepEqual(
  unanchoredReason("xml", { kind: "numeric" }, [{ kind: "pdf_text", confidence: "none" }], false),
  { code: "unlocated" },
);

// ---- a table-row quote must reach the cells of that row --------------------
//
// Two separate bugs stood between an XML table anchor and a visible mark, and
// each alone left it at zero matches. `fold` kept the pipe (quotes.py folds
// `_CELL_EDGE` to a space), and the haystack concatenates pieces with nothing
// between them, so two cells ran together as `GroupF (1.29) = 37.3`.
const ROW = ["Group", "F (1.29) = 37.3", "F (1.29) = 24.8"];
const ROW_QUOTE = "| Group | F (1.29) = 37.3 | F (1.29) = 24.8 |";

assert.equal(fold("| Group | F (1.29) = 37.3 |"), "group f (1.29) = 37.3");
assert.equal(fold("a || b"), "a b");

// Cells butted together cannot match: this is what the caller must not do.
assert.equal(findQuoteSpans(ROW.map((d) => ({ data: d })), ROW_QUOTE).length, 0);

// With a one-space piece at each block boundary, it matches and the spans land
// on the real cells (0, 2, 4) rather than on a separator.
const spaced = [];
ROW.forEach((d, i) => { if (i) spaced.push({ data: " " }); spaced.push({ data: d }); });
const rowHits = findQuoteSpans(spaced, ROW_QUOTE);
assert.equal(rowHits.length, 1);
assert.deepEqual(rowHits[0].map((s) => s.node), [0, 2, 4]);

// Digits stay untouched by the cell-edge fold -- the whole guarantee.
assert.equal(fold("|12.5|3.4|"), "12.5 3.4");

// ---- PDF zoom ladder --------------------------------------------------------
assert.equal(zoomIn(1), 1.25);
assert.equal(zoomIn(0.5), 0.75);
assert.equal(zoomOut(1), 0.75);
assert.equal(zoomOut(1.25), 1);
// The ends are stops, not wraps.
assert.equal(zoomIn(3), 3);
assert.equal(zoomOut(0.5), 0.5);
assert.equal(canZoomIn(3), false);
assert.equal(canZoomOut(0.5), false);
assert.equal(canZoomIn(1), true);
assert.equal(canZoomOut(1), true);
// A value off the ladder steps to the next rung, never past it.
assert.equal(zoomIn(1.1), 1.25);
assert.equal(zoomOut(1.1), 1);
// Storage: only a real rung is honoured, everything else means "fit".
assert.equal(parseStoredZoom("1.5"), 1.5);
assert.equal(parseStoredZoom("0.5"), 0.5);
assert.equal(parseStoredZoom("1.37"), ZOOM_FIT);   // not a rung
assert.equal(parseStoredZoom("garbage"), ZOOM_FIT);
assert.equal(parseStoredZoom(null), ZOOM_FIT);
assert.equal(parseStoredZoom("1e9"), ZOOM_FIT);
assert.equal(zoomLabel(1), "100%");
assert.equal(zoomLabel(0.75), "75%");
// Fit is the default and must stay on the ladder.
assert.ok(ZOOM_STEPS.includes(ZOOM_FIT));

// ---- PubPeer: a DOI SEARCH link, never a claim that a thread exists --------
// The pattern Dan specified, verbatim: the slash MUST arrive percent-encoded
// or PubPeer's search does not match the DOI.
assert.equal(
  pubpeerSearchLink("10.1152/ajpgi.00313.2020").href,
  "https://pubpeer.com/search?q=10.1152%2Fajpgi.00313.2020",
);
// A full doi.org URL is accepted and stripped, so a metadata record carrying
// either form gets the same link.
assert.equal(
  pubpeerSearchLink("https://doi.org/10.1152/ajpgi.00313.2020").href,
  "https://pubpeer.com/search?q=10.1152%2Fajpgi.00313.2020",
);
assert.equal(
  pubpeerSearchLink("  10.1007/s11033-014-3464-3  ").href,
  "https://pubpeer.com/search?q=10.1007%2Fs11033-014-3464-3",
);
// The label must not read as "this paper HAS a PubPeer thread" -- the project
// table's pubpeer_url is that fact; this is only a lookup.
assert.equal(pubpeerSearchLink("10.1152/ajpgi.00313.2020").label, "PubPeer search");
// No DOI, no link. A search for an empty string lands on PubPeer's whole
// index, which would read as a result about this paper.
assert.equal(pubpeerSearchLink(null), null);
assert.equal(pubpeerSearchLink(undefined), null);
assert.equal(pubpeerSearchLink(""), null);
assert.equal(pubpeerSearchLink("   "), null);
assert.equal(pubpeerSearchLink("not-a-doi"), null);
assert.equal(pubpeerSearchLink("PMC123456"), null);
// normalizeDoi is shared with doiLink, so both links agree on what a DOI is.
assert.equal(normalizeDoi("https://dx.doi.org/10.1/x"), "10.1/x");
assert.equal(normalizeDoi("10.1/x"), "10.1/x");
assert.equal(normalizeDoi("nope"), null);
assert.equal(doiLink("https://doi.org/10.1/x").href, "https://doi.org/10.1/x");
assert.equal(doiLink("nope"), null);
// The paper-directory fallback both surfaces use when a paper has no metadata
// record: `--` is the DOI's slash, and only the FIRST one is the separator.
assert.equal(
  pubpeerSearchLink("10.1007--s11033-014-3464-3".replace("--", "/")).href,
  "https://pubpeer.com/search?q=10.1007%2Fs11033-014-3464-3",
);

// ---- comparator geometry: the rotated box lands on the ORIGINAL panel -------
//
// The numbers are `within:10.1152--ajpgi.00313.2020:IMGDUP-1` as the detector
// recorded them (rotation -8.7 deg, scale 0.951, no flip): A is 455x364 px,
// B is 303x347 px, and the affine maps A -> B.
const AFF = fromAffine([[0.94032, 0.144574, -238.923311], [-0.144574, 0.94032, -14.419028]]);
const BOX_A = [209.4, 66.4, 448, 356.3];
const BOX_B = [6.6, 8.1, 221.2, 279.6];
const centre = (quad) => [quad.reduce((t, p) => t + p[0], 0) / 4, quad.reduce((t, p) => t + p[1], 0) / 4];
const within = ([x, y], b) => x > b[0] && x < b[2] && y > b[1] && y < b[3];

// A's box through the affine lands on B, tilted -- never axis-aligned. An
// inlier box is an axis-aligned BOUND, so its rotated image pokes past the
// panel edge by design (this one leaves B's top edge by ~17 px); what must
// hold is that the mapped region names the same tissue as B's own box, i.e.
// its centre sits inside that box.
const aInB = quadThrough(BOX_A, AFF);
assert.equal(aInB.length, 4);
assert.equal(isAxisAligned(aInB), false);
assert.ok(within(centre(aInB), BOX_B), `A's region maps away from B's box: ${JSON.stringify(aInB)}`);
// B's box through the inverse lands on A, tilted the other way, centred in A's box.
const bInA = quadThrough(BOX_B, invert(AFF));
assert.equal(isAxisAligned(bInA), false);
assert.ok(within(centre(bInA), BOX_A), `B's region maps away from A's box: ${JSON.stringify(bInA)}`);
// The tilt is the recorded one: the top edge of B-in-A rises 8.7 deg.
const [[x0, y0], [x1, y1]] = bInA;
assert.ok(Math.abs(Math.atan2(y1 - y0, x1 - x0) * 180 / Math.PI - 8.7) < 0.2);
// A 90-degree turn swaps a box's extents.
const ROT90 = [0, 1, -1, 0, 100, 0];   // x' = -y + 100, y' = x
const turned = quadThrough([10, 20, 50, 40], ROT90);
const xs = turned.map((p) => p[0]), ys = turned.map((p) => p[1]);
assert.equal(Math.max(...xs) - Math.min(...xs), 20);
assert.equal(Math.max(...ys) - Math.min(...ys), 40);
assert.equal(isAxisAligned(turned), true);
// The guessed fallback (no affine) is a similarity without rotation.
assert.equal(isAxisAligned(quadThrough(BOX_A, fromBoxes(BOX_A, BOX_B))), true);
assert.equal(fromAffine(null), null);
assert.equal(fromAffine([[1, 0]]), null);
// Flip: the detector's frame is B mirrored; composing the mirror back puts
// a point that sat at x in mirrored-B at width - x on B as printed.
const [fx, fy] = quadThrough([0, 0, 10, 10], toOriginalB([1, 0, 0, 1, 5, 5], true, 300))[0];
assert.equal(fx, 295);
assert.equal(fy, 5);
assert.deepEqual(toOriginalB(AFF, false, 303), AFF);
assert.deepEqual(mirrorBox([10, 20, 50, 40], 300), [250, 20, 290, 40]);

// The caption fragment says what the transform is, and nothing when the
// measurements record no transform at all (an old manifest).
assert.equal(describeTransform({ rotation_deg: -8.7, scale: 0.951, flip: false }), "rotation −8.7°, scale 0.951");
assert.equal(describeTransform({ rotation_deg: 90, scale: 1, flip: true }), "mirrored, rotation 90°");
assert.equal(describeTransform({ rotation_deg: 0, scale: 1, flip: false }), "translation only");
assert.equal(describeTransform({}), null);

// The video view exists only when a video was rendered.
assert.deepEqual(viewModes(true), ["side", "blink", "overlay", "video"]);
assert.deepEqual(viewModes(false), ["side", "blink", "overlay"]);

// Byte ranges must return the requested bytes, especially video suffix probes.
const { byteRange } = await import("../lib/byteRange.ts");
assert.deepEqual(byteRange("bytes=-16", 1000), { start: 984, end: 999 });
assert.deepEqual(byteRange("bytes=900-2000", 1000), { start: 900, end: 999 });
assert.deepEqual(byteRange("bytes=900-", 1000), { start: 900, end: 999 });
assert.equal(byteRange("bytes=1000-", 1000), false);
assert.equal(byteRange("bytes=-0", 1000), false);
assert.equal(byteRange("bytes=0-0", 0), false);
assert.equal(byteRange("bytes=0-1,5-6", 1000), null);
assert.equal(byteRange("bytes=-", 1000), false);
assert.equal(byteRange("bytes=2-1", 1000), false);
