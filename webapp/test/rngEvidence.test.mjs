import { test } from "vitest";
import assert from 'node:assert/strict';
import { decimals, printedPrecision, valuePairs, generatorLabel, inputFacts,
         hitCellIndex, valuesArePrinted, maxDelta } from '../lib/rngEvidence.ts';

test("rngEvidence", async () => {
  assert.equal(decimals(0.2447), 4);
  assert.equal(decimals(12), 0);
  assert.equal(decimals(1e-7), 7);
  assert.equal(decimals(1.5e-7), 8);
  assert.equal(printedPrecision([0.24, 0.2447, 1]), 1e-4);
  assert.equal(printedPrecision([]), 1);

  // A reproduction within half the printed step is a match; beyond it is flagged.
  const pairs = valuePairs([0.2447, 0.5000, 0.9], [0.24471, 0.5006, 0.9]);
  assert.deepEqual(pairs.map((p) => p.off), [false, true, false]);
  assert.equal(pairs.length, 3);
  // The common prefix only: a longer generated list adds no phantom rows.
  assert.equal(valuePairs([1, 2], [1, 2, 3, 4]).length, 2);
  assert.equal(valuePairs(null, undefined).length, 0);
  // Non-numeric input is flagged, never silently zero.
  assert.equal(valuePairs(['x'], [1])[0].off, true);

  assert.equal(generatorLabel('numpy_legacy:normal:even'),
               'NumPy legacy (np.random.seed / RandomState) · normal · even');
  assert.equal(generatorLabel('unknown_family'), 'unknown_family');
  assert.equal(generatorLabel(null), '');

  const facts = inputFacts({ generator: 'r_mt:runif', seed: 123, tier: 1,
                             excess_bits: 2960.84, log10_chance: -891.33, n_values: 6349 });
  assert.deepEqual(facts.map(([k]) => k),
    ['generator', 'seed', 'values matched', 'tier', 'excess bits', 'log10 chance matches']);
  assert.equal(facts.find(([k]) => k === 'excess bits')[1], '2960.8');
  assert.deepEqual(inputFacts(null), []);
  // An unrecorded fact is absent, not "undefined" or "0".
  assert.ok(!inputFacts({ seed: 42 }).some(([, v]) => v === 'undefined' || v === 'null'));

  const idx = hitCellIndex({ cells: [[]], hit_cells: { 0: [[2, 1], null, [3, 1]], 1: [[5, 2]] } });
  assert.equal(idx.get('2,1'), 0);
  assert.equal(idx.get('3,1'), 0);
  assert.equal(idx.get('5,2'), 1);
  assert.equal(idx.has('9,9'), false);
  assert.equal(hitCellIndex(null).size, 0);
  // Coordinates measured off a figure have no printed step: never flagged, max |Δ| reported.
  const measured = valuePairs([480.245, 468.135], [480.247, 468.137], { printed: false });
  assert.deepEqual(measured.map((p) => p.off), [false, false]);
  assert.ok(Math.abs(maxDelta(measured) - 0.002) < 1e-9);
  assert.equal(maxDelta([]), null);
  assert.equal(valuesArePrinted({ page: 6 }, 'data units'), false);
  assert.equal(valuesArePrinted({ table: 'Table 2' }, 'data units'), true);
  assert.equal(valuesArePrinted(null, 'table values as printed'), true);
  assert.equal(valuesArePrinted(null, null), true);
  console.log('rngEvidence ok');
});
