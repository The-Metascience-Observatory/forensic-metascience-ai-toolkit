"""`python -m metascience_agent.scaffold <paper_dir> [options]`

Builds the document layer, runs the three passes and the residual pass, assembles
the account, renders it, and writes everything under `<paper_dir>/scaffold/`:

    document.json      layer 0 (text, sections, tables, figures, repairs, floor)
    body.repaired.md   the text the passes read; body.original.md beside it
    structure.json     the frozen structural account (`structure.py`), with
                       every version kept under structure.versions/<n>.json
    pass1.json ...     each pass's output, prompt, schema, raw CLI result, meta
    account.json       the merged account
    account.md         the human view
    values.csv         one long-form row per value (`export.py`)
    checks.json/.md    the forensic checks run on the account's own premises
                       (`checks.py`) -- free, so it runs on every path
    premise_reading.json  a model's verdict on each candidate sentence offered
                       for a bound / step / estimator / correction premise
                       (`premise_reading.py`); PAID, written only under
                       `--read-premises`, and reused on a later run. Bounded by
                       `--premise-budget` in CANDIDATES, which is the unit that
                       is billed; over budget it stops asking and records which
                       premises and variables it never asked about

Deliberately a module entry point and not a `metascience` verb: the CLI's
tool-exposure ratchets pin every registered command, and this component is not
yet a pipeline stage (2026-09-05).

`--resume` reuses any pass output already on disk, so a run interrupted after
pass 2 does not pay for passes 1 and 2 again. `--no-llm` assembles from what is
on disk and runs nothing.

TABLE READINGS OUTLIVE THIS DIRECTORY. Each one is also written to a
content-addressed store outside every run (`reading_store`,
`~/.cache/metascience/readings`), keyed by what the reading is a reading OF, so
deleting `<paper_dir>/scaffold/` no longer destroys what it cost. The run
directory stays authoritative: a reading in it is the one used, and a store
entry that disagrees is reported rather than applied. A DELIBERATE RE-READ of a
paper (test-retest) must set `METASCIENCE_READING_CACHE=off`, or it will be
answered with the reading it is trying to vary.

THE PAPER IS DECOMPOSED ONCE. With a `structure.json` on disk -- of any status --
passes 1 and 2 are not run at all: the studies, groups, phases, variables and
levels come from that file, every later pass selects from it, and an id it does
not contain is refused downstream. A paper with no structure file is decomposed
by passes 1 and 2, which write version 1. `--redecompose` is the only way to
decompose again, and it writes the next version rather than overwriting this one.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import bind as _bind
from . import schema as _schema
from . import reconstruct as _recon
from . import document as _document
from . import passes as _passes
from . import prompts as _prompts
from . import export as _export
from . import render as _render
from . import structure as _structure
from . import premise_reading as _premise_reading
from . import adjudication as _adjudication
from . import adjudication_attach as _adjudication_attach
from . import adjudication_n as _adjudication_n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m metascience_agent.scaffold")
    ap.add_argument("paper_dir")
    ap.add_argument("--model", default=_passes.DEFAULT_MODEL)
    ap.add_argument("--glyph-map", default=None,
                    help="JSON {font: {reported: intended}}; default <paper_dir>/scaffold/glyph_map.json if present")
    ap.add_argument("--resume", action="store_true", help="reuse pass outputs already on disk")
    ap.add_argument("--no-llm", action="store_true", help="assemble from disk only")
    ap.add_argument("--skip-residual", action="store_true")
    ap.add_argument("--recon-model", default=_recon.DEFAULT_MODEL,
                    help="model that reads each rendered table (section 8n); cached per table")
    ap.add_argument("--no-recon", action="store_true", help="walker cells only; no table reading")
    ap.add_argument("--no-supplement-text", action="store_true",
                    help="do not serve or index each supplement's running prose (the pre-2026-09-06 "
                         "behaviour, kept so the two can be measured against each other)")
    ap.add_argument("--allow-unextracted-supplements", action="store_true",
                    help="build the document even though a supplement PDF has no extraction "
                         "cache. Off by default: an un-extracted supplement serves 0 characters "
                         "and 0 tables, which reads as a supplement with nothing in it")
    ap.add_argument("--serve-protocol-supplements", action="store_true",
                    help="serve the running prose of a supplement classified `protocol` too "
                         "(off by default: a trial protocol is the sponsor's procedures, and "
                         "one of them is 194,792 characters. Its tables are read either way)")
    ap.add_argument("--freeze-draft", action="store_true",
                    help="freeze the structural account this run writes (or the draft on disk) "
                         "without adjudicating it; the account then says so in section 1")
    ap.add_argument("--freeze", action="store_true",
                    help="freeze the structural account on disk (the explicit command after "
                         "the structural adjudication)")
    ap.add_argument("--adjudicate-structure", action="store_true",
                    help="PAID: a second reader reads the structural account against the paper "
                         "with a STRUCTURE focus, and its corrections are applied under the "
                         "gates, writing the next version. Never runs implicitly")
    ap.add_argument("--redecompose", action="store_true",
                    help="run passes 1 and 2 again against a structure that already exists, "
                         "writing the next version as a new draft and printing the diff; the "
                         "version it replaces stays on disk under its own number")
    ap.add_argument("--review", action="store_true",
                    help="a model reads the finished account against the paper: located notes and "
                         "spot checks, marked as model readings (review.py)")
    ap.add_argument("--review-model", default=None, help="model for --review (default: --model)")
    ap.add_argument("--read-premises", action="store_true",
                    help="PAID. A model judges, once for this paper, whether each candidate "
                         "sentence establishes the bound / step / estimator / correction "
                         "premise it was surfaced for (premise_reading.py); the account is "
                         "then stamped from that reading rather than from the vocabularies")
    ap.add_argument("--premise-model", default=_premise_reading.DEFAULT_MODEL,
                    help="model for --read-premises (default: the one E1 validated)")
    ap.add_argument("--premise-budget", type=int,
                    default=_premise_reading.MAX_CANDIDATES_PER_PAPER,
                    help=f"PER-PAPER CANDIDATE BUDGET for whichever recall net is run "
                         f"(default {_premise_reading.MAX_CANDIDATES_PER_PAPER}, "
                         f"~${_premise_reading.projected_usd(_premise_reading.MAX_CANDIDATES_PER_PAPER)} "
                         f"at {_premise_reading.MAX_PER_CALL} candidates a call and "
                         f"${_premise_reading.USD_PER_FULL_CALL:.2f} a full call). The unit is "
                         f"CANDIDATES because candidates are what is billed. Over budget the "
                         f"run STOPS ASKING rather than truncating or failing: the account "
                         f"records `budget_exhausted`, and `unasked` names every premise and "
                         f"variable whose question was never put. Read that as reduced "
                         f"coverage -- these are REFUSAL nets, so a question not asked leaves "
                         f"a check running that the model might have withdrawn. 0 asks "
                         f"nothing at all; any NEGATIVE number means no budget, which is "
                         f"the pre-budget behaviour and the only way to spend whatever the "
                         f"net produces")
    ap.add_argument("--adjudicate", action="append", default=None,
                    choices=sorted(_adjudication._NETS),
                    help="PAID, PROTOTYPE, OPT-IN (wave 7e, adjudication.py). Repeatable. "
                         "Ask the model this REFUSAL premise's question of every passage "
                         "plausibly ABOUT how the quantity was arrived at, instead of only "
                         "the passages a closed vocabulary happened to match. A verdict "
                         "here can remove a check and can never add an accusation, and no "
                         "licence premise is touched. `estimator` is the wider net and "
                         "costs MUCH more -- in CANDIDATES, which is the unit that is "
                         "billed, not in governing windows: 10 to 21 windows on real corpus "
                         "bodies become 984 to 4,536 candidates (25 to 114 calls, $5 to $23) "
                         "because the net spends its per-scope cap once per variable, so the "
                         "count is linear in the variable count at ~97 each. Budget with "
                         "--premise-budget and read its docket. Not the default for anything")
    ap.add_argument("--adjudicate-averaging", action="store_true",
                    help="the wave 7e spelling of `--adjudicate averaging`, kept so the "
                         "instrument rounds 15 and 16 measured is unchanged")
    ap.add_argument("--adjudicate-varying-n", action="store_true",
                    help="PAID, PROTOTYPE, OPT-IN (round 18, adjudication_n.py). Ask the "
                         "model, for every quantity whose check would otherwise RUN, "
                         "whether the paper says fewer subjects contributed to it than the "
                         "denominator the account binds -- instead of only the sentences "
                         "`premises._N_VARIES` happens to match. A verdict here can only "
                         "WITHDRAW a denominator and refuse the check; it can never supply "
                         "one, and the alternative-base ceiling is untouched. Its own flag "
                         "rather than a `--adjudicate` choice because the net lives in a "
                         "separate module, which is what keeps D71's grep rail on "
                         "`adjudication.py` passing unedited. Not the default for anything")
    ap.add_argument("--adjudicate-attachment", action="store_true",
                    help="PAID, PROTOTYPE, OPT-IN (round 24, widened in round 28; "
                         "adjudication_attach.py). For every variable whose per-subject "
                         "step of 1 rests on a SENTENCE, ask the model ONE question about "
                         "that sentence: does it show that the figure the paper reports "
                         "for one subject is a whole number? It covers the three ways the "
                         "sentence can fail to -- the whole-number words belong to another "
                         "quantity, the paper takes whole-number recording away, or what "
                         "is made whole is one observation rather than the reported figure "
                         "-- which the free path guards with three separate vocabularies. "
                         "A verdict here can only WITHDRAW the licence the vocabulary "
                         "granted; no answer to it grants or restores a step the free "
                         "path withheld, which is why it is allowed near a licence at "
                         "all. Its own flag rather than a `--adjudicate` choice because "
                         "the net lives in a separate module, which is what keeps D71's "
                         "grep rail on `adjudication.py` passing unedited. Not the "
                         "default for anything")
    ap.add_argument("--max-residual-iterations", type=int, default=4,
                    help="iterate the gap work queue until empty, non-shrinking, or this many passes")
    args = ap.parse_args(argv)

    pd = Path(args.paper_dir)
    out = pd / "scaffold"
    out.mkdir(parents=True, exist_ok=True)
    gm_path = Path(args.glyph_map) if args.glyph_map else out / "glyph_map.json"
    glyph_map = None
    if gm_path.is_file():
        glyph_map = {k: v for k, v in json.loads(gm_path.read_text(encoding="utf-8")).items()
                     if not k.startswith("_")}
    t0 = time.time()
    doc = _document.build(pd, glyph_map=glyph_map,
                          serve_supplement_text=not args.no_supplement_text,
                          serve_protocol_text=args.serve_protocol_supplements,
                          allow_unextracted_supplements=args.allow_unextracted_supplements)
    _document.save(doc, out)
    _bs = ", ".join(f"{k} {v['n_total']}" for k, v in
                    sorted((doc["numeral_floor"].get("by_source") or {}).items()))
    _supp = "".join(f", +{s['file']} {s['n_chars']} chars" for s in doc.get("supplement_spans") or [])
    # THE SET-ASIDE COUNT IS PRINTED BESIDE THE TOTAL, never only inside the
    # code that computed it: it is the number of supplement numerals the floor
    # counts from the table cells rather than from the pipe rows of the served
    # text, and a number removed from a denominator has to be visible.
    _aside = doc["numeral_floor"].get("n_supplement_pipe_rows_set_aside") or 0
    print(f"document: {doc['source']['n_chars']} chars ({doc['source']['n_chars_article']} article"
          f"{_supp}), {doc['repairs']['n_repairs']} repairs, "
          f"{len(doc['tables'])} tables, {len(doc['figures'])} figures, "
          f"{doc['numeral_floor']['n_total']} numerals ({_bs})"
          + (f"; {_aside} supplement pipe-row numeral(s) set aside, counted as table cells"
             if _aside else ""), flush=True)

    # THE STRUCTURE IS READ BEFORE ANYTHING IS RUN. With one on disk, passes 1
    # and 2 are not called at all -- not resumed, not re-prompted, not skipped
    # by a flag: the vocabulary comes from the file, and that is the whole point
    # of freezing it (D43). `--redecompose` is the only way past it, and it
    # writes the next version rather than overwriting this one.
    struct = _structure.load(out)
    previous = None
    if struct is not None and args.redecompose:
        previous, struct = struct, None
        print(f"structure: --redecompose against v{previous['version']} "
              f"({previous['status']}); passes 1 and 2 will run again", flush=True)
    stamp: dict = {}

    def stage(name: str, prompt_fn, schema: dict | None = None):
        if args.resume or args.no_llm:
            got = _passes.load_pass(name, out)
            if got is not None:
                print(f"{name}: reused from disk", flush=True)
                return got
        if args.no_llm:
            raise SystemExit(f"--no-llm but no saved {name}.json")
        prompt = prompt_fn()
        print(f"{name}: running ({len(prompt)} chars of prompt) ...", flush=True)
        got = _passes.run_pass(name, prompt, out, model=args.model, schema=schema,
                               extra_meta=stamp or None)
        print(f"{name}: done in {got['meta']['elapsed_s']}s, ${got['meta'].get('cost_usd')}, "
              f"{len(got['problems'])} schema problems", flush=True)
        return got

    if struct is not None:
        p1 = {"data": struct["pass1"], "problems": [],
              "meta": {"source": f"structure.json v{struct['version']}"}}
        p2 = {"data": struct["pass2"], "problems": [],
              "meta": {"source": f"structure.json v{struct['version']}"}}
        print(f"structure: v{struct['version']} {struct['status']}, "
              f"sha {_structure.content_sha256(struct)[:12]}, "
              + ", ".join(f"{k} {n}" for k, n in _structure.id_counts(struct).items())
              + "; passes 1 and 2 NOT run", flush=True)
        if (args.freeze or args.freeze_draft) and struct["status"] != "frozen":
            struct = _structure.freeze(struct, out)
            print(f"structure: v{struct['version']} frozen at {struct['frozen_at']}", flush=True)
        elif args.freeze or args.freeze_draft:
            print(f"structure: v{struct['version']} was already frozen at "
                  f"{struct['frozen_at']}; nothing rewritten", flush=True)
    else:
        p1 = stage("pass1", lambda: _prompts.pass1_prompt(doc["text"]))
        p2 = stage("pass2", lambda: _prompts.pass2_prompt(doc["text"], p1["data"]))
        produced = {"pass1": p1.get("meta"), "pass2": p2.get("meta")}
        if previous is None:
            struct = _structure.create(p1["data"], p2["data"], doc, out,
                                       produced_by=produced, freeze_draft=args.freeze_draft)
        else:
            struct, diff = _structure.redecompose(previous, p1["data"], p2["data"], doc, out,
                                                  produced_by=produced,
                                                  freeze_draft=args.freeze_draft)
            print(_structure.format_diff(diff), flush=True)
        print(f"structure: wrote v{struct['version']} ({struct['status']}), "
              f"sha {_structure.content_sha256(struct)[:12]}", flush=True)
    if args.adjudicate_structure and args.no_llm:
        # `--no-llm` PROMISES THAT NOTHING RUNS. A paid pass under it would be
        # the flag lying, which is worse than the two flags being incompatible.
        raise SystemExit("--adjudicate-structure is a paid pass and --no-llm runs nothing; "
                         "pick one")
    if args.adjudicate_structure:
        # STEP 2 OF THE LIFECYCLE, AND IT IS PAID. Never implicit: it runs on
        # this flag and on nothing else. What binds to each variable is read
        # from the account already on disk, because a removal is refused unless
        # we can PROVE nothing binds -- with no account there, every removal is
        # refused rather than guessed at.
        acc_path = out / "account.json"
        bound: set[str] | None = None
        if acc_path.is_file():
            bound = {v.get("variable_id") for v in
                     json.loads(acc_path.read_text(encoding="utf-8")).get("values") or []
                     if v.get("variable_id")}
        res = _passes.run_pass("structure_review",
                               _structure.structure_review_prompt(struct, doc["text"]), out,
                               model=args.review_model or args.model,
                               schema=_structure.structure_adjudication_schema(),
                               extra_meta=stamp or None)
        adj = {"model": args.review_model or args.model, "version": "structure_review/1",
               **res["data"]}
        from . import interpret as _interpret
        struct, audit = _structure.apply_structural_adjudication(
            struct, adj, doc["text"], side="a", bound_variable_ids=bound,
            # WHAT THE TABLES ACTUALLY PRINT, so a `printed_as` label is checked
            # rather than believed. From the walker's own cells: a row stub is
            # not prose and is not in the body text.
            printed_row_labels=_interpret.row_label_vocabulary(doc["tables"]),
            out_dir=out)
        p1 = {"data": struct["pass1"], "problems": [], "meta": p1["meta"]}
        p2 = {"data": struct["pass2"], "problems": [], "meta": p2["meta"]}
        print(f"structure: adjudicated (${res['meta'].get('cost_usd')}), wrote "
              f"v{struct['version']}: {audit['n_applied']} applied, {audit['n_skipped']} skipped, "
              f"{audit['n_conflicts']} conflict(s) recorded", flush=True)
    stamp = _structure.stamp(struct)
    stale = _structure.stale_document(struct, doc)
    if stale:
        print("structure: STALE DOCUMENT -- the served text is not the one this structure was "
              f"read from ({stale['document_sha256_in_structure'][:12]} then, "
              f"{stale['document_sha256_now'][:12]} now); nothing re-decomposed, "
              f"chars {stale['changed_by_source']['total']}", flush=True)
    # THE TABLES ARE READ HERE, AFTER PASS 2 AND BEFORE PASS 3: the reader gets
    # the passages that cite each table and the declared variables and groups,
    # and pass 3 then sees the tidy cells. `--no-llm` reuses cached readings.
    if not args.no_recon:
        _recon.reconstruct_tables(pd, doc["tables"], out / "tables",
                                  model=None if args.no_llm else args.recon_model,
                                  problems=doc["problems"], text=doc["text"],
                                  p1=p1["data"], p2=p2["data"], stamp=stamp)
        _document.save(doc, out)
        _rs = [t.get("reconstruction") or {} for t in doc["tables"]]
        print("tables read by model: " + ", ".join(
            f"{t['id']} {r.get('status')}" + (f" ${r['cost_usd']:.2f}" if r.get("cost_usd") else "")
            for t, r in zip(doc["tables"], _rs)), flush=True)
    # PASS 3 IN PARTS. Verified tables are entries already and are not re-read;
    # the unread tables go to the main call up to a cell budget and to separate
    # table-only calls beyond it (one call over twelve tables overflowed the
    # output cap). The parts are merged and saved as pass3.json, so --resume and
    # bind see one pass 3 as before.
    main_tables, batches = _prompts.pass3_batches(doc["tables"])
    p3 = stage("pass3", lambda: _prompts.pass3_prompt(doc["text"], p1["data"], p2["data"],
                                                      main_tables, doc["figures"]))
    if batches:
        merged = dict(p3["data"]); merged["table_readings"] = list(merged.get("table_readings") or [])
        for k, batch in enumerate(batches, start=1):
            part = stage(f"pass3_tables_{k}", lambda b=batch: _prompts.pass3_tables_prompt(p1["data"], p2["data"], b),
                         schema=_schema.pass_schema("pass3"))
            merged["table_readings"] += list(part["data"].get("table_readings") or [])
            p3["problems"] = list(p3.get("problems") or []) + list(part.get("problems") or [])
        # ONE READING PER TABLE, FIRST WINS. A resumed run loads the pass3.json
        # that already holds the batches' readings and would merge them again
        # (26 readings for 11 tables on the first --no-llm re-assembly).
        merged["table_readings"] = _prompts.dedupe_readings(merged["table_readings"])
        p3["data"] = merged
        (out / "pass3.json").write_text(json.dumps(merged, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"pass3: {len(batches)} table batch(es) merged; {len(merged['table_readings'])} table readings", flush=True)
    # THE GAP IS A WORK QUEUE, ITERATED TO CLOSURE (Greg, 2026-09-05). Each
    # iteration assembles the account, lists the numerals still unplaced in
    # reading order with their sentences, and asks the model -- scaffold in hand
    # -- where each belongs. It stops when the gap is empty, stops shrinking, or
    # `--max-residual-iterations` is reached. The gap at every iteration is
    # recorded; that curve is the result, not the final number alone.
    residual: dict | None = None
    gap_curve: list[dict] = []
    if not args.skip_residual:
        residual = {"dispositions": [], "new_values": []}
        # A legacy single-pass file counts as iteration 1 when resuming.
        legacy = _passes.load_pass("residual", out) if (args.resume or args.no_llm) else None
        prev = None
        for it in range(1, args.max_residual_iterations + 1):
            draft = _bind.assemble(doc, p1["data"], p2["data"], p3["data"], residual,
                                   structure=struct)
            rows = _bind.residual_rows(draft["accounting"], text=doc["text"], pages=doc.get("pages"))
            b = draft["completeness"]["three_buckets"]
            gap_curve.append({"iteration": it - 1, "placed": b["placed_as_value"],
                              "dispositioned": b["dispositioned_non_measurement"],
                              "ambiguous": b["ambiguous_with_candidates"], "unplaced": len(rows),
                              "values": draft["completeness"]["values_total"]})
            print(f"residual iteration {it - 1}: placed {b['placed_as_value']}, ambiguous "
                  f"{b['ambiguous_with_candidates']}, unplaced {len(rows)}", flush=True)
            if not rows or (prev is not None and len(rows) >= prev):
                break
            prev = len(rows)
            name = f"residual_{it}"
            values_index = [{"id": v["id"], "printed": v["printed"], "variable_id": v.get("variable_id"),
                             "statistic": v["statistic"], "coordinate": v.get("coordinate")}
                            for v in draft["values"]]
            structure = {
                "studies": [{"id": s["id"], "label": s["label"], "groups": [g["id"] for g in s["groups"]],
                             "phases": [p["id"] for p in s["phases"]]} for s in draft["studies"]],
                "phases": [p["id"] for p in draft.get("phases", []) or []],   # paper-level occasions
                "variables": [{"id": v["id"], "name": v["name"], "role": v["role"]} for v in draft["variables"]],
                "procedures": [{"id": p["id"], "name": p["name"]} for p in draft["procedures"]],
            }
            if it == 1 and legacy is not None and _passes.load_pass(name, out) is None:
                res = legacy
                print("residual_1: reused legacy residual.json", flush=True)
            else:
                res = stage(name, lambda: _prompts.residual_prompt(rows, values_index, structure, iteration=it))
            residual["dispositions"] += res["data"].get("dispositions", [])
            residual["new_values"] += res["data"].get("new_values", [])
        else:
            draft = _bind.assemble(doc, p1["data"], p2["data"], p3["data"], residual,
                                   structure=struct)
            rows = _bind.residual_rows(draft["accounting"])
            b = draft["completeness"]["three_buckets"]
            gap_curve.append({"iteration": args.max_residual_iterations, "placed": b["placed_as_value"],
                              "dispositioned": b["dispositioned_non_measurement"],
                              "ambiguous": b["ambiguous_with_candidates"], "unplaced": len(rows),
                              "values": draft["completeness"]["values_total"]})
            print(f"residual iteration {args.max_residual_iterations}: {len(rows)} numerals unplaced "
                  "(iteration cap reached)", flush=True)
    provenance = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "model": args.model, "elapsed_s": round(time.time() - t0, 1),
                  "gap_curve": gap_curve, **stamp,
                  "passes": {n: (_passes.load_pass(n, out) or {}).get("meta")
                             for n in ["pass1", "pass2", "pass3", "residual"]
                             + [f"residual_{i}" for i in range(1, args.max_residual_iterations + 1)]
                             if (_passes.load_pass(n, out) or {}).get("meta")}}
    # THE PREMISE READING, BEFORE THE ACCOUNT IT GOVERNS. It needs the variables
    # and values to build candidates, so it runs on a draft assembly and the
    # final assembly carries its verdicts into the stamp. A reading already on
    # disk is reused, so `--resume` and `--no-llm` cost nothing here.
    #
    # ONE FLAG, ONE PREMISE EACH, AND THE OLD SPELLING IS AN ALIAS. A second
    # boolean per premise would make the mutual-exclusion check below grow a term
    # every round, and `adjudicate()` takes a list anyway.
    adjudicate = list(dict.fromkeys(
        (args.adjudicate or []) + (["averaging"] if args.adjudicate_averaging else [])))
    varying_n = bool(args.adjudicate_varying_n)
    attachment = bool(args.adjudicate_attachment)
    reading = _premise_reading.load(out)
    if (args.read_premises or adjudicate or varying_n or attachment) and reading is None:
        draft = _bind.assemble(doc, p1["data"], p2["data"], p3["data"], residual,
                               structure=struct)
        # THE PROTOTYPE IS A DIFFERENT RECALL NET, NOT A DIFFERENT PIPELINE, so
        # it writes the same `premise_reading.json` the ordinary pass does and
        # the assembly below carries it the same way. Asking for BOTH is
        # refused rather than merged: two candidate sets written to one file
        # would leave a reader unable to say which net produced a verdict, and
        # the point of a gated prototype is that it can be measured apart.
        if sum([bool(args.read_premises), bool(adjudicate), varying_n,
                attachment]) > 1:
            ap.error("--read-premises, --adjudicate, --adjudicate-varying-n and "
                     "--adjudicate-attachment write the same reading file by different "
                     "recall nets; run one")
        # A NEGATIVE BUDGET IS THE ONLY WAY TO SAY "UNBUDGETED" FROM A TYPED INT
        # FLAG, and it has to be sayable: the library takes `budget=None` and
        # without this the CLI could not express it at all, which would make the
        # default a ceiling nobody could lift rather than one they could choose
        # to. 0 still means ask nothing -- a different instruction, deliberately.
        budget = args.premise_budget if args.premise_budget >= 0 else None
        reading = (_adjudication_attach.adjudicate(draft, doc["text"], out,
                                                   model=args.premise_model,
                                                   budget=budget)
                   if attachment else
                   _adjudication_n.adjudicate(draft, doc["text"], out,
                                              model=args.premise_model,
                                              budget=budget)
                   if varying_n else
                   _adjudication.adjudicate(draft, doc["text"], out,
                                            model=args.premise_model,
                                            premises=tuple(adjudicate),
                                            budget=budget)
                   if adjudicate else
                   _premise_reading.read(draft, doc["text"], out,
                                         model=args.premise_model, budget=budget))
        # WHAT WAS ASKED, WHAT IT COST, AND WHAT WAS NOT ASKED -- the third is the
        # one a silently truncated run would leave out, so it is printed on its
        # own line and never folded into the first.
        #
        # AND THERE IS NO RUN-LEVEL COST TOTAL TO CONTRIBUTE TO, WHICH IS WORTH
        # WRITING DOWN RATHER THAN QUIETLY INVENTING ONE. `passes.run_pass`
        # stamps `cost_usd` into every `<name>.meta.json`, and these nets already
        # go through it -- so each of their calls is in the only ledger this
        # package keeps, and `read` sums them into the record below. What does
        # not exist anywhere in `scaffold/` is a total for the whole invocation:
        # each pass prints its own price and nothing adds them up. Summing the
        # metas on disk would NOT be that total either, because a resumed run
        # reuses replies whose saved meta still carries the price originally
        # paid -- it would bill a free run at full price. Building an honest
        # one means tracking what THIS invocation spent across passes, which is
        # a change to every pass and not to the adjudication nets.
        spent = reading.get("cost_usd")
        total = reading.get("cost_usd_total")
        reused = reading.get("n_calls_reused") or 0
        price = f"${spent}" if not reused else (
            f"${spent} this run (${total} to produce; {reused} of "
            f"{reading['n_calls']} call(s) reused, costing nothing again)")
        print(f"premises read by model: {reading['n_asked']} of {reading['n_candidates']} "
              f"candidate(s) asked in {reading['n_calls']} call(s), "
              f"{len(reading['verdicts'])} verdict(s), {price}", flush=True)
        if reading.get("budget_exhausted"):
            scopes = reading.get("unasked") or []
            variables = {r.get("variable_id") for r in scopes}
            print(f"  BUDGET EXHAUSTED at {reading.get('budget')} candidate(s): "
                  f"{reading.get('n_unasked_over_budget')} of {reading.get('n_askable')} "
                  f"askable candidate(s) were NEVER ASKED, over {len(scopes)} scope(s) and "
                  f"{len(variables)} variable(s). These are refusal nets, so each unasked "
                  f"question leaves a check running that the model might have withdrawn. "
                  f"`unasked` in premise_reading.json names them; raise --premise-budget to "
                  f"ask them (the full set is ~"
                  f"${_premise_reading.projected_usd(reading.get('n_askable') or 0)}).",
                  flush=True)
    account = _bind.assemble(doc, p1["data"], p2["data"], p3["data"], residual, provenance,
                             structure=struct,
                             artifact_stamps=_structure.artifact_stamps(out),
                             premise_reading=reading)
    (out / "account.json").write_text(json.dumps(account, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "account.md").write_text(_render.render(account, doc["text"]), encoding="utf-8")
    # THE LONG FORM, beside the record and the reading. A projection of
    # `account.json` and nothing else -- one row per value, no filtering.
    (out / "values.csv").write_text(_export.values_csv(account), encoding="utf-8")
    # THE CHECKS, AFTER THE ACCOUNT AND FOR NOTHING. The bridge reads the
    # account and the structure it has just written and calls the tool registry
    # in process: no model, no network, no cost. It therefore runs on every
    # path, `--no-llm` included -- there is no budget to gate it behind, and a
    # check that is free and not run is a check nobody sees.
    from . import checks as _checks
    checks = _checks.run(out)
    print(f"checks: {checks['n_run']} of {checks['n_candidates']} candidate(s) ran, "
          + (", ".join(f"{k} {v}" for k, v in checks["by_severity"].items()) or "no verdicts")
          + f"; {checks['n_refused']} refused ("
          + ", ".join(f"{k} {v}" for k, v in
                      sorted(checks["refused_by_reason"].items(), key=lambda kv: -kv[1])[:3])
          + ")", flush=True)
    (out / "account.md").write_text(_render.render(account, doc["text"], checks), encoding="utf-8")
    if args.review:
        # THE SECOND READER runs on the finished, rendered account and its
        # notes are attached as model readings; the account is re-rendered
        # with them under their own heading. Never on --no-llm's dime unless
        # asked: --review is explicit.
        from . import review as _review
        rv = _review.run_review(account, (out / "account.md").read_text(encoding="utf-8"), doc["text"], out,
                                model=args.review_model or args.model)
        account["review"] = rv
        (out / "account.json").write_text(json.dumps(account, indent=1, ensure_ascii=False), encoding="utf-8")
        (out / "account.md").write_text(_render.render(account, doc["text"], checks), encoding="utf-8")
        print(f"review: {len(rv.get('notes') or [])} notes, {len(rv.get('unstable_readings') or [])} unstable readings, "
              f"spot checks {rv.get('spot_checks_by_verdict')}, ${rv.get('cost_usd')}", flush=True)
    c = account["completeness"]
    print(f"account: {c['values_total']} values, {c['comparisons_total']} comparisons, "
          f"{c['claims_total']} claims; numerals accounted {c['numerals_accounted']}/"
          f"{c['numerals_in_scope']} ({c['share_accounted']}); unaccounted {c['numerals_unaccounted']}; "
          f"integrity problems {len(account['integrity_problems'])}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
