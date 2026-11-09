/** Records of the image review system (queue rows, panels, feeds, filters),
 *  as the workbench service returns them. Types only, so lib/ modules and
 *  app/ components share one definition without lib/ importing app/.
 *  `app/images/lib.ts` re-exports every name for its existing importers. */
import type { LatestInfo, RunOption } from "./runs";

export type Subfigure = { status: string; raw?: string | null; normalized?: string | null };

export type Placement = { page: number; bbox: number[] | null; figure_label?: string | null;
  document_path?: string; document_id?: string; bbox_kind?: string;
  transform?: number[]; parent_size?: number[]; page_size?: number[]; page_rotation?: number; subfigure?: Subfigure; geometry_gap?: string;
  /** Set when the geometry came from `panels/panel_identity.json` rather than the live PDF. */
  identity_source?: string; occurrence_id?: string | null };

export type Rendition = { rendition_id?: string | null; source?: string | null; file?: string | null;
  width?: number | null; height?: number | null; provenance?: string | null; passthrough?: boolean | null;
  link?: string | null; framing?: string | null; n_inliers?: number | null; detail?: string };

/** `state` is "current", "stale:<why>" or "absent" ("absent" means the ledger
 *  verb has not run, which is not "the PDF is the only copy"). */
export type FigureSources = { state: string;
  best_pixels?: { rendition_id?: string | null; source?: string | null; file?: string | null;
                  width?: number | null; height?: number | null } | string | null;
  best_pixels_reason?: string | null; links?: Record<string, number>; renditions?: Rendition[] };

/** The identity sidecar's state for this panel's document: present only when
 *  a sidecar file exists (`usable` / `stale` / `no_record` / `unreadable`). */
export type IdentitySidecar = { status: string; reason?: string | null; path?: string };

export type Panel = {
  uid: string;
  crop_box?: number[] | null;
  paper_dir: string;
  paper_path?: string;
  image: string | null;
  placements: Placement[];
  figure_label: string | null;
  caption_key: string | null;
  caption: string | null;
  caption_source?: string | null;
  image_unavailable_reason?: string | null;
  image_recovery?: { method: string; run_id: string };
  document?: { id: string; path: string; role: string; status: string };
  subfigure?: Subfigure;
  caption_warnings?: string[];
  caption_locator?: { path?: string; page?: number };
  identity_gaps?: string[];
  identity_sidecar?: IdentitySidecar;
  /** The figure source ledger's view of this panel's figure (image_review `_figure_sources_for`). */
  figure_sources?: FigureSources;
  /** The parent figure's PNG (relative to the paper), for a crop or a native
   *  publisher/SI figure with no PDF placement. Set by `evidence.enrich_panel`. */
  parent_image?: string | null;
  panel_readings?: { page: number | null; subfigure_raw: string | null; status: string; context_text: string }[];
};

export type PaneTarget = { id: string; kind: string; label: string; page: number;
  boxes: { page: number; x0: number; y0: number; x1: number; y1: number; tid?: string }[];
  confidence: string; method?: string; paper_dir?: string; document_path?: string };

/** What `PdfPane` is told to open. `method` is what makes a page-only image
 *  placement read "Figure on p. N" rather than the numeric-token sentence:
 *  `_targets` emits it, and a feed cached before it did gets it inferred
 *  from the target kind. */
export type PaneLocator = { page: number; confidence: string; method?: string; targets: PaneTarget[] };

export type PaneDocument =
  | { kind: "pdf"; path: string; substituted: boolean }
  | { kind: "native"; path: string | null; reason: string }
  | { kind: "none"; reason: string };

export type PaperHead = {
  pubpeer_url?: string | null;
  dir: string; path?: string; doi?: string | null; title?: string | null;
  journal?: string | null; year?: number | string | null; pdf?: string | null;
  authors?: string | null; volume?: string | null; issue?: string | null; pages?: string | null;
};

export type Decision = {
  decision: string; reviewer?: string; at?: string; note?: string; pending?: boolean;
};

export type ContentSupportData = {
  status: string; note?: string; reason?: string; limitations?: string[];
  saved_support?: {tentative_pairs:number; supporting_pairs:number; eligible_supporting_pairs:number};
  independent_masked_fit?: {status:string; inliers:number|null; tentative_pairs:number};
  agreement?: {original_agree_px:number; eligible_overlap_px:number; overlap_px:number; closing_added_px:number};
  panels?: {mask?: {eligible_px:number; total_px:number; excluded_px:number; note:string; text:{status:string; engine?:string; reason?:string}};
    segmentation?: {reason:string; cells:{row:number;column:number;box:number[]}[]}}[];
  cell_pairs?: {a:number;b:number;supporting_pairs:number;eligible_supporting_pairs:number}[];
  artifacts?: {role:string;side:string;sha256:string;ref:string;cell?:number}[];
};

