"""A paper with no shared catalog record takes its citation from its folder's
metadata.json, so the project table shows its title, not its folder name."""
import json
import os

from forensic_metascience_ai_toolkit.workbench.repository import local_metadata


def test_reads_citation_fields(tmp_path):
    (tmp_path / 'metadata.json').write_text(json.dumps({
        'title': 'ANKRD62 Modulates NF-kB Signaling', 'authors': 'Chenjun Hao, Yanqiu Li',
        'first_author': 'Chenjun Hao', 'journal': 'Cancer Medicine', 'year': 2026,
        'doi': '10.1002/cam4.71822', 'pages': None, 'authors_list': [{'full': 'x'}]}), encoding='utf-8')
    assert local_metadata(tmp_path) == {
        'title': 'ANKRD62 Modulates NF-kB Signaling', 'authors': 'Chenjun Hao, Yanqiu Li',
        'first_author': 'Chenjun Hao', 'journal': 'Cancer Medicine', 'year': 2026, 'doi': '10.1002/cam4.71822'}


def test_missing_or_broken_file_gives_nothing(tmp_path):
    assert local_metadata(tmp_path) == {}
    assert local_metadata(None) == {}
    (tmp_path / 'metadata.json').write_text('{not json', encoding='utf-8')
    assert local_metadata(tmp_path) == {}


def test_rereads_after_the_file_changes(tmp_path):
    f = tmp_path / 'metadata.json'
    f.write_text(json.dumps({'title': 'Old'}), encoding='utf-8')
    assert local_metadata(tmp_path)['title'] == 'Old'
    f.write_text(json.dumps({'title': 'New'}), encoding='utf-8')
    st = f.stat()
    os.utime(f, (st.st_atime, st.st_mtime + 5))
    assert local_metadata(tmp_path)['title'] == 'New'
