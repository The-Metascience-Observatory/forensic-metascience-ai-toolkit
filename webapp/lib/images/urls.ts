/** URLs of the image review: media, item, queue and paper pages. Pure; split out of `app/images/lib.ts`, which re-exports it. */
import { mediaUrl as buildMediaUrl } from "@/lib/mediaUrl";

/** Image-track media: `lib/mediaUrl` with this track as the default component. */
export function mediaUrl(project: string, dir: string, rel: string, component = "image_forensics"): string {
  return buildMediaUrl(project, dir, rel, component);
}

export function itemHref(project: string, id: string, run = "latest"): string {
  return `/project/${encodeURIComponent(project)}/images/${encodeURIComponent(id)}?run=${encodeURIComponent(run)}`;
}

export function queueHref(project: string, run = "latest"): string {
  return `/project/${encodeURIComponent(project)}/images?run=${encodeURIComponent(run)}`;
}

export function paperHref(project: string, dir: string, run: string = "latest"): string {
  return `/project/${encodeURIComponent(project)}/review/${encodeURIComponent(dir.split("/").pop() || dir)}?dir=${encodeURIComponent(dir)}&run=${encodeURIComponent(run)}`;
}
