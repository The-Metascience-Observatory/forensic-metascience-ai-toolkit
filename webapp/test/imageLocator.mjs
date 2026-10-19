/** The two item-page defects Phase 4 fixes, as pure helpers.
 *
 *  1. A page-only image placement used to reach `PdfPane` without a
 *     `method`, so the pane printed the numeric-token sentence for a
 *     figure whose page is known exactly.
 *  2. The main PDF was substituted for EVERY non-PDF document, so a
 *     publisher render or an SI image was shown beside a page of the main
 *     article it was never printed on. */
import assert from 'node:assert/strict';
import {
  buildPaneLocator, cropPolygonPixels, nativePaneSentence, paneDocument,
} from '../app/images/lib.ts';

// --- buildPaneLocator -------------------------------------------------------
assert.equal(buildPaneLocator([]), null);
const pageOnly = { id: 'it:a:0', kind: 'pdf_bbox', label: 'A p. 5', page: 5, boxes: [], confidence: 'page',
  method: 'placement_page', paper_dir: 'p' };
const loc = buildPaneLocator([pageOnly]);
assert.deepEqual(loc, { page: 5, confidence: 'page', method: 'placement_page', targets: [pageOnly] });
// A feed cached before `_targets` emitted `method` still gets the figure sentence.
const legacy = { ...pageOnly, method: undefined };
assert.equal(buildPaneLocator([legacy]).method, 'placement_page');
const boxed = { ...pageOnly, boxes: [{ page: 5, x0: 1, y0: 2, x1: 3, y1: 4, tid: 'it:a:0' }], confidence: 'bbox', method: undefined };
assert.equal(buildPaneLocator([boxed]).method, 'placement_bbox');
assert.equal(buildPaneLocator([boxed]).confidence, 'bbox');
// A text target (numeric tokens) carries whatever method the locator gave it, never an inferred one.
const text = { id: 't', kind: 'text', label: 'x', page: 2, boxes: [], confidence: 'page' };
assert.equal(buildPaneLocator([text]).method, undefined);
assert.equal(buildPaneLocator([text, pageOnly]).page, 2);

// --- paneDocument -----------------------------------------------------------
const paper = { dir: '10.1--x', pdf: '10.1--x.pdf' };
const mainPdf = { uid: 'x.pdf:xref1', paper_dir: '10.1--x', image: 'panels/xref1.png', placements: [],
  figure_label: null, caption_key: null, caption: null,
  document: { id: 'd', path: '10.1--x.pdf', role: 'main', status: 'present' } };
assert.deepEqual(paneDocument(mainPdf, paper), { kind: 'pdf', path: '10.1--x.pdf', substituted: false });
// An archived (retained) PDF path is a PDF whatever its extension.
assert.deepEqual(paneDocument({ ...mainPdf, document: { ...mainPdf.document, path: '__runs/r1/pdf' } }, paper),
  { kind: 'pdf', path: '__runs/r1/pdf', substituted: false });
// A supplement PDF is shown itself, never the main article.
assert.deepEqual(paneDocument({ ...mainPdf, document: { id: 's', path: 'supplements/si.pdf', role: 'supplement', status: 'present' } }, paper),
  { kind: 'pdf', path: 'supplements/si.pdf', substituted: false });
// Main/unknown role with a non-PDF (or absent) document path: the main PDF stands in.
assert.deepEqual(paneDocument({ ...mainPdf, document: { id: 'd', path: 'article.xml', role: 'main', status: 'present' } }, paper),
  { kind: 'pdf', path: '10.1--x.pdf', substituted: true });
assert.deepEqual(paneDocument({ ...mainPdf, document: undefined }, paper),
  { kind: 'pdf', path: '10.1--x.pdf', substituted: true });
assert.deepEqual(paneDocument({ ...mainPdf, document: { id: 'd', path: 'unknown', role: 'unknown', status: 'unavailable' } }, paper),
  { kind: 'pdf', path: '10.1--x.pdf', substituted: true });
// A publisher render is NOT the main PDF: native image, with the sentence.
const pmc = paneDocument({ ...mainPdf, uid: 'pmc_figures:pmc:F1.png', parent_image: 'pmc_figures/F1.png',
  document: { id: 'pmc', path: 'pmc_figures/manifest.json', role: 'pmc_render', status: 'present' } }, paper);
assert.equal(pmc.kind, 'native');
assert.equal(pmc.path, 'pmc_figures/manifest.json');
assert.equal(pmc.reason, 'No PDF location: this panel comes from pmc_figures/manifest.json; shown on its native image.');
assert.equal(nativePaneSentence('supplements/data.docx'),
  'No PDF location: this panel comes from supplements/data.docx; shown on its native image.');
