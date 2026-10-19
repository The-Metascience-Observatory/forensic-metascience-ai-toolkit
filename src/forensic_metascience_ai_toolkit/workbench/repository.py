"""Pure projections over synchronized summaries. No scans or network in list reads."""
from __future__ import annotations

from .timing import timed

import json
import threading
import weakref
from collections import Counter
import uuid
from pathlib import Path
from .catalog import now  # noqa: F401 -- re-exported
from forensic_metascience_ai_toolkit.workbench.common import (  # noqa: F401 -- re-exported
    component, db_primary_key, page)
from forensic_metascience_ai_toolkit.workbench.queue_fields import (  # noqa: F401 -- re-exported
    _folder_search_forms, adjudicator_output, judgment_decision, matches_paper_folder,
    paper_column, run_time, sort_feed_items)
from .image_mixins import SharedImageQueueMixin


class Repository(SharedImageQueueMixin):
    """The shared projection. Image items and the shared-storage image queue
    (`item_view`, `feed`, `local_video_items`) come from the image package's
    `SharedImageQueueMixin`."""
    def __init__(self, catalog, *, videos=None):
        self.catalog = catalog
        self.videos = videos
        self.version = -1

    #: The projection attributes that are pure functions of (catalog
    #: generation, scope) and are never written to after the load. They are
    #: SHARED between workers; `paper_pages` and `feed_pages` are excluded
    #: because they are per-worker caches that get mutated.
    _SHARED_KEYS = ('data','corpora','papers','runs','by_uid','executions','users',
                    'local','visits','runs_by_project','runs_by_paper','items','items_by_run',
                    'findings','findings_by_run','derived','decisions','publication',
                    'project_ids','run_review_status','channels','paper_review_rows')
    _shared: dict = {}
    _shared_lock = threading.Lock()
    _load_locks = weakref.WeakValueDictionary()

    @timed("projection")

    def refresh(self, project=None, selection=None, kind=None):
        """Bring this worker's projection to the catalog's current generation.

        A SQLite read transaction provides a consistent generation without
        blocking writers or other readers. The LOAD is then shared between
        workers at the same (generation, scope): every worker at one generation
        computes byte-identical data from the same read-only tables, so paying
        for it once is not a semantic change -- it is the same answer, once.

        MEASURED 2026-09-15 on the embargoed 2026-09 corpus (37,465 items, ~200k rows):
        the load costs about 4.4 s, and each worker used to pay it. The service
        runs FOUR interactive readers and hands each thread its own Repository,
        so three sequential queue requests hit three cold workers and paid
        7.5-8.6 s apiece -- with the catalog generation provably unchanged
        between them. It also held four copies of the projection on a machine
        that was swapping.
        """
        scope=(project,selection,kind)
        version=self.catalog.version
        if self.version == version and getattr(self,'scope',None)==scope:
            return
        key=(str(getattr(self.catalog,'path','')), version, scope)
        # Only cache bookkeeping uses the global lock. A cold corpus must not
        # hold up another scope's cached detail; same-scope loads still coalesce.
        with Repository._shared_lock:
            load_lock = Repository._load_locks.setdefault((key[0], scope), threading.Lock())
        with load_lock:
            version = self.catalog.version
            key = (key[0], version, scope)
            with Repository._shared_lock:
                payload = Repository._shared.get(key)
            if payload is None:
                with self.catalog.snapshot():
                    version = self.catalog.version
                    self._load_projection(project, selection, kind)
                key = (key[0], version, scope)
                payload = {k: getattr(self, k) for k in self._SHARED_KEYS if hasattr(self, k)}
                with Repository._shared_lock:
                    if len(Repository._shared) >= 4:
                        Repository._shared.pop(next(iter(Repository._shared)), None)
                    Repository._shared[key] = payload
        for name,value in payload.items(): setattr(self,name,value)
        # Per-worker caches are NOT shared: they are mutated on every read.
        self.paper_pages={}
        self.feed_pages={}
        self.version=version
        self.scope=scope

    def _load_projection(self, project, selection, kind):
        c = self.catalog
        self.data = c.headers(project)
        self.corpora = {p['id']:p for p in self.data.get('corpora',[])}
        self.papers = {p['id']:p for p in self.data.get('papers',[])}
        self.runs = {db_primary_key(r):r for r in self.data.get('runs',[])}
        self.by_uid = {r['run_uid']:r for r in self.runs.values()}
        self.executions = {e['execution_uid']:e for e in self.data.get('executions',[])}
        self.users = {u['id']:u for u in self.data.get('users',[])}
        self.local = {(p,d):(b,path) for p,d,b,path in c.local_papers(project)}
        query = 'select project,dir,body from visits'
        self.visits = {(p,d):json.loads(body) for p,d,body in c.reader.execute(
            query + (' where project=?' if project else ''), [project] if project else [])}
        self.runs_by_project = {}
        self.runs_by_paper = {}
        for r in self.runs.values():
            self.runs_by_project.setdefault(self.project_for_run(r),[]).append(r)
            self.runs_by_paper.setdefault(r.get('paper_id'),[]).append(r)
        if project and selection:
            chosen=self.selected_runs(project,selection,kind)
            # The paper page's fallback (see `partial_fallback`) needs its
            # findings in the projection; every other view selects its runs
            # explicitly and so never sees them.
            if selection=='latest' and kind is None:
                chosen+=self.partial_fallback(project,chosen)
            run_ids=[db_primary_key(r) for r in chosen]
        else:
            run_ids=list(self.runs)
        for entity in ('component_items','findings','reviews','run_channels','run_review_status'):
            self.data[entity]=c.rows_for(entity,'run_id',run_ids) if project!='' or entity in ('reviews','run_review_status') else []
        for entity in ('image_publication','paper_reviews'):
            self.data[entity]=c.rows_for(entity,'paper_id',self.papers) if project!='' else []
        # Derived image types are keyed by ITEM, not run: load them for exactly
        # the items just loaded. (The cache held all 31,418 rows for the first
        # corpus while every item read `untyped`, because this fixed list did
        # not include the table -- a loader omission reads as "nothing typed".)
        item_ids=[i['id'] for i in self.data.get('component_items',[])]
        self.data['component_item_derived']=c.rows_for('component_item_derived','item_id',item_ids) if project!='' and item_ids else []
        self.items = {i['id']:i for i in self.data.get('component_items',[])}
        # Derived image type per item (migration 007): a model's classification,
        # kept beside the sealed item record rather than in it.
        self.derived = {d['item_id']:d for d in self.data.get('component_item_derived',[])}
        self.findings = {i['id']:i for i in self.data.get('findings',[])}
        self.publication = {(p['paper_id'],p['item_uid']):p for p in self.data.get('image_publication',[])}
        self.decisions = {}
        for e in sorted(self.data.get('reviews',[]),key=lambda e:(str(e.get('decided_at') or ''),e['id'])):
            r = self.runs.get(e['run_id'])
            if not r: continue
            u = self.users.get(e['reviewer_id'],{})
            reviewer = u.get('legacy_name') or u.get('name') or str(e['reviewer_id'])
            rec = dict(event_id=e.get('event_uid') or f"legacy:{e['id']}",run_id=r['run_uid'],
                       item=e['issue_key'],decision=e.get('decision'),reviewer=reviewer,
                       at=e.get('decided_at'),note=e.get('note'),extra=e.get('extra'),pending=False)
            self.decisions.setdefault((r['run_uid'],e['issue_key']),[]).append(rec)
        for e in c.pending():
            self.decisions.setdefault((e['run_id'],e['item']),[]).append({**e,'pending':True})
        self.project_ids = {p['name']:p['id'] for p in self.corpora.values()}
        self.runs_by_project = {}
        self.runs_by_paper = {}
        self.items_by_run = {}
        self.findings_by_run = {}
        for r in self.runs.values():
            self.runs_by_project.setdefault(self.project_for_run(r),[]).append(r)
            self.runs_by_paper.setdefault(r.get('paper_id'),[]).append(r)
        for i in self.items.values(): self.items_by_run.setdefault(i['run_id'],[]).append(i)
        for f in self.findings.values(): self.findings_by_run.setdefault(f['run_id'],[]).append(f)
        self.paper_pages = {}
        self.feed_pages = {}
        self.run_review_status=self.data.get('run_review_status',[])
        self.channels={}
        for ch in self.data.get('run_channels',[]):self.channels.setdefault(ch['run_id'],{})[ch['channel']]={'state':ch['state'],'detail':ch.get('detail')}
        self.paper_review_rows=self.data.get('paper_reviews',[])


    def judgments(self, run, item):
        events = self.decisions.get((run,item),[])
        latest = {}
        # Pending local events overlay this user's acknowledged event until sync.
        for e in events: latest[e['reviewer']] = e
        rows = list(latest.values())
        conflict = len({r['decision'] for r in rows})>1
        return dict(reviewers=rows,history=events,conflict=conflict,
                    decision=rows[-1] if rows and not conflict else None)

    def project_name(self, paper):
        return self.corpora.get(paper.get('corpus_id'),{}).get('name')

    def project_for_run(self, run):
        p = self.papers.get(run.get('paper_id'))
        if p: return self.project_name(p)
        e = self.executions.get(run.get('execution_uid'),{})
        return self.corpora.get(e.get('corpus_id'),{}).get('name')

    def selected_runs(self, project, selection='latest', kind=None, paper=None):
        rows = [r for r in (self.runs_by_paper.get(paper,[]) if paper is not None else self.runs_by_project.get(project,[])) if self.project_for_run(r)==project
                and (kind is None or component(r)==kind) and (paper is None or r.get('paper_id')==paper)]
        rows.sort(key=lambda r:(run_time(r),db_primary_key(r)))
        if selection and selection!='latest':
            execution = self.executions.get(selection)
            reused = (execution or {}).get('reused_run_ids') or []
            selected = [r for r in rows if selection in (r['run_uid'],r.get('execution_uid'),r.get('name')) or r['run_uid'] in reused]
            if not selected and selection not in self.executions:
                raise ValueError('Selected run is not recorded for this project/paper')
            rows = selected
        else:
            rows = [r for r in rows if (r.get('history_record') or {}).get('latest_eligible') is not False and not r.get('retired_at')]
            # A partial pipeline is an experiment: never part of the default
            # paper review (counts, severity, queue). Explicit selection, or
            # asking for kind='partial_review', still reaches it.
            if kind != 'partial_review':
                rows = [r for r in rows if component(r) != 'partial_review']
        grouped = {}
        copy_jobs = {}
        families = {(component(r), (r.get('history_record') or {})['selection_family']): r.get('execution_uid')
                    for r in rows if (r.get('history_record') or {}).get('selection_family')}
        for r in rows:
            if component(r)=='copy_paste':
                copy_jobs[r.get('paper_id')] = r.get('parent_run_uid') or r.get('execution_uid') or r['run_uid']
        for r in rows:
            h = r.get('history_record') or {}
            if h.get('selection_family') and r.get('execution_uid') != families[(component(r),h['selection_family'])]:
                continue
            if component(r)=='copy_paste':
                if (r.get('parent_run_uid') or r.get('execution_uid') or r['run_uid']) == copy_jobs[r.get('paper_id')]:
                    grouped[r['run_uid']] = r
            else:
                grouped[(component(r),h.get('scope_key') or r.get('paper_id') or 'cross')] = r
        # Explicit run UID always means precisely that run, including failed/empty.
        return list(grouped.values())

    def partial_fallback(self, project, selected, paper=None):
        """The newest partial run of each paper `selected` has no review for.

        `latest` leaves partial pipelines out on purpose: they are never a
        paper's review, so they must not set its counts, severity or queue
        place. But a paper whose ONLY runs are partial then read "No run
        recorded for this selection" -- its tools-agent findings existed and
        could not be seen (2026-10-18, the GRIM ground-truth tools_only
        runs). The paper page shows this run instead, labelled provisional;
        the full-review views never call this.
        """
        reviewed={r.get('paper_id') for r in selected if component(r)=='comprehensive'}
        newest={}
        for r in self.selected_runs(project,'latest','partial_review',paper):
            if r.get('paper_id') in reviewed: continue
            old=newest.get(r.get('paper_id'))
            if old is None or (run_time(r),db_primary_key(r))>(run_time(old),db_primary_key(old)):
                newest[r.get('paper_id')]=r
        return list(newest.values())

    def run_history(self, project, kind=None, **args):
        """Run selection needs headers only, never candidate/review projections."""
        headers = Repository(self.catalog)
        with self.catalog.snapshot():
            data = self.catalog.headers(project)
            headers.corpora = {r['id']: r for r in data['corpora']}
            headers.papers = {r['id']: r for r in data['papers']}
            headers.runs = {db_primary_key(r): r for r in data['runs']}
            headers.executions = {r['execution_uid']: r for r in data['executions']}
        return headers.catalog_runs(project, kind, **args)

    def catalog_runs(self, project, kind=None, **args):
        runs = [r for r in self.runs.values() if self.project_for_run(r)==project and (not kind or component(r)==kind)]
        rows=[]
        for r in sorted(runs,key=lambda r:(run_time(r),db_primary_key(r)),reverse=True):
            rows.append(dict(id=r['run_uid'],label=f"v{r.get('pipeline_version') or 'unknown'} · {run_time(r) or 'date unknown'} · {r.get('name') or r['run_uid']}"+(' · details retired' if r.get('retired_at') else ''),
                             status='retired' if r.get('retired_at') else r.get('execution_status') or r.get('status'),execution_id=r.get('execution_uid'),component=component(r)))
        # Execution selections retain reused jobs and failed/empty executions.
        executions = [e for e in self.executions.values() if self.corpora.get(e['corpus_id'],{}).get('name')==project and (not kind or kind in e.get('requested_components',[]))]
        options = [dict(id=e['execution_uid'],label=f"{e.get('started_at') or 'date unknown'} · {e['name']}",status=e['status']) for e in sorted(executions,key=lambda e:str(e.get('started_at') or ''),reverse=True)]
        # ONE LINE PER EVENT. A run record is the per-paper answer an execution
        # produced; listing both showed every sweep twice on a one-paper corpus
        # (Dan, 2026-09-14: "one run should not be shown twice") and N+1 times
        # on an N-paper one. A record folds into its execution -- selecting the
        # execution already selects its records (`selected_runs`) -- and only a
        # record whose execution is not in this listing stands on its own.
        by_execution = {o['id']: o for o in options}
        standalone = []
        for row in rows:
            option = by_execution.get(row.get('execution_id'))
            if option is None:
                standalone.append(row)
                continue
            option['n_runs'] = option.get('n_runs', 0) + 1
            option.setdefault('components', [])
            if row.get('component') and row['component'] not in option['components']:
                option['components'].append(row['component'])
            version = row['label'].split(' · ', 1)[0]
            if version != 'vunknown' and version not in option.setdefault('versions', []):
                option['versions'].append(version)
        for option in options:
            n = option.get('n_runs', 0)
            if n:
                option['n_runs'] = n
                tail = (option.get('versions') or [])[:1] + (option.get('components') or [])[:1]
                if n > 1:
                    tail.append(f"{n} papers")
                option['label'] += ''.join(f" · {t}" for t in tail)
        result,pagination = page(options+standalone,args)
        return dict(runs=result,pagination=pagination,sync=self.catalog.status())

    def findings_page(self,args):
        selected=self.selected_runs(args['project'],args.get('run') or 'latest')
        ids={db_primary_key(r) for r in selected}
        rows=[]
        for rid in ids:
            r=self.runs[rid]
            for f in self.findings_by_run.get(rid,[]):
                if f.get('outcome')!='problem' or f.get('adjudication_action') in ('merged','discarded'):continue
                p=self.papers.get(f['paper_id'],{})
                if args.get('technique') and args['technique']!=f.get('technique'):continue
                if args.get('producer') and args['producer']!=f.get('producer'):continue
                if args.get('min_severity') and (f.get('severity') or 0)<int(args['min_severity']):continue
                if args.get('impossible')=='1' and not f.get('impossible'):continue
                if args.get('journal') and args['journal']!=p.get('journal'):continue
                if args.get('year') and str(args['year'])!=str(p.get('year')):continue
                rows.append({**f,'paper_id':p.get('paper_slug') or Path(p.get('dir') or '').name,
                             'run_id':r['run_uid'],'journal':p.get('journal'),'year':p.get('year'),'detail_key':db_primary_key(f)})
        for rid in ids:
            r=self.runs[rid]
            for raw in self.items_by_run.get(rid,[]):
                if self.represented(raw,selected): continue
                candidate=self.item_view(raw,args.get('run') or 'latest')
                if candidate['publication_status']!='published': continue
                p=self.papers.get(raw['owner_paper_id'],{})
                if args.get('technique') and args['technique']!=candidate.get('detector_kind'): continue
                if args.get('producer') and args['producer']!=component(r): continue
                if args.get('min_severity') or args.get('impossible')=='1': continue
                if args.get('journal') and args['journal']!=p.get('journal'): continue
                if args.get('year') and str(args['year'])!=str(p.get('year')): continue
                rows.append(dict(finding_id=candidate['id'],paper_id=p.get('paper_slug') or Path(p.get('dir') or '').name,
                                 run_id=r['run_uid'],title=candidate.get('sentence') or candidate['id'],
                                 producer=component(r),technique=candidate.get('detector_kind'),severity=None,
                                 impossible=False,journal=p.get('journal'),year=p.get('year'),component_item=raw['id'],
                                 reviews=candidate['reviews']))
        rows.sort(key=lambda f:(-(f.get('severity') or 0),f['finding_id']))
        result,pagination=page(rows,args)
        return {'rows':result,'pagination':pagination,'sync':self.catalog.status()}

    def resolve_paper(self, project, slug='', directory=''):
        matches=[p for p in self.papers.values() if self.project_name(p)==project and
                 ((directory and directory==(p.get('dir') or f"@{p['id']}")) or
                  (not directory and slug in (p.get('paper_slug'),Path(p.get('dir') or '').name,f"@{p['id']}")))]
        if len(matches)>1: raise ValueError('Ambiguous paper; use its corpus-relative directory')
        if matches: return matches[0]
        if (project,directory) in self.local:
            # A moved/nested report is linked only by an exact recorded run ID,
            # never a DOI or basename. Keep the local directory for source reads.
            body = self.local[(project,directory)][0]
            owners = {self.by_uid[r['run_id']]['paper_id']
                      for r in body.get('runs', [])
                      if r.get('run_id') in self.by_uid
                      and self.project_for_run(self.by_uid[r['run_id']]) == project
                      and self.by_uid[r['run_id']].get('paper_id') in self.papers}
            if len(owners) > 1:
                raise ValueError('Local reports refer to multiple shared papers; map this folder explicitly')
            if owners:
                return {**self.papers[owners.pop()], 'dir': directory}
            return dict(id=f'local:{project}:{directory}',corpus_id=None,dir=directory,local_project=project)
        raise LookupError('Paper is not in the synchronized catalog')

    def represented(self, candidate, selected):
        """Deduplicate only explicit parent ownership plus original finding identity."""
        owner=self.runs[candidate['run_id']]
        parent=owner.get('parent_run_uid')
        if not parent: return False
        originals={candidate.get('item_uid'),(candidate.get('record') or {}).get('source_id')}
        return any(f.get('legacy_original_id') in originals and f.get('legacy_original_id')
                   for r in selected if r['run_uid']==parent
                   for f in self.findings_by_run.get(db_primary_key(r),[]))

    def paper_row(self, p):
        project=self.project_name(p) or p.get('local_project')
        directory=p.get('dir') or f"@{p['id']}"
        local=self.local.get((project,directory),({},None))[0]
        selected=self.selected_runs(project,paper=p['id'])
        comprehensive=[r for r in selected if component(r)=='comprehensive']
        latest=comprehensive[-1] if comprehensive else None
        ids={db_primary_key(r) for r in selected}
        fs=[f for rid in ids for f in self.findings_by_run.get(rid,[]) if f.get('outcome')=='problem' and f.get('adjudication_action') not in ('merged','discarded')]
        accepted=[i for rid in ids for raw in self.items_by_run.get(rid,[]) if raw['owner_paper_id']==p['id'] and not self.represented(raw,selected) for i in [self.item_view(raw)] if i['publication_status']=='published']
        authors=p.get('authors')
        if isinstance(authors,list): authors=', '.join(str(a.get('name') or a.get('family') or '') if isinstance(a,dict) else str(a) for a in authors)
        meta=p.get('metadata') or {}
        submitted=any(x['paper_id']==p['id'] and x.get('submitted_to_pubpeer') for x in self.paper_review_rows)
        statuses=[x for x in self.run_review_status if latest and x['run_id']==db_primary_key(latest)]
        complete=any(x['status']=='complete' for x in statuses)
        decisions=[e for (uid,item),events in self.decisions.items() if uid in {x['run_uid'] for x in selected} for e in events]
        paper_decisions=[x for x in decisions if x['item']=='__paper__']
        paper_state=paper_decisions[-1].get('extra',{}) if paper_decisions else {}
        visit=self.visits.get((project,directory))
        viewed=local.get('viewed')
        if visit:
            prior=viewed or {}
            viewed={**prior,'viewed':True,'source':'recorded',
                    'n_views':max(visit.get('n_views',1),prior.get('n_views') or 0),
                    'first_at':min(prior.get('first_at') or visit.get('first_at',visit['at']),visit.get('first_at',visit['at'])),
                    'last_at':max(prior.get('last_at') or '',visit['at']),
                    'viewers':list(dict.fromkeys(v for v in [*(prior.get('viewers') or []),*visit.get('viewers', [visit.get('viewer')])] if v))}
        image_runs=[r for r in selected if component(r)=='image_forensics']
        image_state=next((r.get('execution_status') or r.get('status') for r in image_runs),None)
        image_channel=self.channels.get(db_primary_key(latest),{}).get('image_forensics',{}) if latest else {}
        image_complete=bool(image_runs) and all((r.get('execution_status') or r.get('status')) in ('complete','completed') for r in image_runs)
        if not image_runs:
            image_complete=bool(latest) and (latest.get('execution_status') or latest.get('status')) in ('complete','completed') and image_channel.get('state')=='ran'
        reset=any(r.get('retirement_reason')=='user_requested_rerun' for r in self.runs_by_paper.get(p['id'],[])) and not image_runs
        if reset: image_complete=False
        return {**local,**{k:v for k,v in p.items() if v is not None and k not in ('sources','metadata','authors')},
                'paper_id':p.get('paper_slug') or Path(directory).name,'shared_id':p['id'],'dir':directory,
                'viewed':viewed,'image_status':('awaiting a new analysis' if reset else image_state or image_channel.get('state') or 'not run'),
                'authors':authors or local.get('authors'),'volume':meta.get('volume') or local.get('volume'),
                'issue':meta.get('issue') or local.get('issue'),'channels':self.channels.get(db_primary_key(latest),{}) if latest else {},
                'runs':[],'n_runs':len(self.runs_by_paper.get(p['id'],[])),
                'latest_run':latest['run_uid'] if latest else None,
                'analysed_at':run_time(latest) if latest else None,'pipeline_version':latest.get('pipeline_version') if latest else None,
                'n_findings':len(fs)+len(accepted) if selected else None,
                'n_non_image_findings':sum(f.get('producer')!='image_track' for f in fs) if selected else None,
                'n_image_findings':sum(component(self.by_uid[i['run_id']])=='image_forensics' for i in accepted)+sum(f.get('producer')=='image_track' for f in fs) if image_complete else None,
                'worst_severity_9':max((f.get('severity') or 0 for f in fs),default=None),
                'verdict':latest.get('verdict') if latest else None,'sources':local.get('sources',{'pdf':False,'xml':False,'state':'not_local'}),
                'review':{**paper_state,'reviewed':complete or bool(paper_state.get('reviewed')),'n_decisions':len(decisions),'submitted_to_pubpeer':submitted or bool(paper_state.get('submitted_to_pubpeer'))}, 'evidence':[]}

    def papers_page(self,args):
        project=args['project']
        if project not in self.paper_pages:
            rows=[self.paper_row(p) for p in self.papers.values() if self.project_name(p)==project]
            known={r['dir'] for r in rows}
            for (proj,d),(body,path) in self.local.items():
                if proj==project and d not in known:
                    rows.append(self.paper_row(self.resolve_paper(proj, directory=d)))
            self.paper_pages[project]=rows
        rows=list(self.paper_pages[project])
        search=str(args.get('q') or '').lower()
        if search: rows=[r for r in rows if search in ' '.join(str(r.get(k) or '') for k in ('title','doi','dir','authors')).lower()
                        or matches_paper_folder({'paper': {'dir': r.get('dir')}}, search)]
        key=args.get('sort') or 'findings'; field={'author':'first_author','folder':'dir','run':'analysed_at','version':'pipeline_version','findings':'n_non_image_findings','image':'n_image_findings','sev9':'worst_severity_9','worst':'worst_severity'}.get(key,key)
        reverse=args.get('direction','desc')=='desc'
        numeric=field in ('n_non_image_findings','n_findings','n_image_findings','worst_severity_9','year')
        missing=[r for r in rows if r.get(field) is None or r.get(field)=='']
        rows=[r for r in rows if r.get(field) is not None and r.get(field)!='']
        rows.sort(key=lambda r:((float(r.get(field) or 0) if str(r.get(field) or '').replace('.','',1).isdigit() else 0) if numeric else str(r.get(field) or '').lower(),r['dir']),reverse=reverse)
        rows.extend(sorted(missing,key=lambda r:r['dir']))
        result,pagination=page(rows,args)
        return dict(papers=result,pagination=pagination,sync=self.catalog.status())

    def projects(self):
        # One pass per collection, grouped by project. The per-project rescans
        # this replaces were quadratic: 5.7 s for 106 projects (2026-09-26).
        names=sorted(set(self.project_ids)|{p for p,d in self.local})
        n_shared=Counter();shared_dirs={}
        for p in self.papers.values():
            name=self.project_name(p);n_shared[name]+=1
            shared_dirs.setdefault(name,set()).add(p.get('dir'))
        n_local=Counter();n_pdf=Counter();n_xml=Counter();local_image=Counter()
        for (name,d),(b,path) in self.local.items():
            sources=b.get('sources',{})
            n_pdf[name]+=bool(sources.get('pdf'));n_xml[name]+=bool(sources.get('xml'))
            if d in shared_dirs.get(name,()): continue
            n_local[name]+=1
            local_image[name]+=b.get('channels',{}).get('image_forensics',{}).get('state')=='ran'
        completed={}
        for x in self.run_review_status:
            run=self.runs.get(x['run_id']) if x['status']=='complete' else None
            if run and run.get('paper_id') is not None:
                completed.setdefault(self.project_for_run(run),set()).add(run['paper_id'])
        rows=[]
        for name in names:
            selected=self.selected_runs(name)
            image_papers={x.get('paper_id') for x in selected if component(x)=='image_forensics' and x.get('status')=='complete'}-{None}
            text_papers={x.get('paper_id') for x in selected if component(x)=='text_track' and x.get('status')=='complete'}-{None}
            rows.append(dict(name=name,n_papers=n_shared[name]+n_local[name],n_pdf=n_pdf[name],n_xml=n_xml[name],n_image_run=len(image_papers)+local_image[name],n_text_run=len(text_papers),n_human_reviewed=len(completed.get(name,())),n_not_fetched=0,n_in_progress=0))
        return dict(projects=rows,n_projects=len(rows),n_papers=sum(r['n_papers'] for r in rows),papers_root='registered local roots',sync=self.catalog.status())

    def find_item(self,args):
        selected=self.selected_runs(args['project'],args.get('run') or 'latest',args.get('component'))
        if any(r.get('retirement_reason')=='user_requested_rerun' for r in selected):
            raise LookupError('Image results removed at the user’s request; awaiting a new analysis.')
        ids={db_primary_key(r) for r in selected}
        candidates=[i for i in self.items.values() if i['item_uid']==args['item'] and i['run_id'] in ids and (not args.get('owner') or self.runs[i['run_id']]['run_uid']==args['owner'])]
        if len(candidates)==1 and candidates[0]['record'].get('retired'):
            raise LookupError('Superseded image details were retired; select the newer run. Local archive is preserved.')
        if len(candidates)!=1: raise LookupError('Item is absent or ambiguous in the selected run')
        return candidates[0]

    #: Ceiling on one filter-wide review. Above it the action REFUSES rather
    #: than labelling a prefix: a bulk decision that silently covered the first
    #: N of a larger match set would put a wrong denominator under every
    #: measurement the labels are for.
    BULK_REVIEW_MAX = 5000

    def save_review_filter(self,args):
        """Record one decision on many items in ONE call.

        Two scopes, and the difference is what the reviewer could see:

        * `items`: an explicit `[{run, id}, ...]` selection. Saves every one,
          including rows that already carry a decision -- the reviewer is
          looking at them. This is the path the queue's bulk button takes, and
          it exists because the old one sent ONE HTTP REQUEST PER ROW:
          MEASURED 2026-09-12 at ~95 decisions a minute (~630 ms each), so a
          1,944-row selection took twenty minutes, and every request made the
          service re-refresh its projection over 406,259 cached records and
          bumped the revision the reviewer's own queue was paging through.
        * a filter: the whole match set is walked server-side. Here a row that
          already carries ANY reviewer's decision is SKIPPED and counted -- a
          filter-wide sweep must not overwrite the `true_issue` somebody
          recorded by hand, and the reviewer cannot see what the filter
          covers. It refuses rather than labelling a partial set: above
          `BULK_REVIEW_MAX`, or when `expected_total` no longer agrees.

        Either way each decision is written AGAINST ITS OWN RUN through
        `save_review`, so every event still reaches the durable outbox, and
        `failed` names the rows to retain for retry.
        """
        from ..review_io import ALL_DECISIONS
        reviewer=str(args.get('reviewer') or '').strip()
        if not reviewer: raise ValueError('Reviewer required')
        decision=args.get('decision')
        if decision not in ALL_DECISIONS: raise ValueError('Valid decision required')
        explicit=args.get('items')
        reason=str(args.get('reason') or '').strip()
        note=str(args.get('note') or '').strip()
        scope={k:v for k,v in args.items() if k not in
               ('decision','reviewer','reason','note','expected_total','offset','limit','items')}
        if explicit is not None:
            if not isinstance(explicit,list) or not explicit:
                raise ValueError('items must be a non-empty list of {run, id}')
            if len(explicit)>self.BULK_REVIEW_MAX:
                raise ValueError(f'{len(explicit)} items selected; the ceiling is '
                                 f'{self.BULK_REVIEW_MAX}')
            items=[{'id':row.get('id'),'run_id':row.get('run'),'decision':None}
                   for row in explicit]
            total=len(items)
            skip_decided=False
        else:
            feed=self.feed({**scope,'offset':0,'limit':1})
            total=feed['pagination']['total']
            expected=args.get('expected_total')
            if expected is not None and int(expected)!=total:
                raise ValueError(f'The filter now matches {total} items, not {expected}; '
                                 'reload the queue before applying a filter-wide decision')
            if total>self.BULK_REVIEW_MAX:
                raise ValueError(f'{total} items match; narrow the filter to '
                                 f'{self.BULK_REVIEW_MAX} or fewer')
            items=[]
            offset=0
            while offset<total:
                rows=self.feed({**scope,'offset':offset,'limit':100})['items']
                if not rows: break
                items.extend(rows)
                offset+=len(rows)
            skip_decided=True
        saved=[]; skipped=[]; failed=[]
        for item in items:
            if skip_decided and item.get('decision'):
                skipped.append(item['id']); continue
            try:
                saved.append(self.save_review({
                    'project':args['project'],'run':item['run_id'],'item':item['id'],
                    'decision':decision,'reviewer':reviewer,'note':note,
                    'extra':{k:v for k,v in (('bulk_reason',reason or None),
                                             ('bulk_scope',None if explicit is not None else
                                              {k2:v2 for k2,v2 in scope.items()
                                               if k2!='project'})) if v},
                }))
            except Exception as exc:  # noqa: BLE001 -- one bad row must not lose the rest
                failed.append({'id':item['id'],'error':str(exc)})
        return dict(matched=total,saved=len(saved),skipped_already_decided=len(skipped),
                    failed=failed,decision=decision,reason=reason or None,
                    events=[e.get('event_id') for e in saved])

    def _event_elsewhere(self, event_id):
        """An existing event with this id on ANOTHER target, by indexed lookup."""
        db=self.catalog.reader
        row=db.execute('select body from outbox where event_id=?',[event_id]).fetchone()
        if row: return json.loads(row[0])
        row=db.execute("select body from records where entity='reviews' and json_extract(body,'$.event_uid')=?",[event_id]).fetchone()
        if not row: return None
        e=json.loads(row[0]); r=self.runs.get(e.get('run_id')) or {}
        u=self.users.get(e.get('reviewer_id'),{})
        return dict(event_id=event_id,run_id=r.get('run_uid'),item=e.get('issue_key'),decision=e.get('decision'),
                    reviewer=u.get('legacy_name') or u.get('name') or str(e.get('reviewer_id')),at=e.get('decided_at'),
                    note=e.get('note'),extra=e.get('extra'))

    def save_review(self,args):
        from ..review_io import ALL_DECISIONS
        reviewer=str(args.get('reviewer') or '').strip()
        if not reviewer: raise ValueError('Reviewer required')
        run=self.by_uid.get(args.get('run'))
        if not run or self.project_for_run(run)!=args['project']:
            raise ValueError('An exact owning run is required')
        target=args['item']
        # Per-run lists, never every item: a 5,000-row bulk save used to scan
        # the whole projection (and every decision) once per row.
        if target!='__paper__' and not any(i['item_uid']==target for i in self.items_by_run.get(run['id'],())) and not any(target in (i['finding_id'],i.get('legacy_original_id')) for i in self.findings_by_run.get(run['id'],())):
            raise ValueError('Decision target not in selected run')
        retry=None
        if args.get('event_id'):
            for e in self.decisions.get((run['run_uid'],target),()):
                if e['event_id']==args['event_id']: retry=e
            if retry is None:
                retry=self._event_elsewhere(args['event_id'])
        if retry and (retry['run_id'],retry['item'],retry['reviewer'])!=(run['run_uid'],target,reviewer):
            raise ValueError('Review event ID conflicts with an existing event')
        previous=retry or next((e for e in reversed(self.decisions.get((run['run_uid'],target),[])) if e['reviewer']==reviewer),{})
        decision=args['decision'] if 'decision' in args else previous.get('decision','unsure')
        # Clearing is an explicit uncertainty event, retaining the historical judgment.
        if decision is None: decision='unsure'
        if decision not in ALL_DECISIONS: raise ValueError('Valid decision required')
        extra={**(previous.get('extra') or {}),**(args.get('extra') or {})}
        event=dict(event_id=args.get('event_id') or 'rv_'+uuid.uuid4().hex,run_id=run['run_uid'],item=target,
                   decision=decision,reviewer=reviewer,note=str(args.get('note',previous.get('note')) or ''),at=args.get('at') or (retry or {}).get('at') or now(),extra=extra)
        return self.catalog.enqueue(event)
