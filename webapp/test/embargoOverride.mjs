import assert from 'node:assert/strict';
import { OVERRIDE_VALUE, overrideConfirmed, overrideLine } from '../lib/embargoOverride.ts';
assert.equal(OVERRIDE_VALUE, 'submit-anyway');
assert.equal(overrideConfirmed('submit-anyway'), true);
// A plain submit, an empty field, or any other value does not lift the embargo.
for (const bad of ['', '1', 'true', 'yes', 'OVERRIDE EMBARGO', null, undefined]) assert.equal(overrideConfirmed(bad), false, String(bad));
const line = overrideLine({project:'p', dir:'d', doi:'10.1/x', website_id:'x-2025', marker:'/c/EMBARGO.json'}, new Date('2026-10-22T12:00:00Z'));
assert.ok(line.endsWith('\n'));
assert.deepEqual(JSON.parse(line), {at:'2026-10-22T12:00:00.000Z', action:'website_publication', project:'p', dir:'d', doi:'10.1/x', website_id:'x-2025', marker:'/c/EMBARGO.json', confirmed_by:'submit anyway button'});
console.log('embargo override: only the submit-anyway value lifts it; one JSON audit line per override');
