/** The review page's payloads, as the workbench service returns them.
 *
 *  An `Issue` is one row of `review_issues._v2_issues_from_doc` (plus what the
 *  service adds: `detail_key`, `detail_loaded`, `reviews`, `pipeline`,
 *  `location_basis`, and the detail read's `anchors`, `inputs`, `notes`,
 *  `reported`, `computed`). A summary row lacks the detail fields, so they are
 *  optional. Fields the service may add later stay reachable through the index
 *  signature as `unknown`, never as `any`. */

export type ReviewEvent = {
  event_id?: string;
  run_id?: string;
  item?: string;
  decision?: string | null;
  /** Never empty: `repository.save_review` refuses a decision without one. */
  reviewer: string;
  at?: string | null;
  note?: string | null;
  extra?: Record<string, unknown> | null;
  pending?: boolean;
};

/** `repository.judgments`: every reviewer's latest event, the history, and
 *  the agreed decision (null when reviewers disagree). */
export type Judgments = {
  reviewers?: ReviewEvent[];
  history?: ReviewEvent[];
  conflict?: boolean;
  decision?: ReviewEvent | null;
};

/** `finding_groups._meta`: one tool family in one place. */
export type IssueGroup = {
  id: string;
  family?: string;
  tool?: string;
  unit?: string;
  n?: number;
  severity_9?: number | null;
  [key: string]: unknown;
};

/** A file a finding names (spreadsheet, supplementary PDF, exhibit). */
export type Artefact = {
  kind?: string;
  basename?: string;
  relpath?: string;
  sheet?: string | null;
  cells?: unknown[];
  found?: boolean;
  confidence?: string;
  [key: string]: unknown;
};

export type Passage = { id: string; quote: string; role?: string | null; label?: string | null };

export type Issue = {
  id: string;
  kind: string;
  title: string;
  source_id?: string;
  run?: string;
  plain?: string;
  severity?: string | null;
  severity_9?: number | null;
  severity_is_provisional?: boolean;
  impossible?: boolean;
  quarantined?: boolean;
  quarantine_reason?: string | null;
  adjudication_action?: string | null;
  adjudication_rationale?: string | null;
  technique?: string | null;
  producer?: string | null;
  tool?: string | null;
  tool_source?: string;
  location?: string | null;
  quote?: string;
  quote_verified?: unknown;
  reported?: Record<string, unknown> | null;
  computed?: Record<string, unknown> | null;
  consequence?: unknown;
  priority?: number;
  passages?: Passage[];
  artefacts?: Artefact[];
  extras?: Record<string, unknown>;
  anchors?: Record<string, unknown>[];
  inputs?: Record<string, unknown> | null;
  notes?: string | null;
  group?: IssueGroup | null;
  detail_key?: number | string;
  detail_loaded?: boolean;
  reviews?: Judgments;
  component_item?: string;
  [key: string]: unknown;
};

/** The saved review of one issue (`review_io` issue record). */
export type IssueReview = {
  decision?: string | null;
  note?: string;
  reviewer?: string;
  at?: string;
  submitted_to_pubpeer?: boolean;
  submitted_to_editor?: boolean;
  pubpeer_url?: string | null;
  [key: string]: unknown;
};

/** The paper's review as the page holds it: per-issue records and the
 *  paper-level fields (status, PubPeer flags). */
export type ReviewState = { issues: Record<string, IssueReview>; paper: Record<string, unknown> };

/** What the source pane draws (`extraction/xml_html.article_view` + media). */
export type Article = {
  mode?: string;
  warning?: string | null;
  pdf_relpath?: string | null;
  xml_relpath?: string | null;
  has_pdf?: boolean;
  has_xml?: boolean;
  html?: string | null;
  title?: string | null;
  doi?: string | null;
  doi_url?: string | null;
  figures?: unknown[];
  [key: string]: unknown;
};

/** A registered local root (`catalog.roots`). */
export type Root = { project: string; path: string; available?: boolean };
