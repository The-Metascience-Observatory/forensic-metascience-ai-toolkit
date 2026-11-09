import { test } from "vitest";
import assert from 'node:assert/strict';
import { DECISIONS_BY_PRODUCER, IMAGE_DECISIONS, NUMERIC_DECISIONS, RNG_DECISIONS,
         decisionsFor } from '../lib/constants.gen.ts';
import { COLS_BY_PRODUCER, IMAGE_COLS, NUMERIC_COLS, RNG_COLS, columnKeys,
         decisionColumnsFor, vocabularies } from '../lib/decisions.ts';

test("decisions", async () => {
  // Every layout offers exactly its generated vocabulary: a decision added in
  // review_io.py without a button here, or a button the service would refuse,
  // fails this file.
  const same = (a, b) => assert.deepEqual([...a].sort(), [...b].sort());
  same(columnKeys(NUMERIC_COLS), NUMERIC_DECISIONS);
  same(columnKeys(IMAGE_COLS), IMAGE_DECISIONS);
  same(columnKeys(RNG_COLS), RNG_DECISIONS);
  for (const [producer, decisions] of Object.entries(DECISIONS_BY_PRODUCER)) {
    assert.ok(COLS_BY_PRODUCER[producer], `${producer} declares a vocabulary but has no layout`);
    same(columnKeys(COLS_BY_PRODUCER[producer]), decisions);
  }
  for (const v of vocabularies()) same(columnKeys(v.cols), v.decisions);
  // No layout repeats a key.
  for (const cols of [NUMERIC_COLS, IMAGE_COLS, RNG_COLS]) {
    assert.equal(new Set(columnKeys(cols)).size, columnKeys(cols).length);
  }
  // Chosen by producer first, then by kind -- the same rule as the generated
  // `decisionsFor` and Python's `review_io.decisions_for`.
  assert.equal(decisionColumnsFor({ kind: 'numeric', producer: 'rng_track' }), RNG_COLS);
  assert.equal(decisionColumnsFor({ kind: 'numeric', producer: 'tool_expert' }), NUMERIC_COLS);
  assert.equal(decisionColumnsFor({ kind: 'image', producer: 'image_forensics' }), IMAGE_COLS);
  assert.equal(decisionColumnsFor({ kind: 'numeric' }), NUMERIC_COLS);
  same(decisionsFor('numeric', 'rng_track'), RNG_DECISIONS);
  same(decisionsFor('image', null), IMAGE_DECISIONS);
  same(decisionsFor(null, undefined), NUMERIC_DECISIONS);
  console.log('decisions ok');
});
