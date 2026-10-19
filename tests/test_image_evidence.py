"""Regressions for real image-identity failures, through their consumers."""
import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from metascience_observatory_image_analysis.image_forensics import evidence as E, screening as S
from forensic_metascience_ai_toolkit import adjudicate as A
from metascience_observatory_image_analysis import image_review as IR


@pytest.fixture
def paper(tmp_path):
    import fitz
    from PIL import Image
    p = tmp_path / "10.1--identity"
    (p / "panels").mkdir(parents=True)
    image = Image.new("RGB", (200, 100), "navy")
    data = io.BytesIO()
    image.save(data, format="PNG")
    image.save(p / "panels/parent.png")
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    xref = page.insert_image(fitz.Rect(100, 100, 500, 300), stream=data.getvalue())
    page.insert_image(fitz.Rect(100, 400, 500, 600), xref=xref)
    page.insert_text((108, 120), "A", fontsize=12)
    page.insert_text((308, 120), "B", fontsize=12)
    page.set_rotation(90)
    doc.save(p / (p.name + ".pdf"))
    doc.close()
    uid = f"{p.name}.pdf:xref{xref}"
    records = [{"uid": uid, "doc": p.name+".pdf", "doc_role": "main",
                "acquisition": "embedded_stream", "image_path": str(p/"panels/parent.png")}]
    for n, box in enumerate(([0, 0, 100, 100], [0, 100, 100, 200]), 1):
        crop_uid = uid+f"-seg{n}"
        image.crop((box[1], box[0], box[3], box[2])).save(p / f"panels/crop{n}.png")
        records.append({"uid": crop_uid, "doc": p.name+".pdf", "doc_role": "main",
                        "acquisition": "crop_segment", "crop_box": box,
                        "parent_panel_id": f"xref{xref}"})
    (p / "panels/panel_index.json").write_text(json.dumps({"panels": records}))
    (p / "metadata.json").write_text(json.dumps({"doi": "10.1/identity"}))
    return p, uid


def panel(p, uid, number=1, bbox=None):
    return {"paper_dir": p.name, "uid": uid+f"-seg{number}", "image": f"panels/crop{number}.png",
            "figure_label": "Fig. 1", "caption": "Distinct treatments.",
            "placements": [{"page": 1, "bbox": bbox or [100, 100, 500, 300],
                             "figure_label": "Figure 1", "note": "parent stream",
                             "mirrored": False, "rotation_deg": 0}]}


def test_real_failure_segment_targets_are_crops_not_identical_parents(paper):
    p, uid = paper
    panels = [E.enrich_panel(p, panel(p, uid, n)) for n in (1, 2)]
    boxes = [x["placements"][0]["bbox"] for x in panels]
    assert boxes == [[100, 100, 300, 300], [300, 100, 500, 300]]
    assert all(x["placements"][0]["parent_bbox"] == [100, 100, 500, 300] for x in panels)
    assert [x["subfigure"]["normalized"] for x in panels] == ["A", "B"]
    targets = IR._targets("within:test:IMGDUP-1", panels)
    assert targets[0]["boxes"][0]["x1"] == 700
    assert targets[0]["boxes"][0]["y0"] == 100
    assert targets[1]["boxes"][0]["y0"] == 300
    assert targets[0]["document_path"] == p.name+".pdf"
    assert panels[0]["placements"][0]["page_rotation"] == 90
    assert panels[0]["placements"][0]["coordinate_system"] == "pymupdf_unrotated_points"


@pytest.mark.parametrize("matrix,expected", [
    ([-400, 0, 0, 200, 500, 100], [300, 100, 500, 300]),
    ([0, 400, -200, 0, 300, 100], [100, 100, 300, 300]),
    ([400, 40, 20, 200, 100, 100], [100, 100, 320, 320]),
])
def test_crop_affine_reflection_rotation_shear(matrix, expected):
    assert E._bounds(E.crop_polygon([0, 0, 100, 100], (200, 100), matrix)) == expected


