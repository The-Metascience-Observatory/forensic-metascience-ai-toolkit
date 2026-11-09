// Isolated review/development servers. `dev` falls through to the next free
// port; `start` keeps 3101 so a second review process cannot hide the first.
import { createServer } from 'node:net';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { prepareAssets } from './prepare-assets.mjs';

const MAX_TRIES = 20;
const WEBAPP_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Build output lives in this machine's cache, never in the synced checkout.
// Dropbox synced a Mac `.next-dev` into the Linux one (2026-09-30): every page
// 500'd on /Users/dan paths and "conflicted copy" chunks. The cache folder is
// keyed by checkout path so two checkouts cannot share one build.
export function cacheRoot({ env = process.env, platform = process.platform, home = os.homedir() } = {}) {
  if (env.METASCIENCE_NEXT_CACHE) return path.resolve(env.METASCIENCE_NEXT_CACHE);
  if (platform === 'darwin') return path.join(home, 'Library', 'Caches', 'metascience-webapp');
  if (platform === 'win32') return path.join(env.LOCALAPPDATA || path.join(home, 'AppData', 'Local'), 'metascience-webapp');
  return path.join(env.XDG_CACHE_HOME || path.join(home, '.cache'), 'metascience-webapp');
}

// Next joins distDir and tsconfigPath onto the project folder, so both are
// returned relative to it. METASCIENCE_NEXT_LOCAL_BUILD=0 keeps the old
// in-checkout folder.
//
// Since Next 16 a distDir or tsconfig outside the project folder is refused
// (InvalidDistDirError; Turbopack: "leaves the filesystem root"), and neither
// check follows symlinks. So the checkout holds ONE symlink,
// `.next-cache-<hash>` (gitignored by `.next*`), to this checkout's cache
// folder, and `dist`/`tsconfig` are reached through it; `absDist` is the real
// folder. A Mac checkout of the same Dropbox folder has another cache path,
// so another link, and neither machine rewrites the other's.
// Dropbox does not follow a symlink out of the synced folder.
export function localBuild(name, { webappDir = WEBAPP_DIR, env = process.env, ...where } = {}) {
  if (env.METASCIENCE_NEXT_LOCAL_BUILD === '0') {
    return { dist: name, absDist: path.resolve(webappDir, name), link: null, tsconfig: null };
  }
  const key = createHash('sha256').update(webappDir).digest('hex').slice(0, 10);
  const root = path.isAbsolute(name) ? path.dirname(name) : path.join(cacheRoot({ env, ...where }), key);
  const base = path.basename(name);
  // Named for its target, so an absolute METASCIENCE_NEXT_DIST gets its own link.
  const linkKey = createHash('sha256').update(root).digest('hex').slice(0, 10);
  const link = { path: path.join(webappDir, `.next-cache-${linkKey}`), target: root };
  const via = (p) => path.relative(webappDir, path.join(link.path, p));
  return {
    dist: via(base),
    absDist: path.join(root, base),
    link,
    tsconfig: via(`tsconfig.${base.replace(/^\.+/, '')}.json`),
  };
}

// Point the checkout's link at its cache folder. A real directory under the
// link's name is someone's data, never deleted: refuse by name.
export function linkBuild(build) {
  if (!build.link) return;
  const { path: at, target } = build.link;
  let st = null;
  try { st = fs.lstatSync(at); } catch {}
  if (st && !st.isSymbolicLink()) {
    throw new Error(`${at} exists and is not a symlink; move it away so it can point at ${target}.`);
  }
  if (st && fs.readlinkSync(at) === target) return;
  if (st) fs.rmSync(at, { force: true });
  fs.symlinkSync(target, at, 'junction');
}

// Next appends `<distDir>/types/**/*.ts` to whichever tsconfig it reads. Given
// the checked-in one, every machine would add its own link name to it, so
// Next reads a generated file that extends it. Turbopack resolves a tsconfig
// inside the project only, so every path in it is RELATIVE to where Next sees
// it -- through the link, one folder below the webapp -- never absolute: with
// absolute `extends`/`baseUrl` Turbopack could not resolve `@/*` (2026-11-07).
export function localTsconfig(build, webappDir = WEBAPP_DIR) {
  const from = path.dirname(path.resolve(webappDir, build.tsconfig));
  const rel = (p) => path.relative(from, path.resolve(webappDir, p)) || '.';
  const types = path.relative(from, path.resolve(webappDir, build.dist));
  return {
    extends: rel('tsconfig.json'),
    compilerOptions: { baseUrl: rel('.'), plugins: [{ name: 'next' }] },
    include: [
      rel('next-env.d.ts'), rel('**/*.ts'), rel('**/*.tsx'),
      `${types}/types/**/*.ts`, `${types}/dev/types/**/*.ts`,
    ],
    exclude: [rel('node_modules')],
  };
}

// Server chunks and Next's generated route types sit in the cache folder and
// import `next` and `react`; a node_modules link beside them resolves those
// the ordinary way, for Node and TypeScript alike.
function prepareLocalBuild(build) {
  fs.mkdirSync(build.absDist, { recursive: true });
  if (!build.tsconfig) return;
  linkBuild(build);
  const modules = path.join(build.absDist, '..', 'node_modules');
  const target = path.join(WEBAPP_DIR, 'node_modules');
  let current = null;
  try { current = fs.readlinkSync(modules); } catch {}
  if (current !== target) {
    fs.rmSync(modules, { force: true });
    fs.symlinkSync(target, modules, 'junction');
  }
  const file = path.resolve(WEBAPP_DIR, build.tsconfig);
  const body = JSON.stringify(localTsconfig(build), null, 2) + '\n';
  if (!fs.existsSync(file) || fs.readFileSync(file, 'utf8') !== body) fs.writeFileSync(file, body);
}

