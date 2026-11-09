// The browser component tests load transpiled app modules into a bare page
// through a tiny `require` over `window.modules`. The hooks fetch through
// swr, which ships no browser bundle, so this collects swr's own CommonJS
// build (and the two small packages it requires) from node_modules, wires
// their relative requires together, resolves `react` to the page's React
// (test/reactGlobals.mjs, or Next's compiled copy) and exposes the package
// as `window.modules.swr`. Run it after `window.React` is set.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const pkg = (name) => path.dirname(require.resolve(`${name}/package.json`));
const ENTRY = require.resolve('swr'); // the `require` condition: dist/index/index.js
const EXTERNAL = new Set(['react']);
// Packages whose `exports` map picks a build by NODE_ENV at runtime: name the
// development file directly instead of evaluating that switch in the page.
const PINNED = {
  'use-sync-external-store/shim': path.join(pkg('use-sync-external-store'), 'cjs/use-sync-external-store-shim.development.js'),
};

function resolveFrom(file, spec) {
  if (spec.startsWith('.')) return require.resolve(path.resolve(path.dirname(file), spec));
  return PINNED[spec] || require.resolve(spec);
}

/** Every CommonJS file reachable from the entry, with its resolved requires. */
function collect() {
  const files = new Map();
  const queue = [ENTRY];
  while (queue.length) {
    const file = queue.shift();
    if (files.has(file)) continue;
    const code = readFileSync(file, 'utf8');
    const resolved = {};
    for (const match of code.matchAll(/require\((['"])([^'"]+)\1\)/g)) {
      const spec = match[2];
      if (EXTERNAL.has(spec)) continue;
      resolved[spec] = resolveFrom(file, spec);
      queue.push(resolved[spec]);
    }
    files.set(file, { code, resolved });
  }
  return files;
}

export function swrGlobalsScript() {
  const files = collect();
  const defs = [...files].map(([file, { code }]) =>
    `${JSON.stringify(file)}: function (module, exports, require) {\n${code}\n}`,
  ).join(',\n');
  const links = Object.fromEntries([...files].map(([file, { resolved }]) => [file, resolved]));
  return `(() => {
  var process = { env: { NODE_ENV: 'development' } };
  var defs = {${defs}};
  var links = ${JSON.stringify(links)};
  var cache = {};
  function load(file) {
    if (cache[file]) return cache[file].exports;
    var module = cache[file] = { exports: {} };
    defs[file].call(module.exports, module, module.exports, function (spec) {
      if (spec === 'react') return window.React;
      if (!links[file][spec]) throw new Error('swrGlobals: no module ' + spec + ' from ' + file);
      return load(links[file][spec]);
    });
    return module.exports;
  }
  window.modules = window.modules || {};
  window.modules.swr = load(${JSON.stringify(ENTRY)});
})();`;
}

export async function addSwr(page) {
  await page.addScriptTag({ content: swrGlobalsScript() });
}
