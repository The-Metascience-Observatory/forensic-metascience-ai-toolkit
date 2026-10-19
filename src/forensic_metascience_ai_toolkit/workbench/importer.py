"""Reconcile saved archives/reports with the findings database without copying media or reanalysis.

Existing run IDs and sealed content are compared before writes. Only missing runs
are uploaded. Conflicts are reported, not overwritten. Review events are replayed
idempotently with their original timestamp and event ID.
"""
import argparse
import json
from pathlib import Path
from .remote import Remote


def migrate(root, *, dry_run=False, progress=None):
    from ..analysis_runs import Archive,read
    from ..history_db import sync
    from ..db_push import _doc_and_meta,push_run,push_reviews
    from ..webapp_index import iter_paper_dirs,review_dirs
    root=Path(root).resolve();archive=Archive(root);remote=Remote()
    result={'project':root.name,'dry_run':dry_run,'missing_runs':[],'conflicts':[],'errors':[],'reviews':0}
    try:
        conn=remote.connect()
        write_allowed=not dry_run
        known={uid:sha for uid,sha in conn.execute('select run_uid,sealed_digest from runs')}
        missing=[]
        incompatible=set()
        dependencies={}
        def null_character(value):
            if isinstance(value,str): return '\x00' in value
            if isinstance(value,dict): return any(null_character(k) or null_character(v) for k,v in value.items())
            if isinstance(value,list): return any(null_character(v) for v in value)
            return False
        for path in sorted((archive.base/'runs').glob('*.json')):
            r=read(path)
            dependencies[r['id']]=[x for x in (r.get('parent_run_id'),r.get('revision_of')) if x]
            if null_character(r): incompatible.add(r['id'])
            if r['id'] not in known:missing.append(r['id'])
            elif known[r['id']] and known[r['id']]!=r['sealed_digest']:
                result['conflicts'].append(r['id'])
        result['missing_runs']=missing
        while True:
            expanded=incompatible | {uid for uid,parents in dependencies.items() if any(p in incompatible for p in parents)}
            if expanded==incompatible: break
            incompatible=expanded
        for uid in sorted(set(missing)&incompatible):
            result['errors'].append({'run':uid,'error':'Run or required ancestor contains U+0000, which PostgreSQL JSONB cannot preserve. Original archive retained.'})
        missing=[uid for uid in missing if uid not in incompatible]
        if missing and write_allowed:
            # A damaged record must not roll back thousands of unrelated archives.
            # Do not strip characters or alter sealed evidence to satisfy JSONB.
            result['archive']={'runs':0,'items':0,'reviews':0}
            for start in range(0,len(missing),100):
                batch=missing[start:start+100]
                try:
                    outcome=sync(root,conn,batch)
                except Exception:
                    for uid in batch:
                        try:
                            outcome=sync(root,conn,[uid])
                            for key,value in outcome.items():
                                if key in result['archive']: result['archive'][key]+=value
                        except Exception as exc:
                            result['errors'].append({'run':uid,'error':f'{type(exc).__name__}: {exc}'})
                else:
                    for key,value in outcome.items():
                        if key in result['archive']: result['archive'][key]+=value
                if progress: progress({'batch_end':start+len(batch),'eligible_runs':len(missing),'imported':dict(result['archive']),'errors':len(result['errors'])})
        if write_allowed:
            # Reused-only executions can change without adding a sealed run.
            for path in sorted((archive.base/'executions').glob('*.json')):
                execution=read(path)
                refs=json.dumps(execution.get('reused_run_ids',[]))
                conn.execute("""update executions set configuration=jsonb_set(coalesce(configuration,'{}'::jsonb),
                    '{workbench_reused_run_ids}',%s::jsonb) where execution_uid=%s and
                    configuration->'workbench_reused_run_ids' is distinct from %s::jsonb""",[refs,execution['id'],refs])
        reports=[]
        for paper in iter_paper_dirs(root):
            dirs=review_dirs(paper)+[p/'analysis' for p in paper.glob('forensic_review*_bundle') if (p/'analysis').is_dir()]
            for directory in dirs:
                loaded=_doc_and_meta(directory)
                if not loaded:continue
                doc,meta=loaded;uid=doc.get('run_id')
                if not uid:
                    result['errors'].append(f'{directory}: missing stable run ID');continue
                if uid in known or uid in result['missing_runs'] or uid in reports:continue
                reports.append(uid)
                if write_allowed:
                    push_run(conn,doc,meta,paper,root.name,run_name=directory.name)
                    known[uid]=None
            # Existing legacy decision files use the established importer, which
            # reports unscoped/unmatched judgments instead of inventing a target.
            if write_allowed and (paper/'review.json').is_file():
                found=conn.execute('select p.id from papers p join corpora c on p.corpus_id=c.id where c.name=%s and p.dir=%s',[root.name,paper.relative_to(root).as_posix()]).fetchone()
                if found:
                    with conn.transaction():
                        outcome=push_reviews(conn,found[0],paper)
                    result['reviews']+=outcome.get('pushed',0)
                    if outcome.get('unmatched'):result['errors'].append({str(paper):outcome['unmatched']})
        result['missing_reports']=reports
        if write_allowed:
            from ..history_publication import sync as sync_publication
            result['publication']=sync_publication(root,conn)
        events=archive.base/'reviews.jsonl'
        if write_allowed and events.exists():
            for line in events.read_text().splitlines():
                event=json.loads(line)
                remote.send_review(event);result['reviews']+=1
    except Exception as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
    finally:remote.close()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--dry-run',action='store_true')
    args=p.parse_args();result=migrate(args.root,dry_run=args.dry_run)
    result['counts']={'missing_runs':len(result['missing_runs']),'missing_reports':len(result.get('missing_reports',[]))}
    print(json.dumps(result,default=str))

if __name__=='__main__':main()
