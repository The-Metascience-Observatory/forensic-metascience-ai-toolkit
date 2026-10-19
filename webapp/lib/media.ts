/** Filename and type for `/api/media`. The URL path is `/api/media`, so
 * without Content-Disposition the browser saves the file as `media`. */

const INLINE = new Set([
  ".pdf", ".mp4", ".webm", ".png", ".jpg", ".jpeg", ".gif",
  ".html", ".htm", ".webp",
]);

export const MEDIA_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".xml": "application/xml",
  ".html": "text/html; charset=utf-8",
  ".htm": "text/html; charset=utf-8",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xlsm": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xls": "application/vnd.ms-excel",
  ".csv": "text/csv; charset=utf-8",
  ".tsv": "text/tab-separated-values; charset=utf-8",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

export function mediaBasename(rel: string): string {
  const parts = String(rel || "").replace(/\\/g, "/").split("/");
  const last = parts[parts.length - 1] || "";
  const cleaned = last.replace(/[\x00-\x1f\x7f"]/g, "_").trim();
  return cleaned || "file";
}

export function mediaExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export function mediaType(name: string): string {
  return MEDIA_TYPES[mediaExt(name)] || "application/octet-stream";
}

export function mediaDisposition(rel: string, forceDownload = false): string {
  const name = mediaBasename(rel);
  const ext = mediaExt(name);
  const kind = forceDownload || !INLINE.has(ext) ? "attachment" : "inline";
  const ascii = name.replace(/[^\x20-\x7e]/g, "_") || "file";
  const encoded = encodeURIComponent(name).replace(/['()]/g, (c) =>
    `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
  return `${kind}; filename="${ascii}"; filename*=UTF-8''${encoded}`;
}

/** `__runs/<run>/<artifact>` names one sealed archive object, verified against
 *  its recorded sha256 on every resolve, so its bytes never change: the
 *  browser may keep it. A thumbnail of one is derived by a versioned renderer
 *  and kept a day. Paper-relative files can change in place and are always
 *  revalidated (ETag / Last-Modified). */
export function cacheControl(file: string, variant: string | null) {
  if (!/^__runs\/[^/]+\/[^/]+$/.test(file)) return "private, no-cache";
  return variant === "thumbnail" ? "private, max-age=86400" : "private, max-age=31536000, immutable";
}
