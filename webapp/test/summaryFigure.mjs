import assert from 'node:assert/strict';
import { imagePdfBoxes } from '../lib/imagePdfBoxes.ts';
import { chooseLayout, figureRect, summaryGroups, FIGURE_MARGIN_PT } from '../lib/summaryFigure.ts';
const placement = (page, path) => ({page, document_path:path, bbox_kind:'crop_exact',
  parent_size:[1000,500], transform:[400,0,0,200,50,70], page_size:[600,800], page_rotation:0});
const panel = (dir, page) => ({paper_dir:dir, crop_box:[100,200,300,600], figure_label:'Figure 2',
  document:{id:dir, path:`${dir}.pdf`, role:'main', status:'ok'}, placements:[placement(page, `${dir}.pdf`)]});
const paper = dir => ({dir, pdf:`${dir}.pdf`});
// The whole parent image (the printed figure), not the panel crop.
assert.deepEqual(figureRect(panel('a',1), placement(1,'a.pdf')), [50,70,450,270]);
assert.equal(figureRect(panel('a',1), {...placement(1,'a.pdf'), geometry_gap:'missing'}), null);
// Cross-paper: two figures, each framed with margin and holding its own box.
const cross = {id:'x', kind:'cross', panels:[panel('a',4), panel('b',9)], paper:paper('a'), papers:[paper('a'),paper('b')],
  measurements:{inlier_box_a:[0,0,50,50], inlier_box_b:[0,0,50,50]}};
const groups = summaryGroups(cross, imagePdfBoxes(cross, [[200,100],[200,100]]));
assert.equal(groups.length, 2);
assert.deepEqual(groups.map(g => [g.paperDir, g.page, g.sides, g.boxes.length, g.framed]), [['a',4,[0],1,true],['b',9,[1],1,true]]);
assert.deepEqual(groups[0].rect, [50-FIGURE_MARGIN_PT, 70-FIGURE_MARGIN_PT, 450+FIGURE_MARGIN_PT, 270+FIGURE_MARGIN_PT]);
// Same figure on the same page: one crop covering both sides, not two copies.
const within = {...cross, id:'w', panels:[panel('a',4), panel('a',4)], papers:[paper('a')]};
const one = summaryGroups(within, imagePdfBoxes(within, [[200,100],[200,100]]));
assert.equal(one.length, 1);
assert.deepEqual(one[0].sides, [0,1]);
assert.equal(one[0].boxes.length, 2);
// No exact placement: the page still shows, flagged unframed, no box.
const loose = {...cross, panels:[{...panel('a',4), placements:[{page:4, bbox:null, document_path:'a.pdf'}]}]};
const [page] = summaryGroups(loose, []);
assert.equal(page.framed, false);
assert.deepEqual(page.rect, [0,0,0,0]);
// Layout: nearer-square total wins.
assert.equal(chooseLayout([[400,200],[400,200]]), 'vertical');   // 800x200 vs 400x400
assert.equal(chooseLayout([[200,400],[200,400]]), 'horizontal'); // 400x400 vs 200x800
assert.equal(chooseLayout([[300,300]]), 'horizontal');
// References: full, no DOI, no "None".
import { formatReference, wrapText } from '../lib/summaryFigure.ts';
const meta = {doi:'10.1016/j.bbrc.2011.12.065', title:'SPARC expression induces cell cycle arrest.', journal:'Biochemical and Biophysical Research Communications',
  volume:'417', issue:'2', pages:'874-879', year:2011, url:'https://doi.org/10.1016/j.bbrc.2011.12.065',
  authors_list:[{given:'Chandramu',family:'Chetty'},{given:'Purnachandra Nagaraju',family:'Ganji'},{given:'Sajani S.',family:'Lakka'},{given:'Jean-Paul',family:'Roux'}]};
