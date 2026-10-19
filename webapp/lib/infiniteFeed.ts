import type { Feed } from '../app/images/lib';

/** Keep every appended page in one repository revision, including after reviews.
 *
 * A revision change mid-pagination used to be a hard error, and the reviewer
 * saw it as "Results changed while loading. Please retry." -- which is exactly
 * what a burst of review writes causes, because every saved decision bumps the
 * revision by design. MEASURED 2026-09-12: ~95 decisions a minute for twenty
 * minutes while 39 pages were loaded, so a refresh spanning more than one page
 * could hardly avoid it. The guard is right that pages from two revisions must
 * not be mixed; the right response is to RETAKE THE SNAPSHOT, not to hand the
 * reviewer an error in the middle of their own work. It still refuses after
 * `ATTEMPTS` tries, so a queue that is genuinely churning faster than it can be
 * paged says so rather than looping.
 */
const ATTEMPTS = 3;

export async function queuePages(
  previous: Feed[], mode: 'refresh' | 'more', fetchPage: (offset: number) => Promise<Feed>,
): Promise<Feed[]> {
  const sameRevision = (a: Feed, b: Feed) => !!a.revision && a.revision === b.revision;
  if (mode === 'more' && previous.length) {
    const offset = previous[previous.length - 1].pagination?.next_offset;
    if (offset == null) return previous;
    const next = await fetchPage(offset);
    if (sameRevision(previous[0], next)) return [...previous, next];
  }
  const wanted = Math.max(1, previous.length + (mode === 'more' ? 1 : 0));
  for (let attempt = 1; ; attempt++) {
    const first = await fetchPage(0);
    if (mode === 'refresh' && previous.length && sameRevision(previous[0], first)) {
      return [first, ...previous.slice(1)];
    }
    const pages = [first];
    let stale = false;
    while (pages.length < wanted) {
      const offset = pages[pages.length - 1].pagination?.next_offset;
      if (offset == null) break;
      const next = await fetchPage(offset);
      if (!sameRevision(first, next)) { stale = true; break; }
      pages.push(next);
    }
    if (!stale) return pages;
    if (attempt >= ATTEMPTS) {
      throw new Error('Results changed while loading. Please retry.');
    }
  }
}
