#!/usr/bin/env python3
"""Turn Paul Litvak's planted-error benchmark into FMA paper directories.

    python benchmarks/litvak/prepare.py --which modified
    python benchmarks/litvak/prepare.py --which original   # the clean control

WHY NOT THE BENCHMARK'S OWN CONVERTER. `benchmark/docx_to_pdf.py` renders a
flat text PDF with `fpdf` and says so in its docstring: "This sacrifices
original page layout (no Word/LibreOffice available) in favor of
content-equality". That is the right call for the LLM reviewers Litvak scored,
which all read prose. It is the wrong call for FMA, whose checks live in
TABLES: a flattened PDF destroys the column structure that `check_table`,
`check_count_percent`, GRIM and GRIMMER all read. It also hard-codes a macOS
font path.

We convert with a LAYOUT-PRESERVING converter -- Word over COM where Windows
is reachable, LibreOffice (`soffice --headless`) otherwise. WHICH ONE RAN IS
RECORDED in `prepare_meta.json`, because a number from a Word run and a number
from a LibreOffice run are not interchangeable and the difference would
otherwise be invisible six months later. The input is in either case NOT
identical to what Litvak's systems saw, and that must be stated whenever a
number from this run is reported -- it is a real methodological difference, in
our favour, and hiding it would make the comparison dishonest.

THE `.docx` IS DELIBERATELY NOT COPIED INTO THE PAPER DIRECTORY. It used to be,
"to keep the source beside it". But `agent._resolve_paper_inputs` sweeps every
top-level non-pdf/xml/html/md file into `si_readable` (`.docx` is in
`_SI_READABLE`), so each paper was fed its own manuscript TWICE -- once as the
extracted PDF, once as OOXML -- giving every table a byte-identical twin in the
"supplement". `detect_duplication` escalates at three matching pairs, so this
manufactured a duplication finding on all ten papers, INCLUDING the ten clean
controls whose whole purpose is measuring false positives. Same class as the
`panels/` re-ingestion invariant in CLAUDE.md. The source path is recorded in
`prepare_meta.json` instead; do not "helpfully" restore the copy.

NOTHING IS RUN HERE. This only prepares directories; `metascience batch` is a
separate, deliberate step.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench, resolve_out  # noqa: E402


class NotReachableByWindows(RuntimeError):
    """A path Word cannot see, named as such instead of failing as a COM error."""


class NoConverter(RuntimeError):
    """Neither Word nor LibreOffice is available, said plainly."""


def _win(p: Path) -> str:
    """WSL path -> the Windows path Word needs.

    REFUSES a path outside /mnt/<drive>. Word is a Windows process and cannot
    open or write anywhere in the WSL filesystem, so `/tmp/...` comes back as a
    bare `COMException` with no hint of the cause -- which is exactly what it
    did the first time this was tested. Naming the reason costs one line.
    """
    s = str(p.resolve())
    if not (s.startswith("/mnt/") and len(s) > 6 and s[5].isalpha()):
        raise NotReachableByWindows(
            f"{s} is inside WSL; Word cannot reach it. Use a path under "
            "/mnt/c/... for both the source and the destination.")
    return s[5].upper() + ":" + s[6:].replace("/", "\\")


def _looks_like_pdf(p: Path) -> bool:
    """Verified as BYTES, not by exit code.

    A COM failure or a LibreOffice profile error can leave a zero-byte or HTML
    error file behind and report nothing. Applied on the RESUME path too: a
    truncated PDF from an interrupted run used to survive a re-run because the
    resume check tested only the size.
    """
    try:
        return (p.is_file() and p.stat().st_size > 1000
                and p.read_bytes()[:4] == b"%PDF")
    except OSError:
        return False


def _word_available() -> bool:
    return shutil.which("powershell.exe") is not None


def _soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        if (found := shutil.which(name)):
            return found
    return None


def convert_word(src: Path, dst: Path) -> bool:
    ps = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject Word.Application;$w.Visible=$false;"
        f"$d=$w.Documents.Open('{_win(src)}',$false,$true);"
        f"$d.SaveAs2('{_win(dst)}',17);"
        "$d.Close($false);$w.Quit()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=300)
    return _looks_like_pdf(dst)


def convert_soffice(src: Path, dst: Path, binary: str) -> bool:
    """LibreOffice writes `<stem>.pdf` into --outdir; we rename to `dst`.

    `-env:UserInstallation` points at a scratch profile: a shared profile is
    locked by any running LibreOffice, and the conversion then fails with an
    exit code of 0 and no output file.

    The profile and the raw output both go to a TEMPDIR, not to the paper
    directory. Pointed at the paper directory it leaves a `.lo-profile/` behind
    in every paper -- our own scratch state inside a directory the pipeline
    scans, which is the mistake the `panels/` re-ingestion invariant in
    CLAUDE.md exists to prevent. Only the finished PDF is moved in.
    """
    with tempfile.TemporaryDirectory(prefix="litvak-soffice-") as tmp:
        tmpdir = Path(tmp)
        subprocess.run(
            [binary, f"-env:UserInstallation=file://{tmpdir / 'profile'}",
             "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", str(tmpdir), str(src)],
            capture_output=True, timeout=300, check=False,
        )
        produced = tmpdir / (src.stem + ".pdf")
        if not _looks_like_pdf(produced):
            return False
        shutil.move(str(produced), str(dst))
    return _looks_like_pdf(dst)


def pick_converter() -> tuple[str, str]:
    """(id, human description). Refuses by name rather than failing obscurely."""
    if _word_available():
        return "word_com", "Microsoft Word via COM (layout-preserving)"
    if (binary := _soffice()):
        return "libreoffice", f"LibreOffice headless via {binary} (layout-preserving)"
    raise NoConverter(
        "No layout-preserving converter found. Install LibreOffice "
        "(`soffice` on PATH), or run on a machine where `powershell.exe` can "
        "reach Word. The benchmark's own docx_to_pdf.py is NOT an acceptable "
        "substitute here -- it flattens tables, which is where FMA's checks live."
    )


def convert(src: Path, dst: Path, converter: str) -> bool:
    if converter == "word_com":
        return convert_word(src, dst)
    return convert_soffice(src, dst, _soffice() or "soffice")


def stage_pdfs(src_dir: Path, out: Path) -> tuple[list, list, dict]:
    """Build paper directories from PDFs someone else converted.

    The Litvak PDFs Greg produced are Word-over-COM output (`pdfinfo` says
    `Producer: Microsoft Word for Microsoft 365`), which is the conversion his
    Opus 5 run read. Staging those directly is what lets a grok run isolate the
    BACKEND instead of confounding it with the converter -- LibreOffice, the
    only converter available on this machine, damages tables on 5 of 10 of
    these papers.

    Nothing but the PDF is copied. `agent._resolve_paper_inputs` sweeps every
    top-level non-pdf/xml/html/md file into `si_readable`, so a `.docx` beside
    the PDF feeds each paper its own manuscript twice.
    """
    made, failed, prov = [], [], {}
    for pdf in sorted(src_dir.glob("*.pdf")):
        stem = "".join(ch for ch in pdf.stem if ch.isdigit())
        if not stem:
            failed.append(f"{pdf.name}: no paper number in the filename")
            continue
        paper = out / f"litvak{int(stem):02d}"
        paper.mkdir(parents=True, exist_ok=True)
        dst = paper / f"{paper.name}.pdf"
        if not _looks_like_pdf(pdf):
            failed.append(f"{pdf.name}: not a readable PDF")
            continue
        shutil.copy2(pdf, dst)
        prov[paper.name] = {"source": str(pdf), "producer": _pdf_producer(pdf)}
        made.append(paper.name)
        print(f"  ok   {paper.name}  <- {pdf.name}  "
              f"[{prov[paper.name]['producer']}]", flush=True)
    return made, failed, prov


def _pdf_producer(pdf: Path) -> str:
    """The converter, from the PDF's own metadata.

    One command settles what a docstring cannot: Word, LibreOffice and fpdf all
    name themselves here. Recorded per paper so a mixed corpus cannot look
    uniform.
    """
    exe = shutil.which("pdfinfo")
    if not exe:
        return "unknown (pdfinfo not on PATH)"
    try:
        out = subprocess.run([exe, str(pdf)], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception:                                          # noqa: BLE001
        return "unknown"
    for line in out.splitlines():
        if line.startswith("Producer:"):
            return line.split(":", 1)[1].strip() or "empty"
    return "not recorded in the PDF"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-pdfs", type=Path, default=None,
                    help="Stage already-converted PDFs into paper directories "
                         "instead of converting .docx here. Use this for "
                         "PDFs produced elsewhere (e.g. Word over COM).")
    ap.add_argument("--which", choices=("modified", "original"),
                    default="modified")
    ap.add_argument("--out", type=Path, default=None)
    add_bench_arg(ap)
    a = ap.parse_args()

    if a.from_pdfs:
        if not a.from_pdfs.is_dir():
            print(f"not a directory: {a.from_pdfs}", file=sys.stderr)
            return 1
        out = a.out or (resolve_out() / f"{a.which}_staged")
        out.mkdir(parents=True, exist_ok=True)
        print(f"source   : {a.from_pdfs}")
        print(f"output   : {out}\n")
        made, failed, prov = stage_pdfs(a.from_pdfs, out)
        producers = sorted({v["producer"] for v in prov.values()})
        (out / "prepare_meta.json").write_text(json.dumps({
            "which": a.which, "source": str(a.from_pdfs),
            "converter": "external",
            "converter_description": "; ".join(producers) or "unknown",
            "pdf_producers": producers,
            "docx_copied_into_paper_dir": False,
            "papers": prov, "n_papers": len(made),
            "n_failed": len(failed), "failed": failed,
        }, indent=1), encoding="utf-8")
        print(f"\n{len(made)} paper dir(s) under {out}"
              + (f"; {len(failed)} FAILED: {failed}" if failed else ""))
        print(f"converter: {'; '.join(producers)}")
        if len(producers) > 1:
            print("!! MIXED CONVERTERS in one corpus -- table fidelity will "
                  "differ between papers, and any per-paper comparison "
                  "inherits that.")
        print("\nNext:")
        print(f"  for d in {out}/litvak*; do metascience extract-tables \"$d\"; done")
        print(f"  python benchmarks/litvak/verify_tables.py {out}")
        return 1 if failed else 0

    try:
        bench = resolve_bench(a.bench)
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1

    src_dir = bench / f"{a.which} papers"
    if not src_dir.is_dir():
        print(f"missing: {src_dir}", file=sys.stderr)
        return 1

    try:
        converter, converter_desc = pick_converter()
    except NoConverter as exc:
        print(exc, file=sys.stderr)
        return 1

    out = a.out or (resolve_out() / a.which)
    out.mkdir(parents=True, exist_ok=True)
    print(f"benchmark : {bench}")
    print(f"converter : {converter_desc}")
    print(f"output    : {out}\n")

    made, failed, reused, sources = [], [], [], {}
    for docx in sorted(src_dir.glob("*.docx"), key=lambda p: int(p.stem)):
        paper = out / f"litvak{docx.stem.zfill(2)}"
        paper.mkdir(exist_ok=True)
        pdf = paper / f"{paper.name}.pdf"
        sources[paper.name] = str(docx)
        if _looks_like_pdf(pdf):
            made.append(paper.name)
            reused.append(paper.name)
            print(f"  skip {paper.name}  (already converted)", flush=True)
            continue
        ok = convert(docx, pdf, converter)
        (made if ok else failed).append(paper.name if ok else docx.name)
        print(f"  {'ok  ' if ok else 'FAIL'} {paper.name}", flush=True)

    (out / "prepare_meta.json").write_text(json.dumps({
        "which": a.which,
        "source": str(src_dir),
        "converter": converter,
        "converter_description": converter_desc,
        "not_used": "benchmark/docx_to_pdf.py -- flattens tables, macOS font path",
        "docx_copied_into_paper_dir": False,
        "docx_not_copied_because": (
            "agent._resolve_paper_inputs ingests a top-level .docx as a readable "
            "supplement, which feeds each paper its own manuscript twice and "
            "manufactures a duplication finding on every paper, controls included."),
        "docx_sources": sources,
        "n_papers": len(made), "n_reused": len(reused),
        "n_failed": len(failed), "failed": failed,
    }, indent=1), encoding="utf-8")

    print(f"\n{len(made)} paper dir(s) under {out}"
          + (f" ({len(reused)} reused)" if reused else "")
          + (f"; {len(failed)} FAILED: {failed}" if failed else ""))
    print("NOT RUN. Next step, when Dan says the codebase is settled:")
    print(f"  metascience batch {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