def test_all_repeated_placements_preserved(paper):
    p, uid = paper
    x = panel(p, uid)
    x["placements"][0]["bbox"] = None
    result = E.enrich_panel(p, x)
    assert [q["bbox"][1] for q in result["placements"]] == [100, 400]
    assert len(IR._targets("item", [result])) == 2


def test_tier_one_list_placements_need_no_panel_id():
    group = {"panels": ["p.pdf:xref1"], "placements": [
        {"page": 1, "bbox": [1, 2, 3, 4], "note": "visible"},
        {"page": 3, "bbox": [1, 2, 3, 4]}]}
    assert len(IR._placements_of(group, "p.pdf:xref1")) == 2
    assert IR._placements_of(group, "p.pdf:xref1")[0]["note"] == "visible"


def test_unrecoverable_crop_is_explicitly_approximate(paper):
    p, uid = paper
    (p / (p.name + ".pdf")).unlink()
    x = E.enrich_panel(p, panel(p, uid))
    assert x["placements"][0]["bbox_kind"] == "parent_approximate"
    assert x["placements"][0]["crop_bbox"] is None
    assert x["placements"][0]["geometry_gap"]
    assert x["subfigure"]["normalized"] is None


@pytest.mark.parametrize("raw,want", [("A", "A"), ("A'", "A′"), ("A′", "A′"),
                                     ("A’", "A′"), ("A″", "A′′"), ("A=", None)])
def test_prime_identity_never_silently_changes_equals(raw, want):
    assert E.normalise_subletter(raw) == want


@pytest.mark.parametrize("count", [1, 2, 3])
def test_page_bbox_caption_and_document_changes_invalidate_every_cardinality(tmp_path, count):
    item = {"id": "test", "panels": [{"paper_dir": "paper", "uid": str(n),
             "image": "x.png", "placements": [{"page": 1, "bbox": [1, 2, 3, 4]}]}
             for n in range(count)]}
    stamp = S.input_stamp(tmp_path, item)
    for field, value in (("page", 2), ("bbox", [2, 3, 4, 5]), ("figure_label", "Fig. S1")):
        changed = deepcopy(item)
        changed["panels"][0]["placements"][0][field] = value
        assert S.input_stamp(tmp_path, changed) != stamp
    for field, value in (("caption_source", "changed"), ("subfigure", {"raw": "A′"}),
                         ("document", {"path": "supplements/si.pdf"}), ("parent_uid", "other")):
        changed = deepcopy(item)
        changed["panels"][0][field] = value
        assert S.input_stamp(tmp_path, changed) != stamp


@pytest.mark.parametrize("relative", ["article.html", "pmc_figures/manifest.json",
    "publisher_figures/manifest.json", "supplements/table.docx",
    "supplementary/figure.pdf", "panels/panel_index.json", "paper_images.json"])
def test_new_source_files_invalidate_cached_screen(tmp_path, relative):
    item = {"id": "test", "panels": [{"paper_dir": "paper", "uid": "x", "image": "x.png"}]}
    old = S.input_stamp(tmp_path, item)
    path = tmp_path / "paper" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("new")
    assert S.input_stamp(tmp_path, item) != old


def test_main_and_supplement_caption_never_collide(paper, monkeypatch):
    p, uid = paper
    rec = json.loads((p/"panels/panel_index.json").read_text())
    rec["panels"][1].update(doc="supplements/si.pdf", doc_role="supplement")
    (p/"panels/panel_index.json").write_text(json.dumps(rec))
    (p/"supplements").mkdir()
    (p/"supplements/si.pdf").write_bytes((p/(p.name+".pdf")).read_bytes())
    monkeypatch.setattr(E, "_supplement_captions", lambda _: (
        {"Figure 1": ("SI-specific treatment caption.", 1)}, "read"))
    si = E.enrich_panel(p, panel(p, uid))
    main = E.enrich_panel(p, panel(p, uid, 2))
    assert si["caption"] == "SI-specific treatment caption."
    assert si["caption_key"] != main["caption_key"]
    assert E.scope("paperA", "main.pdf", "Figure 1") != E.scope("paperB", "main.pdf", "Figure 1")
    assert E.scope("paperA", "main.pdf", "Figure 1") != E.scope("paperA", "main.pdf", "Figure S1")


