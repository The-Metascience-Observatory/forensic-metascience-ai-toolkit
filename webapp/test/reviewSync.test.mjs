import { test } from "vitest";
import assert from 'node:assert/strict';
import { ReviewSyncTracker, reviewSyncInterval, reviewSyncCompleted } from '../lib/reviewSync.ts';

// The cadence rules behind the status bar's SWR hook (app/CacheStatus.tsx):
// when a status reading acknowledges a save, and how soon the next read
// follows. The hook's wiring (reads on save and focus, the synced event,
// unmount stopping the poll, offline recovery) is exercised in
// test/components/CacheStatus*.test.tsx against a controlled transport.
test("reviewSync", () => {
  const tracker = new ReviewSyncTracker();
  const reading = (pending, generation = tracker.saves) => ({ state: { pending_writes: pending }, generation });
  // The first reading, before any save, acknowledges nothing.
  assert.equal(tracker.observe(reading(0)), false);
  assert.equal(reviewSyncInterval(reading(0)), 30000);
  // Already synchronized before the first post-save status response.
  tracker.saved(); assert.equal(tracker.observe(reading(0)), true);
  // Delayed: the save shows as pending, polled every five seconds until it drains.
  tracker.saved(); assert.equal(tracker.observe(reading(1)), false);
  assert.equal(reviewSyncInterval(reading(1)), 5000);
  assert.equal(tracker.observe(reading(0)), true);
  assert.equal(reviewSyncInterval(reading(0)), 30000);
  // Saves arriving during a request: the response that was requested before
  // them cannot acknowledge them; the next fresh reading does, once.
  const stale = reading(0);
  tracker.saved(); tracker.saved();
  assert.equal(tracker.observe(stale), false);
  assert.equal(tracker.observe(reading(0)), true);
  assert.equal(tracker.observe(reading(0)), false, 'acknowledged once');
  // Partial batch completion refreshes judgments even with another event pending.
  tracker.saved(); assert.equal(tracker.observe(reading(2)), false);
  assert.equal(tracker.observe(reading(1)), true);
  // Offline keeps the five-second cadence; recovery acknowledges the drained batch.
  assert.equal(reviewSyncInterval(undefined, true), 5000);
  assert.equal(reviewSyncInterval(reading(0), true), 5000);
  assert.equal(tracker.observe(reading(0)), true);
  // Pending writes keep the five-second cadence; a status without a count
  // neither acknowledges nor changes it.
  tracker.saved(); assert.equal(tracker.observe(reading(1)), false);
  assert.equal(reviewSyncInterval(reading(1)), 5000);
  assert.equal(tracker.observe({ state: {}, generation: tracker.saves }), false);
  assert.equal(reviewSyncInterval({ state: {}, generation: tracker.saves }), 30000);
  assert.equal(reviewSyncInterval(undefined), 30000);
  assert.equal(tracker.observe(reading(0)), true);
  assert.equal(reviewSyncCompleted(1, 0), true);
  assert.equal(reviewSyncCompleted(0, 0), false);
  console.log('review sync: immediate/delayed completion, concurrent saves, partial batches, offline and pending cadence passed');
});
