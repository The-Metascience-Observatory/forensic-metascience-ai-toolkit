-- Public findings site ("Scaling Forensic Metascience"): what may be shown, and what
-- happened to each paper afterwards. The site is built from a snapshot of these
-- tables (publication.py); it never connects to this database.

create table if not exists screening_projects (
  id bigint generated always as identity primary key,
  slug text unique not null,
  title text not null,
  tool text not null,                -- cards are grouped by this later
  description text,
  corpus text,                       -- what was screened, in words
  papers_screened bigint,            -- the denominator; NULL = not recorded
  publish_policy text not null check (publish_policy in ('ai_triaged','human_approved')),
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One row per (project, paper). A tool's exporter fills the content columns and
-- ai_eligible; only a person changes state.
create table if not exists publications (
  id bigint generated always as identity primary key,
  project_id bigint not null references screening_projects(id),
  doi text not null,                 -- lowercased, no resolver prefix
  citation jsonb not null default '{}',
  one_line text,
  summary_md text,
  findings jsonb not null default '[]',
  repo_url text,                     -- set only when the repository is public
  ai_eligible boolean not null default false,
  ai_review jsonb,                   -- {category, model, date}
  state text not null default 'draft' check (state in ('draft','published','withdrawn')),
  decided_by text,
  decided_at timestamptz,
  decision_note text,
  updated_at timestamptz not null default now(),
  unique (project_id, doi)
);

-- The status timeline. Rows are added, never edited; a mistake is voided.
create table if not exists outreach_events (
  id bigint generated always as identity primary key,
  doi text not null,
  project_id bigint references screening_projects(id),  -- NULL = applies to the paper
  kind text not null,                -- TEXT + app validation (publication.KINDS)
  occurred_on date not null,
  url text,
  note text,
  actor text,
  event_uid text unique,             -- for idempotent machine-written events
  voided_at timestamptz,
  recorded_at timestamptz not null default now()
);
create index if not exists outreach_events_doi_idx on outreach_events (doi, occurred_on);