def test_figure_mentions_cannot_cross_document_numbering(tmp_path):
    paper = tmp_path/'paper'
    paper.mkdir()
    pdf = paper/'paper.pdf'
    xml = paper/'paper.xml'
    pdf.write_bytes(b'pdf')
    xml.write_text('<article/>')
    summary = {
        'mentions': {'Figure 1': [
            {'sentence': 'PDF mention.', 'path': str(pdf)},
            {'sentence': 'Accepted-manuscript mention.', 'path': str(xml)},
        ]},
        'methods': {'text': 'Shared methods.', 'path': str(xml)},
        'gaps': [],
    }
    scoped = E._document_text_context(
        summary, paper, {'path': 'paper.pdf', 'role': 'main'})
    assert [m['sentence'] for m in scoped['mentions']['Figure 1']] == ['PDF mention.']
    assert scoped['methods']['path'] == str(xml)  # shared, but provenance-labelled
    assert '1 figure-citation mention(s)' in scoped['gaps'][0]


def _message(path, n=1, image=True):
    return [{"message": {"content": [{"type": "tool_use", "name": "Read", "id": str(n),
              "input": {"file_path": str(path)}}]}},
            {"message": {"content": [{"type": "tool_result", "tool_use_id": str(n),
              "content": [{"type": "image" if image else "text"}]}]}}]


def test_parent_context_delivery_is_required_not_just_panel_files(tmp_path):
    a, full = tmp_path/"a.png", tmp_path/"full.png"
    a.write_bytes(b"a"); full.write_bytes(b"parent")
    packet = {"panels": [{"uid": "a", "path": str(a)}], "figures": [{"path": str(full)}]}
    packet["attachments"] = E.attachments(packet)
    assert not E.delivery(packet, {"messages": _message(a)}, "claude")["complete"]
    assert not E.delivery(packet, {"messages": _message(a)+_message(full, 2, False)}, "claude")["complete"]
    assert E.delivery(packet, {"messages": _message(a)+_message(full, 2)}, "claude")["complete"]
    assert E.delivery(packet, {}, "codex")["complete"]
    full.write_bytes(b"changed")
    assert not E.delivery(packet, {}, "codex")["complete"]


def test_deduplicated_attachment_manifest_matches_actual_command(tmp_path):
    a = tmp_path/"a.png"; a.write_bytes(b"a")
    packet = {"panels": [{"uid": "a", "path": str(a)}], "figures": [{"path": str(a)}]}
    packet["attachments"] = E.attachments(packet)
    cmd = SimpleNamespace(argv=[])
    E.attach_to_command(cmd, packet, "codex")
    assert cmd.argv == ["--image", str(a)]
    assert len(packet["attachments"][0]["roles"]) == 2