export type Item = {
  requested_item_id?: string;
  /** Whether the archived panel pixels resolve on this computer (queue rows). */
  evidence?: "available" | "missing" | "unknown";
  /** Publication year from the queue's indexed column (null when unknown). */
  year?: number | null;
  text_label_context?: boolean;
  review_conflict?: boolean;
  record_revision?: string;
  content_support?: ContentSupportData;
  reviews?: {conflict?:boolean;reviewers?:any[];history?:any[]};
  screening_attempts?: unknown[];
  run_status?: string;
  coverage_status?: string;
  region_measurements?: Record<string, unknown>;
  legacy_decision_context?: unknown;
  prior_decisions?: unknown[];

  id: string;
  run_id: string; execution_id: string; provenance?: {version?:string}; publication_status?:string; evidence_source?:string;
  kind: "within" | "cross";
  source_id: string;
  paper: PaperHead;
  papers: PaperHead[];
  group_index: number | null;
  detector_kind: string;
  sentence: string;
  figure_labels: string[];
  spans_figures: boolean;
  /** `match_regions.figure_span`, computed by the service for every queue row. */
  figure_span?: FigureSpan;
  direction?: { later?: string; basis?: string } | null;
  captions: Record<string, { caption: string; source?: string; paper?: string }>;
  panels: Panel[];
  targets: PaneTarget[];
  /** Compact queue rows omit geometry; details load it for the selected run.
   * Missing measurements must never imply a measured empty region. */
  measurements?: Record<string, unknown> | null;
  /** Match-box area divided by each compared panel's area; absent is unmeasured. */
  region_coverage?: {a: number; b: number} | null;
  adjudication: { verdict?: string; category?: string; explanation?: string; confidence?: string } | null;
  screening_status?: string; scientific_disposition?: string | null; eligibility_detail?: string;
  screening?: { decision: string; confidence: string; validated: boolean; policy: string;
    explanation?: string; evidence_quote?: string; validation_errors?: string[];
    panel_readings?: {uid:string;page:number|null;subfigure_raw:string|null;status:string;context_text:string}[] };
  cleared: boolean;
  rank: { score: number; reasons: string[]; verdict?: string | null; category?: string | null;
          lookalike?: boolean };
  exhibit: string | null;
  video: string | null;
  video_revision?: string | null;
  video_generation?: VideoJob;
  exhibit_gate?: string | null;
  decision: Decision | null;
};

export type SpotCheck = { seed: string; per_kind: number;
  strata: Record<string, { population: number; sampled: number; right: number; wrong: number }> };

export type Feed = {
  revision?: string;
  spot_check?: SpotCheck;
  evidence_counts?: { value: string; count: number }[];
  pagination?: {offset:number;limit:number;total:number;next_offset:number|null};
  kinds?: { value: string; count: number }[];
  adjudicator_outputs?: { value: string; count: number }[];
  image_types?: { value: string; count: number }[];
  /** How many of the run's items the unaligned control demoted as lookalikes. */
  lookalike_counts?: { value: string; count: number }[];
  /** Items per figure span, GIVEN the other filters. */
  figure_span_counts?: { value: string; count: number }[];
  match_region_counts?: { value: string; count: number }[];
  /** Totals for the kind select's own "all" and "cross" options, on the same
   *  base as every other facet: the items passing all OTHER filters. `counts`
   *  stays whole-run, because it feeds the run summary line. */
  facet_totals?: { kind?: number; kind_cross?: number };
  empty_reason?: string | null;
  project: string; built_at: string; seconds: number;
  counts: Record<string, number>; items: Item[]; notes: string[];
  judgment_counts?: Record<string, number>;
  selection?: string; runs?: RunOption[]; coverage?: {runs:number;states:Record<string,number>};
  latest_info?: LatestInfo;
  refresh_needed?: boolean; refresh_error?: string;
  screening_progress?: { candidates: number; awaiting_review: number };
};

export type FigureSpan = "different_figures" | "same_figure" | "different_papers" | "unknown";

export type Filter = { text_context?: "exclude" | "include" | "only"; verdict: "unexplained" | "standing" | "all" | "unscreened" | "cleared"; kind: string;
                       /** The typer's class for the item: Blots, Graphs, Microscopy, Body Imaging,
                        *  Flow Cytometry, or `mixed` / `untyped`. "all" disables the filter. */
                       image_type?: string;
                       /** A LOOKALIKE is a group the unaligned control MEASURED and
                        *  failed: the two panels agree about as well unaligned as
                        *  aligned, so the agreement is not specific to the transform --
                        *  generic resemblance rather than shared pixels. Also set for a
                        *  single channel matched to a merge containing it across two
                        *  figures. It never changes the score, only the order, and a
                        *  group whose control was never measured is NOT one: absence of
                        *  a measurement is not a failed measurement. "all" disables. */
                       lookalike?: "all" | "yes" | "no";
                       match_region?: "all" | "partial_both" | "partial_one" | "large_both" | "unknown";
                       region_max_percent?: number;
                       transformation?: "all" | "any_suspicious" | "translation" | "rotation" | "resizing" | "reflection" | "combined" | "unknown";
                       coverage?: "all" | "incomplete" | "unknown";
                       /** Whether the item's placements name two different figures of one
                        *  paper (`different_figures`), one figure (`same_figure`), another
                        *  paper (`different_papers`), or cannot say because a label is
                        *  missing (`unknown`). "all" disables the filter. */
                       figure_span?: "all" | FigureSpan;
                       /** Case-insensitive substring of the paper folder shown in the Paper column. */
                       q?: string;
                       /** Queue order. Default is the triage rule (`triage_rank.sort_key`:
                        *  cleared and measured lookalikes last, then verdict tier, score,
                        *  inliers); `score` is the bare rank score. `paper` is the folder
                        *  column; `decision` groups by human decision, undecided last. */
                       sort?: QueueSort;
                       direction?: "asc" | "desc";
                       /** Spot-check mode: a seeded, stratified sample of the detector's own
                        *  context demotions (e.g. chart_furniture), per kind. Empty = off. */
                       spot_check?: string;
                       /** Whether the item's archived panel pixels resolve on this computer. */
                       evidence?: "all" | "available" | "missing" | "unknown";
                       undecided: boolean; adjudicator?: string; judgments?: string[] };

export type QueueSort = "triage" | "score" | "paper" | "decision" | "year";

export type VideoJob = {
  status: "idle" | "queued" | "running" | "ready" | "failed";
  can_generate: boolean;
  reason?: string | null;
  error?: string | null;
  video?: string | null;
  thumbnail?: string | null;
  revision?: string;
};
