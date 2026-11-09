/** PNG export: a canvas to a PNG blob, and a blob to a download. */

export const toBlob = (canvas: HTMLCanvasElement) => new Promise<Blob>((resolve, reject) =>
  canvas.toBlob(b => b ? resolve(b) : reject(new Error("PNG encoding failed")), "image/png"));


export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