def test_clone_packet_delivers_two_regions_and_an_overview(tmp_path):
    from PIL import Image
    from metascience_observatory_image_analysis.image_forensics.screening_visuals import local_regions
    path = tmp_path / "panel.png"
    Image.new("RGB", (120, 90), "gray").save(path)
    packet = {
        "detector_kind": "intra_panel_clone",
        "panels": [{"uid": "panel-1", "path": str(path), "sha256": E.file_hash(path),
                    "document": {"id": "main"}}],
        "measurements": {"regions": [
            {"role": "source", "bbox": [5, 10, 35, 40]},
            {"role": "copy", "bbox": [70, 45, 100, 75]},
        ]},
    }
    localized = local_regions(packet, tmp_path / "media")
    assert localized["type"] == "within_panel_regions"
    assert [r["candidate"] for r in localized["regions"]] == ["A", "B"]
    assert [r["bbox"] for r in localized["regions"]] == [[5, 10, 35, 40],
                                                          [70, 45, 100, 75]]
    assert [Path(x["path"]).name for x in localized["images"]] == [
        "clone_region_a.png", "clone_region_b.png", "clone_overview.png"]
    packet["localized_comparison"] = localized
    roles = [role for attachment in E.attachments(packet) for role in attachment["roles"]]
    assert {r["role"] for r in roles} >= {
        "clone_region_a", "clone_region_b", "clone_overview"}


def test_clone_only_contract_changes_do_not_stale_pair_v4(tmp_path, monkeypatch):
    pair = {"id": "pair", "panels": [{"paper_dir": "p", "uid": "a", "image": "a.png"},
                                        {"paper_dir": "p", "uid": "b", "image": "b.png"}]}
    clone = {"id": "clone", "detector_kind": "intra_panel_clone",
             "panels": [{"paper_dir": "p", "uid": "a", "image": "a.png"}],
             "measurements": {"regions": [{"bbox": [1, 2, 3, 4]},
                                               {"bbox": [5, 6, 7, 8]}]}}
    pair_stamp, clone_stamp = S.input_stamp(tmp_path, pair), S.input_stamp(tmp_path, clone)
    monkeypatch.setattr(S, "CLONE_SYSTEM", S.CLONE_SYSTEM + "\nclone-only revision")
    assert S.input_stamp(tmp_path, pair) == pair_stamp
    assert S.input_stamp(tmp_path, clone) != clone_stamp


def test_shared_adjudicator_receives_full_rationale_and_cannot_override_without_images(tmp_path):
    from tests.test_adjudicate import finding, verdict
    from metascience_observatory_image_analysis.image_forensics.screening_reconcile import screening_fields
    ref = E.persist_packet(tmp_path, {"id": "pair", "schema": E.VERSION, "attachments": []})
    _, info = screening_fields({"explanation": "full explanation "*100, "fingerprint": "x",
                               "decision": "issue", "confidence": "high", "evidence_packet": ref})
    f = finding("IMGDUP-1", producer="image_track", inputs={"ai_screening": info})
    assert A._docket_row(f)["ai_screening"]["explanation"].endswith("full explanation ")
    bundle = E.adjudication_bundle([f])
    assert bundle["by_finding"] == {"IMGDUP-1": ref["sha256"]}
    output, counts = A.apply([f], {"verdicts": [verdict("IMGDUP-1", action="discarded")]})
    assert output[0]["severity_is_provisional"]
    assert counts["n_image_delivery_withheld"] == 1
    Path(ref["path"]).write_text("{}")
    assert E.adjudication_bundle([f])["errors"]["IMGDUP-1"]


def test_visual_readings_must_reference_correct_placement_and_preserve_prime(tmp_path):
    from tests.test_mandatory_image_screening import answer
    p = {"uid": "u", "document": {"id": "main"}, "caption": "Different treatments",
         "placements": [{"page": 5}]}
    pkt = {"schema": E.VERSION, "panels": [p], "attachments": [
        {"id": "attachment-1", "roles": [{"role": "candidate", "uid": "u", "document_id": "main"}]}]}
    r = {"uid": "u", "placement_index": 0, "document_id": "main", "page": 5,
         "figure_raw": "Figure 2", "subfigure_raw": "A'", "subfigure_normalized": "A′",
         "status": "observed", "attachment_id": "attachment-1", "context_text": "GFP"}
    a = dict(answer(), panel_readings=[r])
    assert S.validate(a, pkt, True)["validated"]
    r["subfigure_normalized"] = "A"
    assert not S.validate(a, pkt, True)["validated"]
    r.update(subfigure_normalized="A′", page=6)
    assert not S.validate(a, pkt, True)["validated"]
    assert not S.validate(answer(), pkt, True)["validated"]


