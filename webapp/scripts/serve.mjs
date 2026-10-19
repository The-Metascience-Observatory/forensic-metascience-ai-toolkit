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
export function localBuild(name, { webappDir = WEBAPP_DIR, env = process.env, ...where } = {}) {
  if (env.METASCIENCE_NEXT_LOCAL_BUILD === '0') {
    return { dist: name, absDist: path.resolve(webappDir, name), tsconfig: null };
  }
  const key = createHash('sha256').update(webappDir).digest('hex').slice(0, 10);
  const root = path.join(cacheRoot({ env, ...where }), key);
  const absDist = path.isAbsolute(name) ? name : path.join(root, path.basename(name));
  return {
    dist: path.relative(webappDir, absDist),
    absDist,
    tsconfig: path.relative(webappDir, path.join(absDist, '..', `tsconfig.${path.basename(absDist).replace(/^\.+/, '')}.json`)),
  };
}

// Next appends `<distDir>/types/**/*.ts` to whichever tsconfig it reads. Given
// the checked-in one, every machine would add its own cache path to it, so
// Next reads a generated file that extends it. baseUrl pins `@/*` to the
// webapp: without it Next resolves paths from the generated file's folder.
export function localTsconfig(build, webappDir = WEBAPP_DIR) {
  const at = (p) => path.join(webappDir, p);
  return {
    extends: at('tsconfig.json'),
    compilerOptions: { baseUrl: webappDir, plugins: [{ name: 'next' }] },
    // The relative entry is the exact string Next looks for before appending
    // its own; the absolute one is what TypeScript actually reads.
    include: [
      at('next-env.d.ts'), at('**/*.ts'), at('**/*.tsx'),
      path.join(build.absDist, 'types/**/*.ts'), `${build.dist}/types/**/*.ts`,
    ],
    exclude: [at('node_modules')],
  };
}

// Server chunks and Next's generated route types sit in the cache folder and
// import `next` and `react`; a node_modules link beside them resolves those
// the ordinary way, for Node and TypeScript alike.
function prepareLocalBuild(build) {
  fs.mkdirSync(build.absDist, { recursive: true });
  if (!build.tsconfig) return;
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
  const mode = process.argv[2] || 'start';
  if (!['build', 'start', 'dev'].includes(mode)) throw new Error('Expected build, start, or dev');
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
  const child = spawn(process.execPath, [next, mode, ...(mode === 'build' ? [] : ['-p', String(port)])], {
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