// A DOCX supplement member likewise.
assert.equal(paneDocument({ ...mainPdf, document: { id: 'x', path: 'supplements/si.docx', role: 'supplement', status: 'present' } }, paper).kind, 'native');
// No PDF on disk at all: a main-role panel with an image shows natively and says why; with no image it says there is nothing.
const noPdf = paneDocument({ ...mainPdf, document: { id: 'd', path: 'article.xml', role: 'main', status: 'present' } }, { dir: '10.1--x', pdf: null });
assert.equal(noPdf.kind, 'native');
assert.match(noPdf.reason, /no PDF on disk for 10\.1--x/);
assert.deepEqual(paneDocument({ ...mainPdf, image: null, document: undefined }, { dir: '10.1--x' }),
  { kind: 'none', reason: 'No PDF on disk for 10.1--x.' });
assert.deepEqual(paneDocument(undefined, paper), { kind: 'pdf', path: '10.1--x.pdf', substituted: true });

// --- cropPolygonPixels (client twin of evidence._parent_locator) -------------
// The Python test: crop [0,0,100,100] of a 200x100 parent -> [[0,0],[100,0],[100,100],[0,100]].
assert.deepEqual(cropPolygonPixels([0, 0, 100, 100], [200, 100]), [[0, 0], [100, 0], [100, 100], [0, 100]]);
assert.deepEqual(cropPolygonPixels([10, 20, 60, 90], [200, 100]), [[20, 10], [90, 10], [90, 60], [20, 60]]);
assert.equal(cropPolygonPixels([0, 0, 101, 100], [200, 100]), null); // outside the parent
assert.equal(cropPolygonPixels([50, 0, 50, 100], [200, 100]), null); // empty
assert.equal(cropPolygonPixels(null, [200, 100]), null);
assert.equal(cropPolygonPixels([0, 0, 10, 10], null), null);
assert.equal(cropPolygonPixels([0, 0, 10, 10], [0, 100]), null);

console.log('image locator: page-only placements name the figure page, native documents stay native, crop outline matches Python');

// --- renditionLines (the figure source ledger, text only) --------------------
import { renditionLines } from '../app/images/lib.ts';
assert.deepEqual(renditionLines(undefined), { note: null, lines: [] });
assert.deepEqual(renditionLines({ state: 'absent', renditions: [] }),
  { note: 'Ledger absent: run metascience image-figure-sources', lines: [] });
assert.equal(renditionLines({ state: 'stale:index rewritten', renditions: [] }).note, 'Ledger stale: index rewritten');
const fs = { state: 'current', best_pixels: { rendition_id: 'els-1', source: 'elsevier', file: 'f.jpg', width: 2905, height: 1800 },
  links: { verified_keypoint: 1 },
  renditions: [
    { rendition_id: 'pdf-1', source: 'pdf_stream', width: 1200, height: 744, link: 'identity', framing: null },
    { rendition_id: 'els-1', source: 'elsevier', width: 2905, height: 1800, link: 'verified_keypoint', framing: 'full_figure' },
    { rendition_id: 'pmc-1', source: 'pmc', width: null, height: null, link: null }] };
assert.deepEqual(renditionLines(fs), { note: null, lines: [
  'pdf_stream 1200x744 · identity',
  'elsevier 2905x1800 · verified_keypoint · full_figure · best pixels',
  'pmc size unknown · link unmeasured'] });
// best_pixels as a bare rendition id marks the same line.
assert.equal(renditionLines({ ...fs, best_pixels: 'pdf-1' }).lines[0], 'pdf_stream 1200x744 · identity · best pixels');
console.log('renditions: ledger lines, best-pixels mark and state notes passed');

// Cross-paper archives: stale producer paths never override the exact-run PDF.
const archivedA={dir:'A',pdf:'__runs/exact-run/source-a'};
const archivedB={dir:'B',pdf:'__runs/exact-run/source-b'};
for (const path of ['/old/work/A/article.pdf','C:\\old\\article.pdf','../article.pdf']) {
 const panel={paper_dir:'A',document:{path,role:'main',status:'unavailable'}};
 assert.deepEqual(paneDocument(panel,archivedA),{kind:'pdf',path:archivedA.pdf,substituted:true});
 assert.equal(paneDocument(panel,archivedB).kind,'none');
 assert.notEqual(paneDocument({...panel,document:{path,role:'supplement'}},archivedA).kind,'pdf');
 assert.notEqual(paneDocument(panel,{dir:'A',pdf:null}).kind,'pdf');
}
assert.equal(paneDocument({paper_dir:'B',document:{path:'article.pdf',role:'main'}},archivedB).path,archivedB.pdf);
assert.equal(paneDocument({paper_dir:'A',document:{path:'__runs/exact-run/si',role:'supplement'}},archivedA).path,'__runs/exact-run/si');