def test_publisher_figure_retains_identity_without_inventing_page(tmp_path):
    p = tmp_path/"paper"; (p/"panels").mkdir(parents=True); (p/"pmc_figures").mkdir()
    uid = "pmc_figures:pmc:F1.png"
    rec = {"uid": uid, "doc": "pmc_figures", "doc_role": "pmc_render",
           "figure_labels": ["Figure 1"], "placements": [
               {"page": None, "figure_label": "Figure 1", "bbox": None}]}
    (p/"panels/panel_index.json").write_text(json.dumps({"panels": [rec]}))
    (p/"pmc_figures/manifest.json").write_text(json.dumps({"figures": []}))
    pls = IR._placements_of({"panels": [uid], "placements": {uid: rec["placements"]}}, uid)
    result = E.enrich_panel(p, {"uid": uid, "paper_dir": p.name, "placements": pls})
    assert result["figure_label"] == "Figure 1"
    assert result["document"]["path"] == "pmc_figures/manifest.json"
    assert result["placements"][0]["page"] is None
    assert IR._targets("item", [result]) == []


def test_source_stream_replacement_cannot_reuse_old_crop_location(paper):
    p, uid = paper
    path = p/"panels/panel_index.json"
    index = json.loads(path.read_text())
    index["panels"][0]["content_sha256"] = "different-source"
    path.write_text(json.dumps(index))
    result = E.enrich_panel(p, panel(p, uid))
    assert result["source_identity_status"] == "mismatch"
    assert result["placements"][0]["bbox_kind"] == "parent_approximate"
    from tests.test_mandatory_image_screening import answer
    assert not S.validate(answer(), {"panels": [result]}, True)["validated"]


@pytest.mark.parametrize("backend,read_parent,valid", [
    ("codex", False, True), ("claude", False, False), ("claude", True, True),
    ("grok", False, False), ("grok", True, True)])
def test_real_judge_command_and_prompt_deliver_context(tmp_path, monkeypatch, backend, read_parent, valid):
    from metascience_observatory_image_analysis import runtime as agent
    from tests.test_mandatory_image_screening import answer
    a, b, parent = [tmp_path/f"{n}.png" for n in ("a", "b", "parent")]
    for f in (a, b, parent):
        f.write_bytes(f.name.encode())
    packet = {"panels": [{"uid": f.name, "path": str(f), "sha256": E.file_hash(f),
                          "caption": "Different treatments"} for f in (a, b)],
              "figures": [{"path": str(parent)}]}
    packet["attachments"] = E.attachments(packet)
    seen = {}
    def build(**kw):
        seen["build"] = kw
        return SimpleNamespace(argv=[])
    async def run(cmd, prompt, **kwargs):
        seen["cmd"], seen["prompt"] = cmd.argv, json.loads(prompt)
        return {"messages": _message(a)+_message(b, 2)+(_message(parent, 3) if read_parent else [])}
    monkeypatch.setattr(agent, "_build_claude_cmd", build)
    monkeypatch.setattr(agent, "_run_stage", run)
    monkeypatch.setattr(agent, "_extract_json", lambda stage: (answer(), "test"))
    result = asyncio.run(S.judge(packet, backend, "test-model"))
    assert result["validated"] is valid
    assert seen["build"]["vision"]
    assert seen["prompt"]["attachments"] == packet["attachments"]
    if backend == "codex":
        assert seen["cmd"] == sum((["--image", str(f)] for f in (a, b, parent)), [])