// The workbench serves local papers, reviews and file paths with no
// authentication, so it listens on loopback only. Measured 2026-11-07: both
// servers accepted connections on every interface. Set
// METASCIENCE_WEBAPP_HOST=0.0.0.0 to expose it on purpose.
export function listenHost(env = process.env) {
  return env.METASCIENCE_WEBAPP_HOST || '127.0.0.1';
}

// Hosted mode (lib/accessToken.ts): Cloudflare Access in front, the app
// verifying its token. `start:hosted` refuses to start with any of the three
// variables unset, because a hosted deployment that silently fell back to
// local mode would be an open server behind the tunnel.
export const HOSTED_VARS = ['METASCIENCE_ACCESS_TEAM', 'METASCIENCE_ACCESS_AUD', 'METASCIENCE_PUBLIC_ORIGIN'];

export function hostedMode(env = process.env) {
  return Boolean((env.METASCIENCE_ACCESS_TEAM || '').trim() && (env.METASCIENCE_ACCESS_AUD || '').trim());
}

export function requireHostedEnv(env = process.env) {
  const missing = HOSTED_VARS.filter((k) => !(env[k] || '').trim());
  if (missing.length) {
    throw new Error(`start:hosted needs ${HOSTED_VARS.join(', ')}; missing: ${missing.join(', ')}. See webapp/README.md "Hosting".`);
  }
  let origin;
  try { origin = new URL(env.METASCIENCE_PUBLIC_ORIGIN.trim()); } catch {}
  if (!origin || origin.protocol !== 'https:') {
    throw new Error(`METASCIENCE_PUBLIC_ORIGIN must be an https origin, got ${env.METASCIENCE_PUBLIC_ORIGIN}`);
  }
}

export function modeBanner(env = process.env) {
  if (!hostedMode(env)) return 'Mode: local (no sign-in; loopback only)';
  const origin = (env.METASCIENCE_PUBLIC_ORIGIN || '').trim() || '(METASCIENCE_PUBLIC_ORIGIN unset: browser saves will be refused)';
  return `Mode: hosted (Cloudflare Access team ${env.METASCIENCE_ACCESS_TEAM.trim()}, public origin ${origin})`;
}

export function isPortFree(port) {
  return new Promise((resolve) => {
    const server = createServer();
    server.unref();
    server.once('error', () => resolve(false));
    // "::" is what Next binds by default, so probe the same address family.
    server.listen({ port, host: '::' }, () => server.close(() => resolve(true)));
  });
}

export async function choosePort(
  preferred,
  { fallback = true, maxTries = MAX_TRIES, skip = [] } = {},
  probe = isPortFree,
) {
  const skipped = new Set(skip);
  let port = preferred;
  let lastTried = preferred;
  for (let tried = 0; tried < maxTries; port++) {
    if (skipped.has(port)) continue;
    lastTried = port;
    tried++;
    if (await probe(port)) return port;
    if (!fallback) {
      throw new Error(
        `Port ${preferred} is already in use. Open the existing app or stop that server before restarting.`,
      );
    }
  }
  throw new Error(`No free port in ${preferred}-${lastTried}; set PORT=<n> to move the range.`);
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const argMode = process.argv[2] || 'start';
  if (!['build', 'start', 'dev', 'start:hosted'].includes(argMode)) throw new Error('Expected build, start, start:hosted, or dev');
  if (argMode === 'start:hosted') requireHostedEnv();
  const mode = argMode === 'start:hosted' ? 'start' : argMode;
  if (mode !== 'build') console.log(modeBanner());
  prepareAssets();
  const preferred = Number(process.env.PORT || (mode === 'dev' ? 3100 : 3101));
  if (!Number.isInteger(preferred) || preferred <= 0) {
    throw new Error(`Invalid PORT: ${process.env.PORT ?? preferred}`);
  }
  const build = localBuild(process.env.METASCIENCE_NEXT_DIST || (mode === 'dev' ? '.next-dev' : '.next-review'));
  prepareLocalBuild(build);
  let port = preferred;
  if (mode !== 'build') {
    if (mode === 'start' && !fs.existsSync(path.join(build.absDist, 'BUILD_ID'))) {
      throw new Error('Build the review app first with npm run build.');
    }
    port = await choosePort(preferred, {
      fallback: mode === 'dev',
      skip: mode === 'dev' && preferred !== 3101 ? [3101] : [],
    });
    if (port !== preferred) {
      console.log(`Port ${preferred} is in use; using http://localhost:${port} instead.`);
    }
  }
  const next = createRequire(import.meta.url).resolve('next/dist/bin/next');
  console.log(`Build folder: ${build.absDist}`);
  const child = spawn(process.execPath, [next, mode, ...(mode === 'build' ? [] : ['-p', String(port), '-H', listenHost()])], {
    stdio: 'inherit',
    env: {
      ...process.env, PORT: String(port),
      METASCIENCE_NEXT_DIST: build.dist,
      ...(build.tsconfig ? { METASCIENCE_NEXT_TSCONFIG: build.tsconfig } : {}),
    },
  });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    else process.exit(code ?? 0);
  });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
}
