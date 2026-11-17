"""The landing page's per-project counts: papers with RNG findings, and
papers with a PDF or an XML (one count, not two that overlap)."""
import json

from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_detector_queue import catalog  # noqa: F401 -- fixture


def project(r, name='project'):
    return next(p for p in r.projects()['projects'] if p['name'] == name)


def test_rng_track_counts_papers_with_a_kept_rng_row(catalog):
    r = Repository(catalog); r.refresh()
    assert project(r)['n_rng_papers'] == 1  # one paper, three rows


def test_an_rng_run_whose_rows_were_all_discarded_counts_no_paper(catalog):
    catalog.apply_changes([('findings', json.dumps([i]), {
        'id': i, 'run_id': 1, 'paper_id': 1, 'finding_id': f'f_{i}', 'producer': 'rng_track',
        'outcome': 'problem', 'adjudication_action': 'discarded'}) for i in (1, 2, 3)], 2)
    r = Repository(catalog); r.refresh()
    assert project(r)['n_rng_papers'] == 0


def test_pdf_or_xml_counts_each_paper_once(catalog):
    r = Repository(catalog); r.refresh()
    r.local = {('project', 'a'): ({'sources': {'pdf': True, 'xml': True}}, None),
               ('project', 'b'): ({'sources': {'pdf': False, 'xml': True}}, None),
               ('project', 'c'): ({'sources': {'pdf': False, 'xml': False}}, None)}
    row = project(r)
    assert (row['n_pdf'], row['n_xml'], row['n_pdf_or_xml']) == (1, 2, 2)


def test_the_landing_page_projection_counts_rng_papers_without_loading_findings(catalog):
    """The service builds the landing summary from headers only (no findings in
    memory); the count must still come out, not read 0."""
    r = Repository(catalog); r.refresh('', 'latest', None)
    assert r.findings_by_run == {} or not any(r.findings_by_run.values())
    assert project(r)['n_rng_papers'] == 1