def test_grok_readfile_imagecontent_receipt_from_live_failure(tmp_path):
    import base64
    from PIL import Image
    path = tmp_path/"panel.png"
    Image.new("RGB", (4, 4), "red").save(path)
    events = [{"message": {"content": [
        {"type": "tool_use", "id": "g", "name": "Read", "grok_meta_tool": "read_file",
         "input": {"target_file": str(path)}}]}},
        {"message": {"content": [{"type": "tool_result", "tool_use_id": "g", "is_error": False,
          "content": json.dumps({"type": "ReadFile", "ImageContent": {
              "data": base64.b64encode(path.read_bytes()).decode(), "mime_type": "image/png"}})}]}}]
    assert S.delivered_images(events) == {str(path)}
    block = events[1]["message"]["content"][0]
    block["is_error"] = True
    assert not S.delivered_images(events)
    block["is_error"] = False
    block["content"] = json.dumps({"type": "ReadFile", "TextContent": "I read the image"})
    assert not S.delivered_images(events)
    block["content"] = json.dumps({"type": "ReadFile", "ImageContent": {
        "data": base64.b64encode(b"not pixels").decode(), "mime_type": "image/png"}})
    assert not S.delivered_images(events)


@pytest.mark.parametrize("context_read", [True, False])
def test_legacy_adjudicator_consumes_same_packet_and_enforces_delivery(paper, monkeypatch, context_read):
    from metascience_observatory_image_analysis import legacy_adjudication as agent
    p, uid = paper
    item = {"id": "within:test:IMGDUP-1", "panels": [panel(p, uid, n) for n in (1, 2)]}
    monkeypatch.setattr(IR, "_within_items", lambda *a, **k: [item])
    monkeypatch.setattr(agent, "_build_claude_cmd", lambda **k: SimpleNamespace(argv=[]))
    monkeypatch.setattr(agent, "_extract_json", lambda s: (
        {"verdicts": [{"group_index": 1, "verdict": "unexplained"}]}, "fixture"))
    captured = {}
    async def run(cmd, prompt, **kw):
        packet = json.loads(prompt.split("\n", 1)[1])[0]["evidence_packet"]
        captured.update(packet)
        assets = packet["attachments"]
        if not context_read:
            assets = [a for a in assets if any(r["role"] == "candidate" for r in a["roles"])]
        return {"messages": sum((_message(a["path"], i) for i, a in enumerate(assets)), [])}
    monkeypatch.setattr(agent, "_run_stage", run)
    stage = asyncio.run(agent._run_image_adjudication(
        {"output": {"result": {"duplicate_groups": [{"panels": [uid+"-seg1", uid+"-seg2"],
            "figure_labels": ["Figure 1"], "duplication_evidence": True}]}}},
        p, model="sonnet", effort="medium", backend="claude"))
    assert captured["schema"] == E.VERSION
    assert len(captured["panels"][0]["placements"]) == 1
    assert stage["image_delivery"][1]["complete"] is context_read
    assert len(stage["adjudication"]["verdicts"]) == int(context_read)


def test_lost_prime_quote_is_normalized_only_with_observed_label():
    from tests.test_mandatory_image_screening import answer
    p = {"uid": "u", "document": {"id": "main"}, "caption":
         "Jarid2 overexpression is confirmed with an antibody (A=, arrow).",
         "placements": [{"page": 5}]}
    pkt = {"schema": E.VERSION, "panels": [p], "attachments": [
        {"id": "a", "roles": [{"role": "candidate", "uid": "u", "document_id": "main"}]}]}
    a = dict(answer("innocuous"), category="caption_explained", evidence_quote=
             "Jarid2 overexpression is confirmed with an antibody (A′, arrow).",
             panel_readings=[{"uid": "u", "placement_index": 0, "document_id": "main", "page": 5,
              "figure_raw": "2", "subfigure_raw": "A′", "subfigure_normalized": "A′",
              "status": "observed", "attachment_id": "a", "context_text": "antibody-only"}])
    result = S.validate(a, pkt, True)
    assert result["validated"]
    assert result["quote_normalizations"][0]["raw_token"] == "A="
    assert p["caption"].endswith("(A=, arrow).")  # source was not rewritten
    assert not S.validate(a, pkt, False)["validated"]
    a["panel_readings"][0].update(subfigure_raw="A", subfigure_normalized="A")
    assert not S.validate(a, pkt, True)["validated"]
    a["panel_readings"][0].update(subfigure_raw="A′", subfigure_normalized="A′")
    p["caption"] = "Jarid2 overexpression is confirmed with an antibody (A=5, arrow)."
    assert not S.validate(a, pkt, True)["validated"]


