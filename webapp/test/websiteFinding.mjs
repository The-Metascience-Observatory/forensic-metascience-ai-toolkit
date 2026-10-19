import assert from 'node:assert/strict';
import { normalisePubpeerUrl, findingId, pngSize, citationFrom, isoDate } from '../lib/websiteFinding.ts';

// PubPeer links: publication pages only, comment anchors kept, #null dropped.
assert.equal(normalisePubpeerUrl('https://pubpeer.com/publications/d3ca75f4b73141b2efc69a0371351c'),
  'https://pubpeer.com/publications/D3CA75F4B73141B2EFC69A0371351C');
assert.equal(normalisePubpeerUrl(' https://pubpeer.com/publications/D3CA75F4B73141B2EFC69A0371351C#3 '),
  'https://pubpeer.com/publications/D3CA75F4B73141B2EFC69A0371351C#3');
assert.equal(normalisePubpeerUrl('https://pubpeer.com/publications/D3CA75F4B73141B2EFC69A0371351C#null'),
  'https://pubpeer.com/publications/D3CA75F4B73141B2EFC69A0371351C');
assert.equal(normalisePubpeerUrl('https://evil.example/publications/D3CA75F4B73141B2EFC69A0371351C'), null);
assert.equal(normalisePubpeerUrl('https://pubpeer.com/search?q=x'), null);
assert.equal(normalisePubpeerUrl('not a url'), null);

// Ids: first author's family name and year; suffixed when taken.
assert.equal(findingId({authors:'Manoj K. Pandey; Bokyung Sung', year:2010}, []), 'pandey-2010');
assert.equal(findingId({authors:'Manoj K. Pandey', year:2010}, ['pandey-2010']), 'pandey-2010-b');
assert.equal(findingId({authors:'Paloma Ordóñez-Morán', year:2012}, []), 'ordonez-moran-2012');
assert.equal(findingId({authors:'', year:null}, []), 'finding');

// PNG size from IHDR.
const png = new Uint8Array([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a, 0,0,0,13, 73,72,68,82, 0,0,6,0x36, 0,0,5,0xd4]);
assert.deepEqual(pngSize(png), {width:1590, height:1492});
assert.equal(pngSize(new Uint8Array([1,2,3])), null);

// Citation block: nulls, never "None"; refused without title or authors.
assert.deepEqual(citationFrom({authors:'A B', title:'T', journal:'J', volume:'1', issue:'', pages:'2-3', year:2010, url:''}, '10.1/x'),
  {authors:'A B', title:'T', journal:'J', volume:'1', issue:null, pages:'2-3', year:2010, url:'https://doi.org/10.1/x'});
assert.equal(citationFrom({title:'T'}, '10.1/x'), null);
assert.match(isoDate(new Date(2026, 8, 5)), /^2026-09-05$/);
