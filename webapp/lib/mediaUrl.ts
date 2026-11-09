/** The one builder for `/api/media` URLs.
 *
 *  Four copies of this string used to exist (the image library, the source
 *  pane, the spreadsheet pane, the video thumbnail). `component` names the
 *  owning track for image and copy-paste media and is omitted for the
 *  paper's own files, which the service resolves under the review; `download`
 *  asks the route for an attachment disposition. */
export function mediaUrl(
  project: string, dir: string, rel: string,
  component?: string | null, options: { download?: boolean } = {},
): string {
  const q = new URLSearchParams();
  if (component) q.set("component", component);
  q.set("project", project);
  q.set("dir", dir);
  q.set("f", rel);
  if (options.download) q.set("download", "1");
  return `/api/media?${q}`;
}
