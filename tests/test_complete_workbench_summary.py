"""Complete-run selection and queue fields survive the compact sync boundary."""
from metascience_agent.workbench.remote import summary_expr


def test_cross_batch_selection_family_is_carried_over_sync():
    # Without this field a smaller new execution leaves old tail batches in
    # "latest", even though the full-record local importer behaves correctly.
    sql = summary_expr('runs')
    assert "'selection_family',t.history_record->'selection_family'" in sql


def test_detection_coverage_and_transforms_survive_compact_item_sync():
    sql = summary_expr('component_items')
    assert "'coverage_status',t.record->'coverage_status'" in sql
    for field in ('rotation_deg', 'scale', 'flip'):
        assert f"'{field}',t.record->'measurements'->'{field}'" in sql