def test_native_parent_context_marks_crop_in_correct_pixel_frame(paper):
    from PIL import Image
    p, uid = paper
    x = E.enrich_panel(p, panel(p, uid))
    rec = E._parent_locator(p.parent, p, x)
    with Image.open(rec["path"]) as im:
        assert im.getpixel((100, 50)) == (255, 0, 0)  # crop's right edge
        assert im.getpixel((150, 50)) == (0, 0, 128)  # outside crop is unchanged
    assert rec["crop_polygon_pixels"] == [[0, 0], [100, 0], [100, 100], [0, 100]]


def test_observed_label_cannot_borrow_another_document_figure_or_placement():
    from tests.test_mandatory_image_screening import answer
    panel = {"uid": "shared-native-id", "document": {"id": "paperA"}, "figure_label": "Figure 2",
             "placements": [{"page": 5}], "caption": "Different treatments"}
    role = {"role": "candidate", "uid": panel["uid"], "document_id": "paperB"}
    packet = {"schema": E.VERSION, "panels": [panel], "attachments": [{"id": "a", "roles": [role]}]}
    a = dict(answer(), panel_readings=[{"uid": panel["uid"], "placement_index": 0,
        "document_id": "paperA", "page": 5, "figure_raw": "2", "subfigure_raw": "A",
        "subfigure_normalized": "A", "status": "observed", "attachment_id": "a", "context_text": "GFP"}])
    assert not S.validate(a, packet, True)["validated"]
    role.update(role="full_figure", document_id="paperA", label="Figure 3")
    assert not S.validate(a, packet, True)["validated"]
    role["label"] = "Figure 2"
    assert S.validate(a, packet, True)["validated"]
    role.update(role="placement_context", page=5, placement_index=1)
    assert not S.validate(a, packet, True)["validated"]
    role["placement_index"] = 0
    assert S.validate(a, packet, True)["validated"]


