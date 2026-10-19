"""Phase 5: one alias table from stored identifiers to display names.

Stored values never change (`tool_expert`/`science_error` are hashed into
every finding_id; `tool_agent`/`science_agent` name archived files). Readers
show people the display name, from `names.py`, derived from MODULE.md.
"""

from metascience_agent import modules
from metascience_agent.names import display, display_names


def test_every_stored_identifier_of_the_two_analysts_maps_to_its_new_name():
    for key in ("tool_expert", "tool_agent", "tools_agent"):
        assert display(key) == "Tools agent"
    for key in ("science_error", "science_agent", "scientific_proofreading_agent"):
        assert display(key) == "Scientific proofreading agent"


def test_it_is_derived_from_the_module_definitions():
    names = display_names()
    for d in modules.definitions().values():
        assert names[d.name] == d.display
        assert names[d.label] in {x.display for x in modules.definitions().values()}


def test_channel_keys_and_unknowns():
    assert display("tortured_phrases").startswith("Text forensics")
    assert display("image_forensics") == "Image analysis"
    assert display("image_track") == "Image analysis"
    assert display("fast_screen") == "fast_screen"         # passes through
    assert display(None) == ""


def test_the_report_shows_the_display_name_and_keeps_the_key():
    from metascience_agent import report_v2
    src = open(report_v2.__file__, encoding="utf-8").read()
    assert "producer: {_display(f.get('producer'))}" in src


def test_the_viewer_maps_every_stage_and_producer_it_shows():
    from metascience_agent import bundle
    src = open(bundle.__file__, encoding="utf-8").read()
    assert "const DN_MAP = __DISPLAY_NAMES__;" in src
    assert "esc(f.producer||'')" not in src and "esc(DN(f.producer||''))" in src
    assert "esc(c.stage)" not in src
