import assert from 'node:assert/strict';
import {entryStarts, stepEntry, isGroupStart, readGrouped} from '../lib/findingGroups.ts';
import {jumpable, surfaceOf, pdfBoxes, xmlCells, highlightJumps} from '../lib/targets.ts';
// The grouping rule itself runs in the service: tests/test_finding_groups.py.

const g = {id:'grp:a', family:'grim', tool:'grim_check', unit:'Table 2', n:3};
const items = [{id:'a'}, {id:'b',group:g}, {id:'c',group:g}, {id:'d',group:g}, {id:'e'}];
assert.deepEqual(entryStarts(items), [0, 1, 4]);
assert.equal(stepEntry(items, 0, 1), 1);       // onto the group's first finding
assert.equal(stepEntry(items, 2, 1), 4);       // from inside the group, past it
assert.equal(stepEntry(items, 4, -1), 1);
assert.equal(stepEntry(items, 0, -1), 0);
assert.equal(isGroupStart(items, 1), true);
assert.equal(isGroupStart(items, 2), false);
assert.equal(isGroupStart(items, 0), false);
assert.equal(readGrouped(null), true);
assert.equal(readGrouped('0'), false);

// Cell targets: an XML cell is jumpable by its address, a PDF cell by its box
// or, with no safe box, by its page.
const xml = {id:'f:cell-T1-r3c3:xml', kind:'xml_cell', confidence:'exact', table_num:1, row:3, col:3, passage_key:'f:cell-T1-r3c3'};
const pdf = {id:'f:cell-T1-r3c3:pdf', kind:'pdf_cell', confidence:'exact', page:4, passage_key:'f:cell-T1-r3c3',
             boxes:[{page:4,x0:1,y0:2,x1:3,y1:4}]};
const pageOnly = {id:'f:cell-T1-r4c1:pdf', kind:'pdf_cell', confidence:'page', page:4, boxes:[], passage_key:'f:cell-T1-r4c1'};
assert.equal(jumpable(xml), true);
assert.equal(jumpable({...xml, table_num:null}), false);
assert.equal(jumpable(pdf), true);
assert.equal(jumpable(pageOnly), true);
assert.equal(jumpable({...pageOnly, confidence:'none', page:null}), false);
assert.equal(surfaceOf(xml), 'xml');
assert.equal(surfaceOf(pdf), 'pdf');
assert.deepEqual(pdfBoxes({targets:[xml, pdf, pageOnly]}).map(b => b.tid), [pdf.id]);
assert.deepEqual(xmlCells([xml, pdf]), [{id:xml.id, tableNum:1, row:3, col:3}]);
// One cell, two surfaces: one comparison group, not two.
assert.equal(highlightJumps([xml, pdf, pageOnly], 'pdf').length, 2);
console.log('findingGroups ok');