def test_separate_caption_page_is_delivered(paper, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import figure_context as F
    p, uid = paper
    monkeypatch.setattr(F, "resolve_document_captions", lambda *a, **k: ({
        "Figure 1": F.CaptionRecord("Figure 1", "Complete caption",
                                      "source_document_pdf", str(p/(p.name+".pdf")), 1)},
                                      ["source PDF: 1 caption"]))
    item = {"id": "example", "panels": [panel(p, uid)]}
    item["panels"][0]["placements"][0]["page"] = 2  # source placement missing; caption still viewable
    packet = E.prepare_visuals(p.parent, E.build_packet(p.parent, item, ocr=False))
    asset = next(a for a in packet["attachments"] if any(r["role"] == "caption_context" for r in a["roles"]))
    assert Path(asset["path"]).is_file()
    assert asset["roles"][0]["page"] == 1
    assert not E.delivery(packet, {"messages": []}, "grok")["complete"]


@pytest.mark.parametrize("raw, kind, normalized", [
    ("a", "subletter", "a"), ("(a)", "subletter", "a"), ("a)", "subletter", "a"),
    ("A'", "subletter", "A′"), ("A′′", "subletter", "A′′"), ("[B]", "subletter", "B"),
    ("ii", "roman", "ii"), ("(iv)", "roman", "iv"), ("VII", "roman", "vii"),
    ("2a", "alnum", "2a"), ("A2", "alnum", "a2"), ("(1b)", "alnum", "1b"),
    ("A*01:01", "allele", "A*01:01"), ("DRB1*04:01", "allele", "DRB1*04:01"),
    ("R444C", "mutation", "R444C"), ("A₂", "subscript", "A2"),
    ("iiii", "none", None), ("Figure", "none", None), ("", "none", None), (None, "none", None),
    ("12", "none", None), ("p<0.05", "none", None),
])
def test_classify_panel_label_names_the_kind_instead_of_dropping_it(raw, kind, normalized):
    """CHANGELOG (the embargoed 2026-09 corpus): `ii`, `2a`, `A*01:01`, `R444C`, `A₂`
    were printed labels that `normalise_subletter` answered None for, and
    None was read as NO label. The narrow function stays narrow; this one
    says what kind of label it is."""
    assert E.classify_panel_label(raw) == {"kind": kind, "normalized": normalized}
    if kind == "subletter":
        assert E.normalise_subletter(raw) == normalized
    elif raw:
        assert E.normalise_subletter(raw) is None  # deliberately unchanged


def test_labels_record_roman_and_alnum_as_candidates_never_observed():
    box = [0, 0, 100, 100]
    word = lambda text, x=10, y=10: [x, y, x + 10, y + 10, text]  # noqa: E731
    only_roman = E._labels([word("ii")], box, "pdf_text")
    assert only_roman["status"] == "candidate" and only_roman["normalized"] == "ii"
    assert only_roman["candidates"][0]["kind"] == "roman"
    only_alnum = E._labels([word("2a")], box, "pdf_text")
    assert only_alnum["status"] == "candidate" and only_alnum["normalized"] == "2a"
    two_kinds = E._labels([word("ii"), word("2a", 50, 50)], box, "pdf_text")
    assert two_kinds["status"] == "ambiguous" and two_kinds["normalized"] is None
    # A subletter still decides, exactly as before, beside a roman numeral.
    letter_and_roman = E._labels([word("A"), word("ii", 50, 50)], box, "pdf_text")
    assert letter_and_roman["status"] == "observed" and letter_and_roman["normalized"] == "A"
    assert [c["kind"] for c in letter_and_roman["candidates"]] == ["subletter", "roman"]
    # Allele/mutation names inside the box are not panel labels.
    assert E._labels([word("R444C"), word("A*01:01", 50, 50)], box, "pdf_text")["status"] == "unresolved"
    # Words outside the box never count, whatever their kind.
    assert E._labels([word("ii", 500, 500)], box, "pdf_text")["status"] == "unresolved"


def test_no_sidecar_adds_exactly_one_named_gap_and_nothing_else(paper):
    p, uid = paper
    out = E.enrich_panel(p, panel(p, uid))
    assert out["identity_gaps"] == ["identity_sidecar_absent"]
    assert "identity_sidecar" not in out
    assert out["placements"][0]["bbox_kind"] == "crop_exact"
    assert all("identity_source" not in pl for pl in out["placements"])
    # A publisher render has no PDF placement to persist, so no gap either.
    q = p.parent / "pmc"
    (q / "panels").mkdir(parents=True); (q / "pmc_figures").mkdir()
    rec = {"uid": "pmc_figures:pmc:F1.png", "doc": "pmc_figures", "doc_role": "pmc_render",
           "figure_labels": ["Figure 1"], "placements": [{"page": None, "figure_label": "Figure 1", "bbox": None}]}
    (q / "panels/panel_index.json").write_text(json.dumps({"panels": [rec]}))
    (q / "pmc_figures/manifest.json").write_text(json.dumps({"figures": []}))
    pmc = E.enrich_panel(q, {"uid": rec["uid"], "paper_dir": q.name, "placements": rec["placements"]})
    assert not any(g.startswith("identity_sidecar") for g in pmc["identity_gaps"])
