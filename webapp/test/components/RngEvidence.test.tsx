// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { expect, test } from "vitest";

import { RngEvidence } from "@/app/project/[project]/review/[slug]/evidence/RngEvidence";
import { renderEvidence } from "@/app/project/[project]/review/[slug]/evidence";

const tableIssue = {
  producer: "rng_track",
  inputs: { generator: "numpy_legacy:normal:even", seed: 123, tier: 2, excess_bits: 41.2,
            log10_chance: -12.4, n_values: 12, table: "Table 3", column: "q" },
  reported: { observed_first_values: [0.244759, 0.694755], units: "table values as printed" },
  computed: {
    generated_first_values: [0.244759, 0.694755],
    blocks: [{ offset: 7, n: 12, kind: "ordered", axis: "col", family: "q", loc: 0.5, scale: 0.2,
               rel_resid: 1e-9, excess_bits: 41.2 }],
    replay: "import numpy as np\nnp.random.seed(123)\n",
    table_grid: { label: "Table 3", caption: "True values of μ and q for each arm in simulations.",
                  header_rows: 1, placed: 2,
                  cells: [["arm", "μ", "q"], ["0", "0.070", "0.244759"], ["1", "0.020", "0.694755"]],
                  hit_cells: { "0": [[1, 2], [2, 2]] } },
  },
  notes: "Reproduce with: rngdetect screen …",
};

test("a table hit renders facts, exact value pairs, the shaded grid cells and the replay", () => {
  const { container } = render(<RngEvidence issue={tableIssue} />);
  const text = container.textContent || "";
  expect(text).toMatch(/NumPy legacy/);
  expect(text).toMatch(/all within printed precision/);
  expect(container.querySelectorAll("tr[data-off]").length).toBe(0);
  // Header row is <th>; the two matched cells are shaded, nothing else is.
  const grid = container.querySelector("table.rng-grid")!;
  expect(grid.querySelectorAll("th").length).toBe(3);
  const hit = [...grid.querySelectorAll("[data-hit]")].map((c) => c.textContent);
  expect(hit).toEqual(["0.244759", "0.694755"]);
  expect(text).toMatch(/Table 3: True values/);
  expect(container.querySelector("pre")!.textContent).toMatch(/np\.random\.seed\(123\)/);
  expect(text).toMatch(/Reproduce with/);
});

test("a figure hit flags nothing against a printed step and reports max delta", () => {
  const issue = { producer: "rng_track", inputs: { generator: "r_mt:rnorm", seed: 42, tier: 1, page: 6, n_values: 6349 },
    reported: { observed_first_values: [480.245, 468.135], units: "data units" },
    computed: { generated_first_values: [480.247, 468.137], blocks: [] } };
  const { container } = render(<RngEvidence issue={issue} />);
  expect(container.textContent).toMatch(/max \|Δ\| 0\.002/);
  expect(container.querySelectorAll("tr[data-off]").length).toBe(0);
});

test("the renderer map answers by stored producer and nothing for others", () => {
  expect(renderEvidence({ producer: "tool_expert", inputs: { x: 1 } })).toBeNull();
  expect(renderEvidence({ producer: "rng_track", inputs: { seed: 1 } })).not.toBeNull();
  const { container } = render(<RngEvidence issue={{ producer: "rng_track" }} />);
  expect(container.innerHTML).toBe("");
});
