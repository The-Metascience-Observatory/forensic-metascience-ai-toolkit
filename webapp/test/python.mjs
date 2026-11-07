import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pyModuleJson } from '../lib/python.ts';

// Exercise the actual child environment without relying on an editable install.
// Assert origins in this checkout, even if another version is installed.
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-python-'));
const oldPath = process.env.PYTHONPATH;
try {
  fs.writeFileSync(path.join(scratch, 'checkout_probe.py'), `
import importlib.util, json
print(json.dumps({name: getattr(importlib.util.find_spec(name), 'origin', None) for name in
    ['forensic_metascience_ai_toolkit', 'copy_paste_detector', 'metascience_observatory_image_analysis']}))
`);
  process.env.PYTHONPATH = scratch;
  // The inherited path must survive too: this module exists only there.
  const found = await pyModuleJson('checkout_probe', []);
  const repo = path.resolve(process.cwd(), '..');
  const toolkit = 'forensic_metascience_ai_toolkit';
  assert.equal(found[toolkit], path.join(repo, 'src', toolkit, '__init__.py'));
  // The image package and the copy-paste detector are their own repositories,
  // checked out beside the toolkit and optional. Where a sibling checkout
  // exists, it must win over any installed copy; elsewhere (a worktree, a
  // plugin-less machine) the bridge has nothing of its own to assert.
  for (const [name, checkout] of Object.entries({
    metascience_observatory_image_analysis: 'metascience-observatory-image-analysis',
    copy_paste_detector: 'metascience-observatory-copypaste-detector'})) {
    const sibling = path.join(repo, '..', checkout, 'src', name, '__init__.py');
    if (fs.existsSync(sibling)) assert.equal(found[name], sibling);
  }
} finally {
  if (oldPath === undefined) delete process.env.PYTHONPATH;
  else process.env.PYTHONPATH = oldPath;
  fs.rmSync(scratch, { recursive: true, force: true });
}

// A slow child must not prevent unrelated timers or another child completing.
let ticked = false, finished = false;
const timer = setTimeout(() => { ticked = !finished; }, 20);
const slow = pyModuleJson('timeit', ['-n', '1', '-r', '1', 'import time; time.sleep(0.4)']);
void slow.finally(() => { finished = true; }).catch(() => {});
const failure = assert.rejects(slow, SyntaxError); // timeit prints prose, not JSON
const json = await pyModuleJson('json.tool', [], { stdin: '{"nested":{"ok":true}}' });
assert.deepEqual(json, { nested: { ok: true } });
await failure;
assert.equal(ticked, true);
clearTimeout(timer);
await assert.rejects(pyModuleJson('timeit', ['-n','1','-r','1','import time; time.sleep(10)'], { timeoutMs: 50 }), /timed out/);
const one = pyModuleJson('json.tool', [], { stdin: '{"one":1}', dedupe: true });
const two = pyModuleJson('json.tool', [], { stdin: '{"one":1}', dedupe: true });
assert.equal(one, two);
assert.deepEqual(await one, { one: 1 });
console.log('python bridge: async, JSON, timeout and deduplication passed');
