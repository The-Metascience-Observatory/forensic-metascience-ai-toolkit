/** The legacy index snapshot (`webapp/data/index.json`, `metascience
 *  webapp-index`): projects, corpora and paper rows. Types only, importable
 *  from client components; the reader is the server module lib/store.ts. */

export interface ProjectRow {
  name: string;
  root: string;
  n_papers: number;
  n_pdf: number;
  n_xml: number;
  n_agent_run: number;
  n_image_run: number;
  n_image_discarded?: number;
  n_image_refused?: number;
  n_text_run: number;
  n_human_reviewed: number;
  n_viewed?: number;
  n_viewed_unknown?: number;
  n_in_progress: number;
  n_not_fetched: number;
  n_pubpeer?: number;
  n_pubpeer_image?: number;
  n_submitted_pubpeer?: number;
  corpus: Corpus;
}

export interface Index {
  schema_version: string;
  papers_root: string;
  projects: ProjectRow[];
  n_projects: number;
  n_papers: number;
  errors?: { path: string; error: string }[];
}

export interface Corpus {
  schema_version: string;
  root: string;
  papers: Paper[];
  errors: { path: string; error: string }[];
  totals: Record<string, unknown>;
}

export interface Paper {
  paper_id: string;
  dir: string;
  doi: string | null;
  title: string | null;
  authors: string | null;
  first_author: string | null;
  journal: string | null;
  volume: string | null;
  issue: string | null;
  year: string | number | null;
  identity_source?: string;
  channels: Record<string, { state: string; detail?: string }>;
  n_runs: number;
  runs: { name: string; status: string; verdict: string | null;
          n_findings: number;
          n_non_image_findings?: number | null;
          pipeline_version?: string | null;
          analysed_at?: string | null }[];
  latest_run: string | null;
  analysed_at?: string | null;
  analysed_at_source?: "recorded" | "file_mtime" | null;
  verdict: string | null;
  worst_severity_9?: number | null;
  n_findings: number | null;
  // Absent (not 0) on an index written before this field existed -- the table
  // shows a dash and says to rescan, rather than passing the total off as the
  // non-image count.
  n_non_image_findings?: number | null;
  /** Standing groups the image adjudicator left unexplained or never
   *  judged. `insufficient_evidence` survivors are counted SEPARATELY in
   *  n_image_undecided — still standing, but not what the LLM called
   *  suspicious, and folding them in is what made this column read 834
   *  where 344 was the truth (2026-09-08). */
  image_status?: string;
  n_image_findings?: number | null;
  n_image_undecided?: number | null;
  /** Findings of the seeded-RNG detector's own run (`rng_track`); absent or
   *  null when no RNG screen covered the paper (shown as a dash, not 0). */
  n_rng_findings?: number | null;
  /** Release that produced the latest run (run_meta.json `version`). */
  pipeline_version?: string | null;
  /** Has anyone OPENED this paper's review page? Absent on an index written
   *  before view tracking — which is neither "no" nor "unknown", it is a
   *  question this index was never asked. `viewed: null` with
   *  `source: "unreadable"` IS unknown: the record exists and could not be
   *  read. */
  viewed?: {
    viewed: boolean | null;
    n_views: number | null;
    first_at: string | null;
    last_at: string | null;
    viewers: (string | null)[];
    source: "recorded" | "inferred_from_review" | "none" | "unreadable";
  };
  review: {
    reviewed: boolean;
    paper_status?: string;
    reviewed_by?: string | null;
    reviewed_at?: string | null;
    n_decisions: number;
    submitted_to_pubpeer?: boolean | null;
    pubpeer_url?: string | null;
    pubpeer_note?: string | null;
  };
  sources: {
    state: string;
    pdf: boolean;
    xml: boolean;
    body_md: boolean;
    landing_page_only: boolean;
    /** Page count of the largest PDF, measured only when an XML is also
     *  held; null/absent = unknown (no fitz), never a claim. */
    main_pdf_pages?: number | null;
    /** ≤2-page PDF beside a full-text XML: a publisher preview stub, not
     *  the paper — image checks were effectively figure-blind. */
    pdf_suspect_stub?: boolean;
  };
  evidence: { path: string | null; is_video?: boolean }[];
  pubpeer?: {
    has_entry: boolean;
    is_image_integrity: boolean;
    figures: string[];
    n_comments: number;
    url?: string | null;
  } | null;
}
