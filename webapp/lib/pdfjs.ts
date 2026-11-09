/** Loads pdf.js on demand with its worker pointed at the copy that
 *  `scripts/prepare-assets.mjs` places in `public/`. Three components used to
 *  repeat the import and the worker assignment; the worker path is the one
 *  thing that must agree with the asset step, so it lives here only. */
export async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  return pdfjs;
}
