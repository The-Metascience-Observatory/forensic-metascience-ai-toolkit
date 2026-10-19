import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { prepareAssets } from '../scripts/prepare-assets.mjs';
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pdf-assets-'));
try {
  assert.throws(() => prepareAssets(root), /Run npm install/);
  const dependency = path.join(root, 'node_modules/pdfjs-dist/build');
  fs.mkdirSync(dependency, { recursive: true });
  const source = path.join(dependency, 'pdf.worker.min.mjs');
  fs.writeFileSync(source, 'worker version 1');
  const target = prepareAssets(root);
  assert.equal(fs.readFileSync(target,'utf8'), 'worker version 1');
  fs.writeFileSync(source, 'worker version 2');
  prepareAssets(root);
  assert.equal(fs.readFileSync(target,'utf8'), 'worker version 2');
  const before = fs.statSync(target).mtimeMs;
  prepareAssets(root);
  assert.equal(fs.statSync(target).mtimeMs, before);
  assert.match(fs.readFileSync('scripts/serve.mjs','utf8'), /prepareAssets\(\);/);
  console.log('PDF assets: missing dependency, fresh worktree, upgrade and repeat startup passed');
} finally { fs.rmSync(root, { recursive: true, force: true }); }
