import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Worktrees may share node_modules without ever running postinstall locally.
// Refresh the worker from the same installed PDF.js version as the viewer.
export function prepareAssets(root = process.cwd()) {
  const candidates = ['build', 'legacy/build'].map(dir =>
    path.join(root, 'node_modules/pdfjs-dist', dir, 'pdf.worker.min.mjs'));
  const source = candidates.find(file => fs.existsSync(file));
  if (!source) throw new Error('PDF.js worker is missing. Run npm install in webapp.');
  const target = path.join(root, 'public/pdf.worker.min.mjs');
  const bytes = fs.readFileSync(source);
  if (fs.existsSync(target) && fs.readFileSync(target).equals(bytes)) return target;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.tmp`;
  try {
    fs.writeFileSync(temporary, bytes);
    fs.renameSync(temporary, target);
  } finally { fs.rmSync(temporary, { force: true }); }
  return target;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  prepareAssets();
}