const ref = formatReference(meta);
assert.equal(ref, 'Chetty, C., Ganji, P. N., Lakka, S. S., & Roux, J.-P. (2011). SPARC expression induces cell cycle arrest. Biochemical and Biophysical Research Communications, 417(2), 874–879.');
assert.ok(!ref.includes('10.1016'));
assert.equal(formatReference({authors:'Chandramu Chetty', title:'T', year:null}), 'Chetty, C. T.');
assert.equal(formatReference({doi:'10.1/x'}), '');
assert.equal(formatReference(null), '');
assert.deepEqual(wrapText('aa bb cc dd', 5, s => s.length), ['aa bb','cc dd']);
assert.deepEqual(wrapText('averyverylongword x', 5, s => s.length), ['averyverylongword','x']);
// References only for cross-paper findings.
import { isCrossPaper } from '../lib/summaryFigure.ts';
assert.equal(isCrossPaper(cross), true);
assert.equal(isCrossPaper(within), false);
// The journal name is its own italic run; the rest stays roman.
import { referenceRuns, wrapRuns } from '../lib/summaryFigure.ts';
const runs = referenceRuns(meta);
assert.deepEqual(runs.filter(r => r.italic).map(r => r.text), ['Biochemical and Biophysical Research Communications']);
assert.equal(runs.map(r => r.text).join(''), ref);
assert.deepEqual(referenceRuns({title:'T', journal:'J'}), [{text:'T. '},{text:'J',italic:true},{text:'.'}]);
assert.deepEqual(referenceRuns({title:'T'}), [{text:'T.'}]);
// Wrapping keeps styles, merges same-style pieces, and splits a word at a style change.
assert.deepEqual(wrapRuns([{text:'a b '},{text:'Jn Cc',italic:true},{text:', 4.'}], 6, s => s.length),
  [[{text:'a b ',italic:false},{text:'Jn',italic:true}], [{text:'Cc',italic:true},{text:', 4.',italic:false}]]);
// Editing geometry.
import { normaliseRect, stageBounds, brandMetrics } from '../lib/summaryFigure.ts';
assert.deepEqual(normaliseRect({x0:50,y0:40,x1:-5,y1:10.4}, 30, 100), {x0:0,y0:10,x1:30,y1:40});
assert.equal(normaliseRect({x0:5,y0:5,x1:5,y1:9}, 30, 30), null);
assert.deepEqual(stageBounds(100, 80, null), {x0:0,y0:0,x1:100,y1:80});
assert.deepEqual(stageBounds(100, 80, {x:-20,y:70,w:30,h:30}), {x0:-20,y0:0,x1:100,y1:100});
assert.equal(brandMetrics(100).font, 18);
assert.equal(brandMetrics(100000).font, 56);
// Selection handles: grab, cursor, drag.
import { grabSelection, grabCursor, scaleRect } from '../lib/summaryFigure.ts';
const box = {x0:100,y0:100,x1:300,y1:200};
assert.deepEqual(grabSelection(box, {x:103,y:98}, 8), {l:true,r:false,t:true,b:false});
assert.deepEqual(grabSelection(box, {x:311,y:189}, 8), {l:false,r:true,t:false,b:true}); // corner zone is 1.5x an edge's
assert.equal(grabSelection(box, {x:311,y:150}, 8), null); // beyond an edge's reach
assert.equal(grabSelection(box, {x:200,y:150}, 8), 'inside');
assert.equal(grabSelection(box, {x:50,y:150}, 8), null);
assert.deepEqual(grabSelection(box, {x:300,y:150}, 8), {l:false,r:true,t:false,b:false});
assert.deepEqual(grabSelection({x0:0,y0:0,x1:10,y1:10}, {x:9,y:5}, 8), {l:false,r:true,t:false,b:false});
assert.equal(grabSelection({x0:0,y0:0,x1:10,y1:10}, {x:5,y:5}, 8), 'inside'); // a small box's middle still moves
assert.equal(grabCursor({t:true,l:true}), 'nw-resize');
assert.equal(grabCursor({r:true}), 'e-resize');
assert.equal(grabCursor('inside'), 'move');
assert.deepEqual(scaleRect(box, {r:true,b:true}, 200, 0), {x0:100,y0:100,x1:500,y1:300}); // corner: aspect kept, 2x
assert.deepEqual(scaleRect(box, {l:true,t:true}, 100, 10), {x0:200,y0:150,x1:300,y1:200}); // shrinks toward the far corner
assert.deepEqual(scaleRect(box, {r:true}, 50, 999), {x0:100,y0:100,x1:350,y1:200});        // edge: one axis only
assert.deepEqual(scaleRect(box, {l:true}, 999, 0), {x0:292,y0:100,x1:300,y1:200});         // never flips, min 8
// A paper with no PDF (PMC figure renders only): the summary figure is the
// native figure image, with the boxes the XML pane draws, one group per image.
import { nativeSides, nativeSummaryGroups } from '../lib/summaryFigure.ts';
const pmcName = 'nihms216620f1.jpg';
const pmcPanel = (crop, seg) => ({uid:`pmc_figures:pmc:${pmcName}-seg${seg}`, paper_dir:'p', image:`__runs/r/c${seg}`,
  parent_image:'/expired/work/panels/pmc/parent.png', crop_box:crop, figure_label:'Figure 1',
  document:{id:'p', path:'pmc_figures/manifest.json', role:'pmc_render', status:'present'},
  placements:[{page:null, bbox:null, document_path:'pmc_figures/manifest.json', bbox_kind:'parent_approximate'}]});
