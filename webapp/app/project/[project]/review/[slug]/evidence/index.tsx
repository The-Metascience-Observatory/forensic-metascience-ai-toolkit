import type { Issue } from "@/lib/types/review";
import type { ReactNode } from "react";

import { RngEvidence } from "./RngEvidence";

/** Evidence renderers keyed by STORED producer value. A separately
 *  distributed detector's rows carry evidence the generic card cannot show
 *  (an RNG match's values and replay; later a spectra trace or a copy-paste
 *  cell map); each registers one renderer here. Unknown producers render
 *  nothing extra. The stored value never changes (it is hashed into finding
 *  ids), so this map is stable across display-name changes. */
export const EVIDENCE_RENDERERS: Record<string, (issue: Issue) => ReactNode> = {
  rng_track: (issue) => <RngEvidence issue={issue} />,
};

export function renderEvidence(issue: Issue): ReactNode {
  const render = issue?.producer ? EVIDENCE_RENDERERS[issue.producer] : undefined;
  return render ? render(issue) : null;
}
