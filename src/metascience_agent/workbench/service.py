"""Managed JSON-lines service. Interactive reads never wait for sync or indexing."""
from __future__ import annotations

import argparse
import contextlib
import os
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import threading
import time
import uuid
import weakref

from .timing import current, measure
from .catalog import Catalog, encode, now
from .remote import Remote, describe_error
from .repository import Repository, component, page, run_time, db_primary_key
from .common import run_pipeline
from .image_mixins import SHARED_QUEUE_METHODS, ImageServiceMixin


class Service(ImageServiceMixin):
    """The workbench JSON-lines service. Image media, items, videos and the
    shared-storage image queue come from the image package's `ImageServiceMixin`."""
    def __init__(self, catalog=None, remote=None, index=None, background=True, detail_remote=None):
        self.catalog=catalog or Catalog()
        self.remote=remote or Remote()
        # One reusable foreground connection, independent of sync transactions.
        # Injected test transports may intentionally model both lanes.
        self.detail_remote=detail_remote or (Remote(self.remote.url) if isinstance(self.remote,Remote) else self.remote)
        self.detail_network=threading.Lock()
        self._workers=threading.local()
        self.network=threading.Lock()
        self.stop=threading.Event()
        self.wake=threading.Event()
        self.local_wake=threading.Event()
        self.last_active=time.monotonic()
        self.index=index
        self.thread=None
        self.local_thread=None
        self.source_cache={}
        self.source_cache_lock=threading.Lock()
        self.source_locks=weakref.WeakValueDictionary()
        self.achromatic_cache={}
        from ..image_plugin import available as image_available, load as image_load
        # Queue thumbnails and review videos are the image package's; without
        # it they are absent and an image request raises ImagePluginUnavailable.
        if image_available():
            self.thumbnails=image_load("review_workbench.thumbnails").Thumbnails(self.catalog)
        else:
            self.thumbnails=None
        self._projects=None
        self._projects_lock=threading.Lock()
        self.jobs={}
        self.jobs_lock=threading.Lock()
        if image_available():
            self.videos=image_load("review_workbench.videos").Videos(self)
        else:
            self.videos=None
        if background:
            if self.videos is not None:
                self.videos.start()
            from .monitor import FileMonitor
            self.local_thread=threading.Thread(target=FileMonitor(self).run,daemon=True,name='local-files')
            self.local_thread.start()
            self.thread=threading.Thread(target=self.background,daemon=True)
            self.thread.start()

    @property
    def repo(self):
        if not hasattr(self._workers,'repo'): self._workers.repo=Repository(self.catalog, videos=self.videos)
        return self._workers.repo

    def cached_source(self, key, convert):
        """Coalesce one source conversion without blocking unrelated sources.

        Callers validate source hashes/dependencies before entering. Locks are
        weakly held so eviction and failed conversions cannot grow a lock cache.
        """
        with self.source_cache_lock:
            if key in self.source_cache:
                return self.source_cache[key]
            lock = self.source_locks.setdefault(key, threading.Lock())
        with lock:
            with self.source_cache_lock:
                if key in self.source_cache:
                    return self.source_cache[key]
            value = convert()
            with self.source_cache_lock:
                self.source_cache[key] = value
                if len(self.source_cache) > 20:
                    self.source_cache.pop(next(iter(self.source_cache)))
            return value

    def start_job(self, kind, work):
        """Run `work(progress)` off the request path; poll with `job_status`.

        A long write (a 5,000-item bulk decision) outlasted the bridge's 60 s
        timer, and the queue then said "Nothing was saved" while the service
        went on saving. A job answers at once with an id; its `progress` says
        how much is durable, and a job this process no longer knows (it was
        restarted) is an UNKNOWN outcome, never a failure that saved nothing.
        """
        job=dict(id='job_'+uuid.uuid4().hex,kind=kind,state='running',started_at=now(),progress={})
        with self.jobs_lock:
            finished=[k for k,j in self.jobs.items() if j['state']!='running']
            for k in finished[:-50]: self.jobs.pop(k,None)
            self.jobs[job['id']]=job
        def run():
            try: job.update(result=work(job['progress']),state='done')
            except Exception as exc: job.update(error=f'{type(exc).__name__}: {exc}',state='failed')
            job['finished_at']=now()
        threading.Thread(target=run,daemon=True,name=f'job-{kind}').start()
        return self.job_status(job['id'])

    def job_status(self, job_id):
        with self.jobs_lock: job=self.jobs.get(job_id)
        if job is None:
            raise LookupError('Unknown job: the service was restarted or the job expired. Its outcome is unknown; '
                              'reload the queue to see which decisions were saved.')
        return json.loads(encode(job))

    @property
    def projection(self):
        """The scope a request reads its projection in. NOT a lock: each worker
        thread owns its Repository (`repo`), so there is nothing to exclude.
        It used to hand each thread its OWN RLock, which excluded nothing while
        reading as though it serialised projection access."""
        return contextlib.nullcontext()

    def background(self):
        while not self.stop.is_set():
            try:
                with self.network:
                    # Bootstrap first only when the shared cache is uninitialized.
                    # Normal saves should not wait behind a routine journal pull.
                    if self.catalog.state('cursor') is None:
                        self.remote.sync(self.catalog)
                    acknowledged=[]
                    for event in self.catalog.pending():
                        try:
                            self.remote.send_review(event)
                            acknowledged.append(event['event_id'])
                        except Exception as exc:
                            with self.catalog.lock,self.catalog.db:
                                self.catalog.db.execute('update outbox set error=? where event_id=?',[str(exc),event['event_id']])
                    # Pull before clearing pending events, avoiding a disappearing decision.
                    self.remote.sync(self.catalog)
                    for event in acknowledged: self.catalog.acknowledge(event)
                    self.catalog.set_state('bytes_received',self.remote.bytes+self.detail_remote.bytes if self.detail_remote is not self.remote else self.remote.bytes)
                    self.catalog.set_state('sync_error',None)
            except Exception as exc:
                self.catalog.set_state('sync_error',describe_error(exc))
                self.remote.close()
            # A failed warm-up leaves the next page load to compute, but it is
            # named: a landing page that is slow because its summary cannot be
            # built must not look like one that was merely cold.
            try:
                self.projects()
                self.catalog.set_state('warmup_error',None)
            except Exception as exc:
                self.catalog.set_state('warmup_error',f'{type(exc).__name__}: {exc}')
            try: self.catalog.checkpoint_when_idle(self.last_active)
            except Exception as exc: self.catalog.set_state('checkpoint_error',f'{type(exc).__name__}: {exc}')
            interval=30 if time.monotonic()-self.last_active<90 else 300
            self.wake.wait(interval); self.wake.clear()

    def projects(self):
        """Landing-page summary, computed once per catalog version.

        The full-catalog projection costs ~6.6 s to load and shares a
        four-entry LRU with every project page, so the landing page used to
        pay it again after any browsing. The summary itself is small; keep it
        beside the version it came from. The background loop warms it after
        each sync.
        """
        with self._projects_lock:
            version=self.catalog.version
            if self._projects and self._projects[0]==version:
                return {**self._projects[1],'sync':self.catalog.status()}
            with self.projection:
                self.repo.refresh('', 'latest', None)
                result=self.repo.projects()
            from .project_admin import apply_flags
            result=apply_flags(self.catalog,result)
            self._projects=(version,result)
            return result

    def reconcile_files(self, changed_paths=None):
        """Poll known paper mappings only. Watcher losses cannot strand availability."""
        papers=self.catalog.records('papers')
        corpora={p['id']:p['name'] for p in self.catalog.records('corpora')}
        changed=False
        if changed_paths is not None:
            # A folder is affected when it IS a changed path, CONTAINS one, or
            # lies INSIDE one. Sets make that one lookup per folder level,
            # instead of every changed path against every paper (and a
            # database read per paper before the test).
            changed_set={Path(p) for p in changed_paths}
            touched=changed_set|{p.parent for p in changed_set}
            mapped={(p,d):path for p,d,path in self.catalog.reader.execute('select project,dir,path from papers_local')} if papers else {}
            roots={}
            for r in self.catalog.roots(): roots.setdefault(r['project'],[]).append(Path(r['path']))
            def affected(project,directory):
                for folder in [Path(mapped[(project,directory)])] if (project,directory) in mapped else [base/directory for base in roots.get(project,())]:
                    if folder in touched or any(a in changed_set for a in folder.parents): return True
                return False
        for paper in papers:
            # A full pass touches every paper folder on disk (minutes on a large
            # catalog). Shutdown must not wait for it: 2026-09-26 a Ctrl-C on
            # `npm run dev` left this service orphaned, mid-pass, for good.
            if self.stop.is_set(): break
            project=corpora.get(paper['corpus_id']); directory=paper.get('dir')
            if not project or not directory: continue
            if changed_paths is not None and not affected(project,directory): continue
            try:
                folder=self.catalog.paper_path(project,directory)
                suffixes={p.suffix.lower() for p in folder.iterdir() if p.is_file()}
                sources={'pdf':'.pdf' in suffixes,'xml':'.xml' in suffixes,'state':'local'}
            except (OSError,ValueError):
                sources={'pdf':False,'xml':False,'state':'unavailable'};folder=None
            with self.catalog.lock,self.catalog.db:
                row=self.catalog.db.execute('select body,path from papers_local where project=? and dir=?',[project,directory]).fetchone()
                body=json.loads(row[0]) if row else {}
                if body.get('sources')==sources: continue
                body['sources']=sources
                if folder or row:
                    self.catalog.db.execute('insert or replace into papers_local values(?,?,?,?)',[project,directory,encode(body),str(folder) if folder else row[1]])
                    changed=True
        if changed: self.catalog.generation+=1

    def detail(self,entity,key):
        found=self.catalog.detail(entity,key)
        if found is not None: return found
        with self.detail_network:
            found=self.catalog.detail(entity,key)
            if found is not None: return found
            generation=self.catalog.record_token(entity,key)
            try:
                found=self.detail_remote.detail(entity,key)
            except Exception:
                self.detail_remote.close()
                raise
            if not self.catalog.save_detail(entity,key,found,generation):
                raise RuntimeError('Record changed while loading; retry')
            return found

    def paper(self,args):
        repo=self.repo
        p=repo.resolve_paper(args['project'],args.get('slug',''),args.get('dir',''))
        selection=args.get('run') or 'latest'
        selected=repo.selected_runs(args['project'],selection,paper=p['id'])
        # A paper whose only numeric runs are partial shows its newest one,
        # labelled provisional, rather than "No run recorded".
        fallback=repo.partial_fallback(args['project'],selected,paper=p['id']) if selection=='latest' else []
        selected=selected+fallback
        ids={db_primary_key(r) for r in selected}
        from ..review_issues import _v2_issues_from_doc
        numeric=[f for f in repo.findings.values() if f['run_id'] in ids]
        issues=[]
        for f in numeric:
            r=repo.runs[f['run_id']]
            # Summary response intentionally has no computed evidence or article body.
            # `tool_basis` is named even when absent: a summary cached before
            # it existed reads "not recorded", not "model judgement".
            doc={'findings':[{**f,'adjudication':{'action':f.get('adjudication_action')},'tool_basis':f.get('tool_basis')}]}
            converted,_,_=_v2_issues_from_doc(doc,r['run_uid'],include_tracks=True)
            basis=f.get('location_basis') or {}
            for issue in converted:
                issue.update(detail_key=db_primary_key(f),detail_loaded=False,reviews=repo.judgments(r['run_uid'],f['finding_id']),
                             pipeline=run_pipeline(r),location_basis=basis)
                if not issue.get('location'): issue['location']=basis.get('location')
            issues.extend(converted)
        # Component/report duplicates require an explicit parent and original finding ID.
        # Every other component keeps its own owning run identity.
        for raw in repo.items.values():
            if raw['run_id'] not in ids or raw['owner_paper_id']!=p['id']: continue
            r=repo.runs[raw['run_id']]
            if repo.represented(raw,selected): continue
            candidate_view=repo.item_view(raw,selection)
            if candidate_view['publication_status']!='published': continue
            issues.append(dict(id=candidate_view['id'],kind='numeric',source_id=candidate_view['id'],run=r['run_uid'],
                title=candidate_view.get('sentence') or candidate_view.get('detector_kind') or candidate_view['id'],plain='',
                producer=component(r),tool=component(r),tool_source='component',
                severity=None,severity_9=None,passages=[],artefacts=[],
                extras={},component_item=raw['id'],reviews=candidate_view['reviews'],detail_loaded=True))
        issues.sort(key=lambda i:(-(i.get('severity_9') or 0),i['id']))
        # GROUP FINDINGS (default on): one tool family in one table or page
        # range is one ENTRY, and pagination counts entries, so a group is
        # never split across pages. Off: today's flat list.
        if str(args.get('group','1')).lower() not in ('0','false','off'):
            from ..finding_groups import group_issues
            entries=group_issues(issues)
            shown,pagination=page(entries,args)
            visible=[i for e in shown for i in e]
            pagination.update(grouped=True,findings_total=len(issues))
        else:
            visible,pagination=page(issues,args)
            pagination.update(grouped=False,findings_total=len(issues))
        for n,i in enumerate(visible,start=pagination['offset']+1):
            if i.get('priority') is None: i['priority']=n
        def model(r):
            # Two tools_only runs of one paper differ by model (sonnet, grok-4.6);
            # without it the picker showed two identical-looking partial runs.
            m=(((r.get('history_record') or {}).get('provenance') or {}).get('parameters') or {}).get('model')
            return f" · {m}" if m else ''
        options=[dict(id=r['run_uid'],label=f"v{r.get('pipeline_version') or 'unknown'} · {run_time(r)} · {r.get('name') or r['run_uid']}{model(r)}",
                      component=component(r),pipeline=run_pipeline(r)) for r in sorted(repo.runs.values(),key=run_time,reverse=True) if r.get('paper_id')==p['id']]
        latest=next((r for r in selected if component(r)=='comprehensive'),None) or (fallback[-1] if fallback else None)
        if latest is None and selection!='latest':
            # An explicitly selected partial run is that paper's run on screen.
            latest=next((r for r in reversed(selected) if component(r)=='partial_review'),None)
        review={'issues':{},'paper':{}}
        for i in issues:
            if i['reviews']['decision']: review['issues'][i['id']]={**i['reviews']['decision'],**(i['reviews']['decision'].get('extra') or {})}
        if latest:
            paper_judgment=repo.judgments(latest['run_uid'],'__paper__')['decision']
            if paper_judgment: review['paper']=paper_judgment.get('extra') or {}
        # Neighbor references contain no findings payloads.
        papers=sorted([x for x in repo.papers.values() if repo.project_name(x)==args['project']],key=lambda x:x.get('dir') or '')
        at=next((i for i,x in enumerate(papers) if x['id']==p['id']),-1)
        def ref(x):
            d=x.get('dir') or f"@{x['id']}"
            return {'slug':x.get('paper_slug') or Path(d).name,'dir':d}
        nav={'prev':ref(papers[at-1]) if at>0 else None,'next':ref(papers[at+1]) if 0<=at<len(papers)-1 else None}
        return dict(paper=repo.paper_row(p),project=args['project'],nav=nav,locators={},
            article={'mode':'none','warning':'Loading local source…'},sync=self.catalog.status(),
            issues=dict(issues=visible,pagination=pagination,review=review,headline={},
                latest_run=latest['run_uid'] if latest else (selected[-1]['run_uid'] if selected else None),
                available_runs=[o['id'] for o in options],run_options=options[:100],n_runs=len(options),
                source={'kind':'database','status':latest.get('execution_status') or latest.get('status') if latest else 'not_requested',
                        'detail':None if selected else 'No run recorded for this selection; this is not a clean-paper verdict.',
                        'execution_id':latest.get('execution_uid') if latest else None,
                        'pipeline':run_pipeline(latest) if latest else None,
                        'partial_fallback':bool(fallback)}))

    def reveal_target(self, args):
        """Resolve the same source as the viewer, preferring its verified named copy.

        An archived __runs reference is an identifier, not a relative filename.
        The current paper's copy may be selected only if its bytes still match
        that archive. Otherwise reveal the actual preserved file.
        """
        if not args.get('f'):
            return {'directory': str(self.catalog.paper_path(args['project'], args['dir'])), 'file': None}
        source = self.artifact(args)
        target = Path(source['path'])
        note = None
        if args['f'].startswith('__runs/'):
            record = source.get('record') or {}
            relative = record.get('original_path') or record.get('name')
            try:
                base = self.catalog.paper_path(args['project'], args['dir']).resolve()
                rel = str(relative or '').replace('\\', '/')
                candidate = (base / rel).resolve()
                if not rel or Path(rel).is_absolute() or '..' in rel.split('/') or not candidate.is_relative_to(base):
                    raise ValueError('Archived source name is not inside the paper folder')
                target = Path(self.catalog.register_file(candidate, expected=source['sha256'], allowed_root=base))
            except (OSError, ValueError) as exc:
                note = f'Showing the preserved source; the current paper copy is unavailable or differs. {exc}'
        return {'directory': str(target.parent), 'file': str(target), 'note': note}

    def artifact(self,args):
        project=args['project']; ref=args['f']
        media=self.image_media(project,args,ref)
        if media is not None: return media
        if not ref.startswith('__runs/'):
            base=self.catalog.paper_path(project,args['dir']).resolve()
            rel=ref.replace('\\','/')
            if Path(rel).is_absolute() or '..' in rel.split('/'): raise ValueError('Path must be paper-relative')
            target=(base/rel).resolve()
            if not target.is_relative_to(base) or not target.is_file(): raise ValueError('File missing or outside paper folder')
            return dict(path=str(target),record={'name':target.name},availability='local_current')
        parts=ref.split('/')
        if len(parts)!=3: raise ValueError('Invalid artifact reference')
        rec=self.catalog.artifact_record(project,parts[1],parts[2])
        sha=rec['content_sha256']
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha): raise ValueError('Invalid artifact hash')
        found=self.catalog.file_for(sha)
        if not found:
            roots=self.catalog.roots(project)
            if not any(r['available'] for r in roots) and self.catalog.discover_root(project):
                roots=self.catalog.roots(project)
            for root in roots:
                base=Path(root['path'])/'.analysis_runs'
                candidate=base/'objects'/sha[:2]/sha
                if candidate.is_file():
                    found=self.catalog.register_file(candidate,sha,base)
                    break
        if not found:
            raise FileNotFoundError(
                f"Historical evidence unavailable on this computer: {rec.get('record',{}).get('name') or parts[2]} "
                f"(sha256 {sha[:12]}...) is in no registered local root of project {project!r} "
                f"({len(self.catalog.roots(project))} registered). Register the corpus folder on the Files page, "
                "or re-run the sweep from this machine.")
        record=rec.get('record') or {'name':parts[2]}
        colour=self.colour_panel(project,args,record,found,sha)
        if colour is not None: return colour
        return dict(path=found,record=record,availability='verified',sha256=sha)

    def source(self,args):
        with self.projection:
            self.repo.refresh(args.get('project',''), args.get('run') or 'latest', args.get('component'))
            p=self.repo.resolve_paper(args['project'],args.get('slug',''),args.get('dir',''))
            kind=args.get('component') or 'comprehensive'
            selection=args.get('run') or 'latest'
            if kind=='image_forensics' and selection!='latest':
                # Cross-paper items share one run. Only explicitly scoped source
                # artifacts may supply the other paper; never show side A for B.
                selected=self.repo.selected_runs(args['project'],selection,kind)
                selected=[run for run in selected if run.get('paper_id') in (None,p['id']) or any(
                    a.get('record',{}).get('paper')==p.get('dir')
                    for a in self.catalog.rows_for('run_artifacts','run_id',[db_primary_key(run)]))]
                if not selected:
                    return {'article':{'mode':'none','warning':'No source recorded for this paper in the selected run.'},'locators':{},'availability':'not_recorded'}
            else:
                selected=self.repo.selected_runs(args['project'],selection,kind,p['id'])
            r=selected[-1] if selected else None
            def for_paper(artifact):
                scope=artifact.get('record',{}).get('paper')
                return scope==p.get('dir') if scope else r is not None and r.get('paper_id')==p['id']
            artifacts=[a for a in self.catalog.rows_for('run_artifacts','run_id',[db_primary_key(r)] if r else []) if for_paper(a) and (a.get('record',{}).get('name') or '').lower().endswith(('.pdf','.xml')) and a.get('role') in ('source','source_pdf','source_xml','input_file')]
        from ..extraction.xml_html import article_media
        if r and r.get('sealed_digest'):
            if artifacts:
                # XML is the reading source; retain a separately verified PDF toggle.
                errors=[]
                article={}
                main=[a for a in artifacts if 'supp' not in a['record']['name'].lower()]
                artifacts=main or artifacts
                for a in sorted(artifacts,key=lambda a:a['record']['name']):
                    is_pdf=a['record']['name'].lower().endswith('.pdf')
                    if article.get('has_pdf' if is_pdf else 'has_xml'): continue
                    ref=f"__runs/{r['run_uid']}/{a['artifact_uid']}"
                    try:
                        resolved=self.artifact({**args,'f':ref})
                    except (FileNotFoundError,ValueError) as exc:
                        errors.append(str(exc)); continue
                    if is_pdf:
                        article={**article,'mode':article.get('mode') or 'pdf','has_pdf':True,'pdf_relpath':ref,
                                 'warning':article.get('warning') or 'Preserved report source.'}
                    else:
                        from ..extraction.xml_html import _xml_article_html, doi_url
                        from ..extraction.xml_figures import IMAGE_SUFFIXES
                        assets=[]
                        for asset in self.catalog.rows_for('run_artifacts','run_id',[db_primary_key(r)]):
                            if not for_paper(asset):
                                continue
                            name=asset.get('record',{}).get('name') or ''
                            if Path(name).suffix.lower() not in IMAGE_SUFFIXES:
                                continue
                            media_ref=f"__runs/{r['run_uid']}/{asset['artifact_uid']}"
                            try:
                                self.artifact({**args,'f':media_ref})
                                state='verified'
                            except (FileNotFoundError,ValueError):
                                state='unavailable'
                            assets.append({'name':name,'ref':media_ref,'availability':state})
                        # Legacy archives often kept XML and candidate crops but
                        # no whole figures. Contemporary artwork is a separately
                        # labelled reading aid, only beside byte-identical XML.
                        local_images=None
                        try:
                            from ..extraction.jats import find_xml
                            local_path=self.catalog.paper_path(args['project'],p.get('dir') or f"@{p['id']}")
                            local_xml=find_xml(local_path)
                            import hashlib
                            if local_xml and hashlib.sha256(local_xml.read_bytes()).hexdigest()==resolved['sha256']:
                                local_images=local_path
                        except (FileNotFoundError,OSError):
                            pass  # No contemporary reading aid; archived text remains usable.
                        from ..extraction.xml_figures import figure_dependencies
                        # Resolve and validate files above on EVERY request. Only
                        # conversion is reused; disappearance/corruption changes
                        # availability and therefore the conversion key.
                        key=('archived', resolved['sha256'], ref,
                             json.dumps(assets, sort_keys=True),
                             str(local_images), figure_dependencies(local_images) if local_images else None)
                        body,meta,flavour,error=self.cached_source(key, lambda:
                            _xml_article_html(Path(resolved['path']),paper_dir=local_images,archived_assets=assets))
                        if error:
                            errors.append(f'Archived XML could not be rendered: {error}'); continue
                        article={**article,'mode':'xml','has_pdf':article.get('has_pdf',False),'has_xml':True,'html':body,
                            'title':meta.get('title'),'doi':meta.get('doi'),'doi_url':doi_url(meta.get('doi')),
                            'figures':meta.get('figures',[]),'xml_relpath':ref,
                            'flavour':flavour,'warning':'Preserved XML source; identity verified against the archived hash.'}
                if article:
                    if errors: article['warning'] += ' ' + '; '.join(errors)
                    article=article_media(article,args['project'],p.get('dir') or f"@{p['id']}")
                    return {'article':article,'locators':{},'availability':'verified'}
                return {'article':{'mode':'none','warning':'; '.join(errors)},'locators':{},'availability':'unavailable'}
            return {'article':{'mode':'none','warning':'No historical source was recorded for this run.'},'locators':{},'availability':'not_recorded'}
        try: path=self.catalog.paper_path(args['project'],p.get('dir') or f"@{p['id']}")
        except FileNotFoundError as exc: return {'article':{'mode':'none','warning':str(exc)},'locators':{},'availability':'unavailable'}
        # Only this source's files are statted, never the corpus; extraction is off
        # the findings path and cached against file identity.
        from ..extraction.xml_figures import figure_dependencies
        stamp=figure_dependencies(path)
        key=(str(path),stamp)
        from ..extraction.xml_html import article_view
        converted=self.cached_source(key, lambda: article_view(path))
        article=article_media(converted,args['project'],p.get('dir') or f"@{p['id']}")
        warning=' '.join(filter(None,[article.get('warning'),'Current local source; no archived source hash is recorded for this legacy run.']))
        return {'article':{**article,'warning':warning},'locators':{},'availability':'local_current'}

    def issue_detail(self,args):
        # The finding's OWN run, when the page names it: a partial run is not
        # in `latest`, so refreshing that scope left its findings unloaded and
        # every one of them read "Finding not in this project".
        scope=args.get('run') or 'latest'
        with self.projection:
            self.repo.refresh(args.get('project',''), scope, args.get('component'))
            f=self.repo.findings.get(int(args['finding']))
            if not f or self.repo.project_for_run(self.repo.runs[f['run_id']])!=args['project']:
                raise LookupError('Finding not in this project')
            r=self.repo.runs[f['run_id']]
            p=self.repo.papers[f['paper_id']]
        full=self.detail('findings',json.dumps([db_primary_key(f)]))['record']
        from ..review_issues import _v2_issues_from_doc
        issues,_,_=_v2_issues_from_doc({'findings':[full]},r['run_uid'],include_tracks=True)
        issue=issues[0] if issues else None
        locators={}
        if issue:
            issue.update(detail_key=db_primary_key(f),detail_loaded=True)
            # Persisted anchors are the cheapest and safest locator source.
            issue['anchors']=full.get('anchors')
            from ..locators import locators_for_paper, persisted_locators
            try:
                # A sealed run's files may have changed since: its persisted
                # anchors still describe what it read, so they are used; the
                # file is not re-searched.
                if r.get('sealed_digest'): locators=persisted_locators([issue])
                else:
                    path=self.catalog.paper_path(args['project'],p.get('dir') or f"@{p['id']}")
                    locators=locators_for_paper(path,[issue])
            except FileNotFoundError:
                locators=persisted_locators([issue])
        with self.projection:
            self.repo.refresh(args.get('project',''), scope, args.get('component'))
            if issue: issue.update(reviews=self.repo.judgments(r['run_uid'],f['finding_id']),pipeline=run_pipeline(r))
        return {'issue':issue,'locators':locators}

    def _thumbnails(self):
        if self.thumbnails is None:
            from ..image_plugin import ImagePluginUnavailable, INSTALL_HINT
            raise ImagePluginUnavailable(f"queue thumbnails: {INSTALL_HINT}")
        return self.thumbnails

    def summary(self,args):
        from ..image_plugin import load as _image_load
        review_media = _image_load("image_forensics.review_media")
        import hashlib
        candidate=self.handle('item',args)
        for panel in candidate.get('panels',[]):
            if not panel.get('image'): raise FileNotFoundError('Historical panel unavailable')
            resolved=self.artifact({**args,'dir':panel.get('paper_dir'),'f':panel['image']})
            path=Path(resolved['path'])
            panel.update(paper_path=str(path.parent),image=path.name)
        evidence=candidate.get('evidence_source') or 'historical provenance unknown'
        candidate['sentence']=f"Saved result · run {candidate['run_id']} · {evidence}. "+(candidate.get('sentence') or '')
        renderer=Path(__file__).with_name('service.py').read_bytes()+Path(review_media.__file__).read_bytes()
        key=hashlib.sha256(encode(candidate).encode()+renderer).hexdigest()
        target=self.catalog.path.parent/'derived'/'summary'/f'{key}.png'
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            result=review_media.summary_figure(candidate,target,corpus_root=target.parent)
            if result.get('error'): raise ValueError(result['error'])
        if not target.is_file(): raise FileNotFoundError('Summary rendering did not produce an image')
        return {'png':str(target)}

    def handle(self,method,args):
        self.last_active=time.monotonic()
        # The shared-storage rollback accepts the progressively loaded UI too.
        method={'image_status':'status','item_core':'item','item_details':'item'}.get(method,method)
        if method in ('status','sync'):
            if method=='sync': self.wake.set()
            return self.catalog.status()
        if method=='text_regions':
            from ..image_plugin import load as _image_load
            return _image_load("review_workbench.text_regions").read(self, args)
        if method=='job_status': return self.job_status(args.get('job'))
        if method=='review_filter_start':
            return self.start_job('review_filter',lambda progress:self.handle('review_filter',args))
        if method=='roots': return {'roots':self.catalog.roots()}
        if method=='register_root':
            result=self.catalog.register_root(args['project'],args['path']); self.local_wake.set(); return result
        if method=='map_paper':
            result=self.catalog.map_paper(args['project'],args['dir'],args['path']); self.local_wake.set(); return result
        if method=='register_file':
            result={'path':self.catalog.register_file(args['path'],args['sha256'])}; self.local_wake.set(); return result
        if method=='import_index':
            result=self.catalog.import_index(args['path']); self.wake.set(); return result
        if method=='summary': return self.summary(args)
        if method in ('video_generate','video_status'): return self.image_video(method,args)
        if method=='reveal_target': return self.reveal_target(args)
        if method=='artifact':
            source=self.artifact(args)
            return self._thumbnails().lookup(source) if args.get('variant')=='thumbnail' else source
        if method=='thumbnail': return self._thumbnails().generate(self.artifact(args))
        if method=='source': return self.source(args)
        if method=='issue_detail': return self.issue_detail(args)
        if method in ('item','item_diagnostics'): return self.image_item(method,args)
        if method=='sheet':
            from ..finding_files import read_sheet
            resolved=self.artifact(args); p=Path(resolved['path']); name=Path(resolved['record']['name']).name
            # Readers choose format from the suffix, while archived filenames are hashes.
            if not resolved.get('sha256'):
                return read_sheet(p,args.get('sheet') or None,args.get('highlights') or [])
            dest=self.catalog.path.parent/'derived'/resolved['sha256']/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():
                from ..atomicio import scratch_sibling
                temp=scratch_sibling(dest,'sheet','.tmp')
                try:
                    shutil.copyfile(p,temp)
                    temp.replace(dest)
                finally: temp.unlink(missing_ok=True)
            return read_sheet(dest,args.get('sheet') or None,args.get('highlights') or [])
        if method=='projects': return self.projects()
        if method in ('project_done','project_delete_plan','project_delete','project_delete_jobs'):
            from . import project_admin
            if method=='project_done': return project_admin.mark_done(self.catalog,args.get('project'),args.get('done',True))
            if method=='project_delete_plan': return project_admin.delete_plan(self.catalog,args.get('project'),args.get('protected') or [])
            if method=='project_delete_jobs': return project_admin.jobs()
            return project_admin.start_delete(self.catalog,args.get('project'),args.get('confirm'),args.get('protected') or [])
        if method=='runs':
            return self.repo.run_history(args['project'],args.get('component'),**{k:v for k,v in args.items() if k not in ('project','component')})
        with self.projection:
            self.repo.refresh(args.get('project',''), args.get('run') or 'latest', args.get('component'))
            if method=='findings': return self.repo.findings_page(args)
            if method=='papers': return self.repo.papers_page(args)
            if method in SHARED_QUEUE_METHODS: return self.shared_image_queue(method,args)
            if method=='paper': return self.paper(args)
            if method=='review':
                result=self.repo.save_review(args); self.wake.set(); return result
            if method=='review_filter':
                result=self.repo.save_review_filter(args); self.wake.set(); return result
            if method=='viewed':
                p=self.repo.resolve_paper(args['project'],args.get('slug',''),args.get('dir',''))
                event={'viewer':args.get('viewer'),'at':now()}
                with self.catalog.lock,self.catalog.db:
                    old=self.catalog.db.execute('select body from visits where project=? and dir=?',[args['project'],p.get('dir')]).fetchone()
                    previous=json.loads(old[0]) if old else {}
                    event.update(first_at=previous.get('first_at') or previous.get('at') or event['at'],
                                 n_views=previous.get('n_views',1 if previous else 0)+1,
                                 viewers=list(dict.fromkeys([*previous.get('viewers',[previous.get('viewer')] if previous.get('viewer') else []),*([event['viewer']] if event['viewer'] else [])])))
                    self.catalog.db.execute('insert or replace into visits values(?,?,?)',[args['project'],p.get('dir'),encode(event)])
                return event
        raise ValueError('Unknown workbench method')


