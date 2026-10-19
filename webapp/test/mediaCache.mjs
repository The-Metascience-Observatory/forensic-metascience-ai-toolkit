import assert from 'node:assert/strict';
import { cacheControl } from '../lib/media.ts';
// Sealed archive objects are content-addressed; paper files can change in place.
assert.equal(cacheControl('__runs/ar_1/a_panel', null), 'private, max-age=31536000, immutable');
assert.equal(cacheControl('__runs/ar_1/a_panel', 'thumbnail'), 'private, max-age=86400');
for (const f of ['panels/p.png', 'paper.pdf', '__runs/ar_1', '__runs/ar_1/a/b', '__videos/x/y', 'x/__runs/a/b'])
  assert.equal(cacheControl(f, null), 'private, no-cache', f);
console.log('media cache: immutable only for sealed archive references passed');
