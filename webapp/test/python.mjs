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
    ['metascience_agent', 'copy_paste_detector', 'metascience_observatory_image_analysis']}))
`);
  process.env.PYTHONPATH = scratch;
  // The inherited path must survive too: this module exists only there.
  const found = await pyModuleJson('checkout_probe', []);
  const repo = path.resolve(process.cwd(), '..');
  for (const [name, folder] of Object.entries({metascience_agent: 'src',
    copy_paste_detector: 'copy_paste_detector/src'})) {
    assert.equal(found[name], path.join(repo, folder, name, '__init__.py'));
  }
  // The image package is its own repository, checked out beside the toolkit
  // and optional. Where the sibling checkout exists, it must win over any
  // installed copy; elsewhere (a worktree, a plugin-less machine) the bridge
  // has nothing of its own to assert.
  const image = 'metascience_observatory_image_analysis';
  const sibling = path.join(repo, '..', 'metascience-observatory-image-analysis', 'src', image, '__init__.py');
  if (fs.existsSync(sibling)) assert.equal(found[image], sibling);
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
