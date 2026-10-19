import type { Panel } from '../app/images/lib.ts';

export type XmlFigure = {
  id: string; anchor: string; label: string; caption: string;
  graphics: { reference: string; relpath: string | null; status: string }[];
};

/** The paper-relative file a PMC or publisher render panel was cut from,
 *  read from its retained uid (`pmc_figures:pmc:<file>[-segN|-visibleN]`). */
export function nativeSource(uid: string): { folder: string; file: string } | null {
  const m = uid.match(/^(pmc_figures:pmc:|publisher_figures:pub:)(.+?)(?:-(?:seg|visible)\d+)?$/);
  return m ? { folder: m[1].split(':')[0], file: m[2] } : null;
}

/** Match source identity, never a collapsed display label (e.g. Extended Data). */
export function panelFigure(panel: Panel, figures: XmlFigure[]): XmlFigure | undefined {
  const paths = [panel.parent_image, panel.image].filter((p): p is string => Boolean(p));
  const native = nativeSource(panel.uid);
  if (native) paths.push(`${native.folder}/${native.file}`);
  const exact = figures.filter(f => f.graphics.some(g => g.relpath && paths.includes(g.relpath)));
  if (exact.length === 1) return exact[0];
  // Retained panel UIDs preserve the source filename even when media paths are
  // archive object references or generated crops. Match the complete token.
  const byUid = figures.filter(f => f.graphics.some(g => {
    const name = g.reference.split('/').pop();
    if (!name) return false;
    return panel.uid.endsWith(`:${name}`) || panel.uid.includes(`:${name}-seg`);
  }));
  return byUid.length === 1 ? byUid[0] : undefined;
}

export function canReadXml(panel: Panel): boolean {
  return ['main', 'unknown', 'pmc_render', 'publisher_render'].includes(panel.document?.role || 'unknown');
}