const pmcFigures = {p:[{anchor:'xml-figure-1', label:'Fig. 1', graphics:[{reference:pmcName, relpath:`pmc_figures/${pmcName}`, status:'local_current'}]}]};
const noPdf = {id:'n', detector_kind:'transformed_match', panels:[pmcPanel([169,614,303,795],6), pmcPanel([170,232,304,413],8)],
  paper:{dir:'p', pdf:null}, papers:[{dir:'p', pdf:null}],
  measurements:{inlier_box_a:[76.9,10.4,172.6,103.6], inlier_box_b:[29.9,31.2,125.8,124.8], flip:false}};
assert.deepEqual(summaryGroups(noPdf, []), [], 'no PDF page to crop');
assert.deepEqual(nativeSides(noPdf, []), [0,1]);
const sizes = [[181,134],[181,134]];
const native = nativeSummaryGroups(noPdf, [0,1], pmcFigures, sizes);
assert.equal(native.length, 1, 'both crops of one figure image make one figure');
assert.deepEqual([native[0].kind, native[0].imagePath, native[0].sides, native[0].figureLabels, native[0].boxes.length, native[0].clone],
  ['image', `pmc_figures/${pmcName}`, [0,1], ['Figure 1'], 2, false]);
assert.deepEqual(native[0].boxes.map(b => [b.side, b.index]), [[0,0],[1,0]]);
// Without the measured frame no box can be placed, so no figure is claimed.
assert.deepEqual(nativeSummaryGroups(noPdf, [0,1], pmcFigures), []);
// A figure list that cannot name the image links nothing.
assert.deepEqual(nativeSummaryGroups(noPdf, [0,1], {p:[]}, sizes), []);
// Only the requested sides.
assert.deepEqual(nativeSummaryGroups(noPdf, [1], pmcFigures, sizes)[0].sides, [1]);
// A paper WITH a PDF is the PDF path's business (the item page opens the PDF pane).
assert.deepEqual(nativeSides({...noPdf, paper:{dir:'p', pdf:'p.pdf'}, papers:[{dir:'p', pdf:'p.pdf'}]}, []), []);
// Cross-paper, one side on a PDF page: only the other side goes native.
const mixed = {...noPdf, kind:'cross', panels:[panel('a',4), {...pmcPanel([169,614,303,795],6), paper_dir:'p'}],
  paper:paper('a'), papers:[paper('a'), {dir:'p', pdf:null}]};