class Dispatcher:
    """JSON-lines requests onto bounded pools, with cancellation of queued work.

    `{"method": "cancel", "params": {"id": N}}` withdraws request N if no
    worker has started it; a request already running finishes (its answer is
    ignored by the bridge). The bridge sends it when the browser goes away or
    its timer fires: two detail workers otherwise worked through every item a
    reviewer skimmed past with j/k before reaching the one on screen. A
    withdrawn request still gets one answer, an error naming the withdrawal,
    so the protocol stays one response per request.
    """
    POOLS=dict(read=4,source=2,detail=2,media=4,thumbnail=2)

    def __init__(self, service, output):
        self.service=service; self.output=output; self.write_lock=threading.Lock()
        self.pools={name:ThreadPoolExecutor(max_workers=n,thread_name_prefix=name) for name,n in self.POOLS.items()}
        self.queued=set(); self.cancelled=set(); self.queue_lock=threading.Lock()

    @staticmethod
    def pool_for(method):
        if method=='thumbnail': return 'thumbnail'
        if method in ('artifact','reveal_target'): return 'media'
        if method in ('item','item_core','item_details','issue_detail','video_status'): return 'detail'
        if method in ('source','item_diagnostics','sheet','register_file','summary','video_generate','project_delete_plan','project_delete','review_filter_job'): return 'source'
        return 'read'

    def write(self, payload):
        with self.write_lock: print(payload,file=self.output,flush=True)

    def dispatch(self, line):
        try:
            request=json.loads(line)
            method=request.get('method')
            if method=='cancel':
                target=(request.get('params') or {}).get('id')
                with self.queue_lock:
                    if target in self.queued: self.cancelled.add(target)
                return
            with self.queue_lock: self.queued.add(request.get('id'))
            self.pools[self.pool_for(method)].submit(self.answer,request,time.perf_counter())
        except (ValueError,TypeError,AttributeError) as exc:
            self.write(encode({'id':None,'error':str(exc)}))

    def answer(self, request, submitted):
        rid=request.get('id')
        with self.queue_lock:
            self.queued.discard(rid)
            withdrawn=rid in self.cancelled
            self.cancelled.discard(rid)
        if withdrawn:
            self.write(encode({'id':rid,'error':'CancelledError: withdrawn by the caller before it started','cancelled':True}))
            return
        start=time.perf_counter()
        self.service.last_active=time.monotonic()
        timings={'queue':(start-submitted)*1000}; token=current.set(timings)
        try: result={'id':rid,'result':self.service.handle(request['method'],request.get('params') or {})}
        except Exception as exc: result={'id':rid,'error':f'{type(exc).__name__}: {exc}'}
        result['milliseconds']=round((time.perf_counter()-start)*1000,2)
        with measure('serialization'): payload=encode(result)
        payload=payload[:-1]+', "timings": '+encode({k:round(v,2) for k,v in timings.items()})+'}'
        current.reset(token)
        self.write(payload)

    def shutdown(self):
        for pool in self.pools.values(): pool.shutdown(wait=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--migrate',action='store_true')
    parser.add_argument('--sync',action='store_true')
    parser.add_argument('--index')
    parser.add_argument('--db')
    parser.add_argument('--images-local',action='store_true')
    args=parser.parse_args()
    if args.images_local:
        from ..image_plugin import INSTALL_HINT, available
        if not available():
            parser.error(f"--images-local: {INSTALL_HINT}")
        from .image_review_host import load as load_review
        ImageCatalog = load_review("local_images").ImageCatalog
        _local_service = load_review("local_image_service")
        LocalImageService, Offline = _local_service.LocalImageService, _local_service.Offline
        catalog=ImageCatalog(args.db); remote=Offline()
    else:
        catalog=Catalog(args.db); remote=Remote()
    if args.migrate:
        from .image_cleanup import migrate as migrate_reset
        remote.migrate(); migrate_reset(remote.connect())
        print(encode({'migrations':['004_workbench','005_image_retirement','006_image_reset'],'applied':True})); remote.close(); return
    if args.sync:
        if args.index: catalog.import_index(args.index)
        remote.sync(catalog); catalog.set_state('sync_error',None); catalog.set_state('bytes_received',remote.bytes); print(encode(catalog.status())); remote.close(); return
    protocol_output=sys.stdout
    sys.stdout=sys.stderr
    service=LocalImageService(catalog) if args.images_local else Service(catalog,remote,args.index)
    dispatcher=Dispatcher(service,protocol_output)
    try:
        for line in sys.stdin:
            dispatcher.dispatch(line)
    except KeyboardInterrupt:
        pass  # Ctrl-C on the parent dev server: shut down like an EOF, without a traceback.
    finally:
        service.stop.set(); service.wake.set()
        service.local_wake.set()  # the image reconcile thread sleeps on this for 5 s at a time
        service.videos.close()
        dispatcher.shutdown()
        # Both are daemon threads and check `stop`; the timeouts are a bound,
        # not the mechanism, so a stuck pass cannot keep the process alive.
        if service.thread: service.thread.join(timeout=10)
        if service.local_thread: service.local_thread.join(timeout=3)
        service.remote.close()
        if service.detail_remote is not service.remote: service.detail_remote.close()
        # A file/ingest pass still running holds an open transaction; the WAL
        # discards it at exit, whereas closing its connection under it does not.
        if not (service.local_thread and service.local_thread.is_alive()): catalog.close()
        # Everything is closed; interpreter finalisation would now spend
        # seconds collecting the index's object graph for nothing.
        for stream in (protocol_output, sys.stderr):
            try: stream.flush()
            except OSError: pass
        os._exit(0)


if __name__=='__main__': main()
