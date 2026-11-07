// React 19 ships no UMD builds, and the component tests render app modules in a
// bare page from `window.React` / `window.ReactDOM`. This loads React's own
// CommonJS development builds into the page with a tiny `require` and exposes
// the same two globals. `ReactDOM.render` (removed in React 19) is kept for the
// tests as a synchronous `createRoot(...).render` under `flushSync`, one root
// per container, which is what the legacy call did for them.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
// The packages' `exports` hide cjs/, so resolve each package folder first.
const pkg = (name) => path.dirname(require.resolve(`${name}/package.json`));
const FILES = {
  react: ['react', 'cjs/react.development.js'],
  'react-dom': ['react-dom', 'cjs/react-dom.development.js'],
  'react-dom/client': ['react-dom', 'cjs/react-dom-client.development.js'],
  scheduler: ['scheduler', 'cjs/scheduler.development.js'],
};

export function reactGlobalsScript() {
  const defs = Object.entries(FILES).map(([name, [from, file]]) =>
    `${JSON.stringify(name)}: function (module, exports, require) {\n${readFileSync(path.join(pkg(from), file), 'utf8')}\n}`,
  ).join(',\n');
  return `(() => {
  var process = { env: { NODE_ENV: 'development' } };
  var defs = {${defs}};
  var cache = {};
  function load(name) {
    if (cache[name]) return cache[name].exports;
    if (!defs[name]) throw new Error('reactGlobals: no module ' + name);
    var module = cache[name] = { exports: {} };
    defs[name].call(module.exports, module, module.exports, load);
    return module.exports;
  }
  var React = load('react'), dom = load('react-dom'), client = load('react-dom/client');
  var roots = new WeakMap();
  window.React = React;
  window.ReactDOM = Object.assign({}, dom, client, {
    render: function (element, container) {
      var root = roots.get(container);
      if (!root) { root = client.createRoot(container); roots.set(container, root); }
      dom.flushSync(function () { root.render(element); });
    },
  });
})();`;
}

export async function addReact(page) {
  await page.addScriptTag({ content: reactGlobalsScript() });
}