const mixedPdf = summaryGroups(mixed, imagePdfBoxes(mixed, [[200,100],[181,134]]));
assert.deepEqual(mixedPdf.map(g => g.sides), [[0]]);
assert.deepEqual(nativeSides(mixed, mixedPdf), [1]);
// A clone uses side 0 only, and its regions are labelled by index.
const cloneNative = nativeSummaryGroups({...noPdf, detector_kind:'intra_panel_clone',
  measurements:{panel_px_a:[181,134], regions:[{bbox:[0,0,20,20]},{bbox:[40,40,60,60]}]}}, [0], pmcFigures);
assert.deepEqual(cloneNative.map(g => [g.sides, g.clone, g.boxes.map(b => b.index)]), [[[0], true, [0,1]]]);
assert.deepEqual(nativeSides({...noPdf, detector_kind:'intra_panel_clone'}, []), [0]);
// A real split-stream regression: Viruses 2024 Figure 2 (10.3390/v16101509),
// page 9, xrefs 187/188. The second strip holds the bottom of the micrographs.
import { adjoiningFigureRect, expandFigureBox } from '../lib/summaryFigure.ts';
import { pdfImageRects } from '../lib/summaryPdfGeometry.ts';
const upper = [102.329, 313.461, 495.749, 574.281];
const lower = [102.329, 574.281, 495.749, 611.421];
assert.deepEqual(adjoiningFigureRect(upper, [upper, lower]), [102.329,313.461,495.749,611.421]);
assert.deepEqual(adjoiningFigureRect(lower, [upper, lower]), [102.329,313.461,495.749,611.421]);
assert.deepEqual(adjoiningFigureRect(upper, [[102.329,580,495.749,620]]), upper, 'a gap does not join separate figures');
assert.deepEqual(adjoiningFigureRect(upper, [[110,574.281,300,620]]), upper, 'partial edges do not join');
assert.deepEqual(adjoiningFigureRect([0,0,10,10], [[20,0,30,10],[10,0,20,10]]), [0,0,30,10]);
const ops = {save:1, restore:2, transform:3, paintImageXObject:4, paintInlineImageXObject:5, paintFormXObjectBegin:6, paintFormXObjectEnd:7};
const paints = {fnArray:[1,3,4,2,1,3,4,2], argsArray:[[],[393.42,0,0,260.82,102.329,267.609],['upper',3296,2184],[],[],[393.42,0,0,37.14,102.329,230.469],['lower',3296,312],[]]};
const rects = pdfImageRects(paints, ops, {transform:[1,0,0,-1,0,841.89]});
for (const [i,r] of rects.entries()) r.forEach((v,j) => assert.ok(Math.abs(v - [upper,lower][i][j]) < 1e-8));
assert.equal(rects.length,2);
assert.deepEqual(pdfImageRects({fnArray:[6,1,3,4,2,7],argsArray:[[[1,0,0,1,30,40]],[],[10,0,0,20,0,0],['im'],[],[]]},ops,{transform:[1,0,0,1,0,0]}),[[30,40,40,60]],'form and graphics state transforms compose');
const polygon = [[10,10],[30,10],[30,20],[10,20]];
assert.deepEqual(expandFigureBox(polygon,200,[0,0,100,100]),[[0,5],[40,5],[40,25],[0,25]]);
assert.deepEqual(expandFigureBox(polygon,100,[0,0,100,100]),polygon,'reset preserves exact original geometry');
assert.deepEqual(expandFigureBox(polygon,1000,[0,0,50,50]),[[0,0],[50,0],[50,50],[0,50]],'expansion stays on the figure');
assert.deepEqual(polygon,[[10,10],[30,10],[30,20],[10,20]],'original evidence geometry is untouched');
