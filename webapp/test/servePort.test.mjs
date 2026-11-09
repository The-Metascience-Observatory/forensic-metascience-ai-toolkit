import { test } from "vitest";
import assert from 'node:assert/strict';
import { createServer } from 'node:net';
import path from 'node:path';
import { cacheRoot, choosePort, isPortFree, linkBuild, listenHost, localBuild, localTsconfig } from '../scripts/serve.mjs';

test("servePort", async () => {
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
  // Next 16 refuses a distDir or tsconfig outside the project: both are reached
  // through one link inside the webapp whose target is the cache folder.
  assert.equal(path.dirname(dev.link.path), webappDir, 'the link sits in the webapp');
  assert.match(path.basename(dev.link.path), /^\.next-cache-[0-9a-f]{10}$/, 'gitignored by `.next*`');
  assert.equal(dev.link.target, path.dirname(dev.absDist));
  assert.equal(path.resolve(webappDir, dev.dist), path.join(dev.link.path, '.next-dev'), 'distDir is inside the project folder');
  assert.ok(!dev.dist.startsWith('..') && !path.isAbsolute(dev.dist));
  assert.equal(path.resolve(webappDir, dev.tsconfig), path.join(dev.link.path, 'tsconfig.next-dev.json'));
  const review = localBuild('.next-review', linux);
  assert.equal(review.link.path, dev.link.path, 'dev and review share one link per checkout');
  const other = localBuild('.next-dev', { ...linux, webappDir: '/other/checkout/webapp' });
  assert.notEqual(other.absDist, dev.absDist, 'two checkouts never share a build folder');
  assert.notEqual(path.basename(other.link.path), path.basename(dev.link.path), 'nor a link name, so Dropbox copies never collide');
  const abs = localBuild('/abs/build', linux);
  assert.equal(abs.absDist, '/abs/build');
  assert.equal(abs.link.target, '/abs');
  assert.notEqual(abs.link.path, dev.link.path, 'an absolute build folder gets its own link');
  assert.deepEqual(
    localBuild('.next-dev', { ...linux, env: { METASCIENCE_NEXT_LOCAL_BUILD: '0' } }),
    { dist: '.next-dev', absDist: path.join(webappDir, '.next-dev'), link: null, tsconfig: null },
  );
  const ts = localTsconfig(dev, webappDir);
  assert.equal(ts.extends, '../tsconfig.json', 'relative: Turbopack resolves inside the project only');
  assert.equal(ts.compilerOptions.baseUrl, '..', '`@/*` resolves from the webapp, not the cache');
  assert.ok(ts.include.includes('.next-dev/types/**/*.ts'));
  assert.ok(ts.include.every((p) => !path.isAbsolute(p)));

  // The link is replaced when stale and never replaces a real folder.
  {
    const fs = await import('node:fs');
    const os = await import('node:os');
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'serve-link-'));
    try {
      const at = path.join(tmp, 'link'); const t1 = path.join(tmp, 'a'); const t2 = path.join(tmp, 'b');
      fs.mkdirSync(t1); fs.mkdirSync(t2);
      linkBuild({ link: { path: at, target: t1 } });
      assert.equal(fs.readlinkSync(at), t1);
      linkBuild({ link: { path: at, target: t2 } });
      assert.equal(fs.readlinkSync(at), t2);
      fs.rmSync(at); fs.mkdirSync(at);
      assert.throws(() => linkBuild({ link: { path: at, target: t1 } }), /is not a symlink/);
      assert.ok(fs.statSync(at).isDirectory());
    } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
  }

  console.log('serve port: occupied fallback, review-port skip, start refusal, and local build folder passed');

  // Loopback unless exposure is asked for by name.
  assert.equal(listenHost({}), '127.0.0.1');
  assert.equal(listenHost({ METASCIENCE_WEBAPP_HOST: '0.0.0.0' }), '0.0.0.0');
});
