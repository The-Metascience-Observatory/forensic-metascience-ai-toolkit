import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import path from 'node:path';
import { cacheRoot, choosePort, isPortFree, localBuild, localTsconfig } from '../scripts/serve.mjs';

function occupy(port) {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen({ port, host: '::' }, () => resolve(server));
  });
}

// This file runs both directly and through smoke.mjs in the parallel stack.
// Test exact next-port decisions against explicit availability, not a random
// range another test or application can occupy between probes.
const base = 3100;
const occupied = new Set();
const probe = async (port) => !occupied.has(port);
assert.equal(await choosePort(base, { fallback: true, maxTries: 5 }, probe), base);
occupied.add(base);
assert.equal(await choosePort(base, { fallback: true, maxTries: 5 }, probe), base + 1);
assert.equal(
  await choosePort(base, { fallback: true, skip: [base + 1], maxTries: 5 }, probe),
  base + 2,
);
await assert.rejects(
  () => choosePort(base, { fallback: false }, probe),
  /Port \d+ is already in use/,
);
occupied.add(base + 1);
assert.equal(await choosePort(base, { fallback: true, maxTries: 5 }, probe), base + 2);
await assert.rejects(
  () => choosePort(base, { fallback: true, maxTries: 2 }, probe),
  /No free port in/,
);

// Keep a real socket check. The OS assigns this port and we hold it throughout
// both assertions, so concurrent suites cannot change its occupancy.
const server = await occupy(0);
try {
  const port = server.address().port;
  assert.equal(await isPortFree(port), false);
  assert.equal(await isPortFree(0), true);
  await assert.rejects(() => choosePort(port, { fallback: false }), /already in use/);
} finally {
  await new Promise((resolve) => server.close(resolve));
}

// Build output goes to this machine's cache, never into the synced checkout.
const webappDir = '/sync/Dropbox/project/webapp';
const linux = { env: {}, platform: 'linux', home: '/home/u', webappDir };
assert.equal(cacheRoot(linux), '/home/u/.cache/metascience-webapp');
assert.equal(cacheRoot({ ...linux, env: { XDG_CACHE_HOME: '/xdg' } }), '/xdg/metascience-webapp');
assert.equal(cacheRoot({ ...linux, platform: 'darwin', home: '/Users/u' }), '/Users/u/Library/Caches/metascience-webapp');
assert.equal(cacheRoot({ ...linux, env: { METASCIENCE_NEXT_CACHE: '/fast' } }), '/fast');
const dev = localBuild('.next-dev', linux);
assert.ok(dev.absDist.startsWith('/home/u/.cache/metascience-webapp/'), dev.absDist);
assert.equal(path.basename(dev.absDist), '.next-dev');
assert.equal(path.resolve(webappDir, dev.dist), dev.absDist, 'distDir is joined onto the project folder');
assert.equal(path.basename(dev.tsconfig), 'tsconfig.next-dev.json');
assert.notEqual(
  localBuild('.next-dev', { ...linux, webappDir: '/other/checkout/webapp' }).absDist, dev.absDist,
  'two checkouts never share a build folder',
);
assert.equal(localBuild('/abs/build', linux).absDist, '/abs/build');
assert.deepEqual(
  localBuild('.next-dev', { ...linux, env: { METASCIENCE_NEXT_LOCAL_BUILD: '0' } }),
  { dist: '.next-dev', absDist: path.join(webappDir, '.next-dev'), tsconfig: null },
);
const ts = localTsconfig(dev, webappDir);
assert.equal(ts.extends, path.join(webappDir, 'tsconfig.json'));
assert.equal(ts.compilerOptions.baseUrl, webappDir, '`@/*` resolves from the webapp, not the cache');
assert.ok(ts.include.includes(`${dev.dist}/types/**/*.ts`), 'Next finds its own entry and leaves tsconfig.json alone');

console.log('serve port: occupied fallback, review-port skip, start refusal, and local build folder passed');
