import assert from 'node:assert/strict';
import { panelFigure, canReadXml } from '../lib/xmlFigures.ts';
const figures = [
  {id:'F1',label:'Figure 1',anchor:'one',graphics:[{reference:'main.jpg',relpath:'pmc_figures/main.jpg'}]},
  {id:'F5',label:'Extended Data Figure 1',anchor:'five',graphics:[{reference:'extended.jpg',relpath:'pmc_figures/extended.jpg'}]},
];
assert.equal(panelFigure({uid:'pmc_figures:pmc:extended.jpg-seg1',figure_label:'Figure 1'},figures).id,'F5');
assert.equal(panelFigure({uid:'other',figure_label:'Figure 1'},figures),undefined);
assert.equal(panelFigure({uid:'main',parent_image:'pmc_figures/main.jpg'},figures).id,'F1');
assert.equal(panelFigure({uid:'pmc:main.jpg-seg1'},[...figures,figures[0]]),undefined);
// A publisher rendition listed under the PMC figure: its file name is not the
// XML reference, so only its path links it (side B of bbamcr.2014.10.017 IMGDUP-8).
const both = [{id:'F1',label:'Fig. 1',anchor:'one',graphics:[{reference:'nihms1f1.jpg',relpath:'pmc_figures/nihms1f1.jpg'},
  {reference:'nihms1f1.jpg',relpath:'publisher_figures/1-s2.0-X-gr1_lrg.jpg'}]},
  {id:'F2',label:'Fig. 2',anchor:'two',graphics:[{reference:'nihms1f2.jpg',relpath:'publisher_figures/1-s2.0-X-gr2_lrg.jpg'}]}];
assert.equal(panelFigure({uid:'publisher_figures:pub:1-s2.0-X-gr1_lrg.jpg-seg1',image:'__runs/r/a',parent_image:'/expired/work/p.png'},both).id,'F1');
assert.equal(panelFigure({uid:'pmc_figures:pmc:nihms1f1.jpg-seg7',image:'__runs/r/b'},both).id,'F1');
assert.equal(panelFigure({uid:'publisher_figures:pub:1-s2.0-X-gr1.jpg-seg1'},both),undefined,'another rendition name is not this file');
assert.equal(canReadXml({document:{role:'pmc_render'}}),true);
assert.equal(canReadXml({document:{role:'supplement'}}),false);
console.log('XML figure identity and native supplement routing passed');
