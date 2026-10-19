"""
R-based tools using subprocess to call R packages.

These provide more robust implementations of complex algorithms
like SPRITE (via rsprite2) and GRIM/GRIMMER (via scrutiny).
"""

import math
import subprocess
import re

from . import rounding as _rounding


def _r_string(value: str) -> str:
    """Quote a Python string as an R string literal (escaping \\ and \").

    All string interpolation into generated R source MUST go through this —
    raw f-string interpolation breaks on paths containing quotes or
    backslashes and is an injection hazard.
    """
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _r_num(value) -> str:
    """Coerce a value to a numeric literal safe to embed in R source.

    NON-FINITE VALUES ARE REFUSED. `repr(float("nan"))` is the bare word `nan`,
    which R parses as a SYMBOL, not a number. Verified: r_sprite(mean=nan,
    sd=2.61, n=7) put `mean = nan` into the generated source, R raised
    "object 'nan' not found", and the wrapper returned that R parser error as
    severity `impossible` -- a syntax error published as a verdict about a
    paper. Refusing here means no call site can inject one, whatever the
    registry gate does upstream.
    """
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(
            f"non-finite value {value!r} cannot be embedded in R source"
        )
    return repr(v)


def _r_int(value) -> str:
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(
            f"non-finite value {value!r} cannot be embedded in R source"
        )
    return str(int(v))


def run_r_code(r_code: str, timeout: int = 60) -> dict:
    """
    Run R code and capture output.

    Args:
        r_code: R code to execute
        timeout: Maximum execution time in seconds

    Returns:
        Dictionary with stdout, stderr, and return code
    """
    try:
        result = subprocess.run(
            ["Rscript", "-e", r_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "error": "R not installed or Rscript not in PATH",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "error": f"R code timed out after {timeout} seconds",
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "error": str(e),
        }


#: The `if (!require(pkg)) { cat("ERROR: pkg package not installed...") }`
#: preamble every snippet below uses.
_MISSING_PKG_RE = re.compile(r"ERROR:\s*(\S+) package not installed")


def _r_unavailable(result: dict, package: str) -> dict:
    """Say WHY an R cross-check produced no verdict, in a shape callers can branch on.

    WHY THIS EXISTS. The missing-package diagnostic is written by R's `cat()`
    to STDOUT, and `require(..., quietly = TRUE)` keeps STDERR empty, so a
    failure branch reading `result["error"] or result["stderr"]` reports the
    empty string: `error` is absent (no Python exception fired) and `stderr`
    is "". MEASURED: with `scrutiny` absent, `r_grim` returned
    `{"error": "", "note": "Consider using Python GRIM implementation
    instead"}` on every call. Nothing downstream could tell that apart from a
    cross-check that ran and disagreed -- and the prompts tell the model that
    a disagreement means OUR tooling is wrong, so the model correctly
    downgraded findings the engine had never actually examined. Every GRIM
    failure in one corpus paper was capped at `suspicious` on that basis; run
    by hand, all three were `impossible`.

    So the three cases are now NAMED rather than collapsed into one empty
    string:

      package_missing  the engine is not installed here. Says nothing about
                       the paper, and must never be read as agreement or
                       disagreement.
      r_absent         no Rscript on PATH at all.
      r_error          R ran and genuinely failed.

    `available: False` is the flag callers should branch on; `error` stays
    populated for backward compatibility and is never empty.
    """
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    err = (result.get("error") or "").strip()

    match = _MISSING_PKG_RE.search(stdout)
    if match:
        pkg = match.group(1)
        kind = "package_missing"
        reason = (
            f"the R package `{pkg}` is not installed on this machine, so the "
            f"cross-check never ran. This is a fact about this environment, "
            f"not about the paper -- do NOT read it as the engines "
            f"disagreeing. Install with: install.packages('{pkg}')"
        )
    elif "Rscript" in err:
        kind = "r_absent"
        reason = f"{err}. The {package} cross-check cannot run here."
    elif err:
        kind = "r_error"
        reason = err
    else:
        kind = "r_error"
        reason = (
            stderr or stdout
            or f"Rscript exited {result.get('returncode')} with no output"
        )

    return {
        "success": False,
        "available": False,
        "unavailable_reason": kind,
        "package": package,
        "error": reason,
    }


def r_sprite(
    mean: float,
    sd: float,
    n: int,
    scale_min: int = 1,
    scale_max: int = 7,
    num_samples: int = 10,
    decimals: int = 2,
    seed: int = 20260811,
) -> dict:
    """
    Run SPRITE using R's rsprite2 package -- the canonical GROUND TRUTH.

    Use this to cross-check `sprite_reconstruct`. A disagreement between the
    two is a bug in one of them, not evidence about the paper.

    Args:
        mean: Target mean
        sd: Target standard deviation
        n: Sample size
        scale_min: Minimum value on scale
        scale_max: Maximum value on scale
        num_samples: Number of distributions to generate
        decimals: Reported precision of the mean and SD. Pinned into rsprite2 as
            m_prec/sd_prec -- WITHOUT this it infers precision from the literal
            (4.0 reads as 0 decimals) and answers a materially easier question.

    Returns:
        Dictionary with results or error. A raise out of rsprite2 comes back as
        `severity="indeterminate"` with the R message in `r_error`: it is a fact
        about R, not about the paper, and never licenses `impossible`.
    """
    # Build every R literal BEFORE any R runs. `_r_num`/`_r_int` refuse
    # non-finite input, so a NaN mean can no longer reach the R parser and come
    # back as a verdict (see `_r_num`). A bad input is our problem, not the
    # paper's, so it is `indeterminate`.
    try:
        r_mean, r_sd = _r_num(mean), _r_num(sd)
        r_n, r_min, r_max = _r_int(n), _r_int(scale_min), _r_int(scale_max)
        r_decimals, r_samples = _r_int(decimals), _r_int(num_samples)
    except (TypeError, ValueError) as exc:
        return {
            "success": False,
            "infeasible": False,
            "severity": "indeterminate",
            "error": f"inputs cannot be passed to R: {exc}",
            "inputs": {"mean": mean, "sd": sd, "n": n},
            "source": "R rsprite2",
        }

    r_code = f'''
    if (!require("rsprite2", quietly = TRUE)) {{
        cat("ERROR: rsprite2 package not installed. Run: install.packages('rsprite2')")
        quit(status = 1)
    }}

    # SEEDED, for the same reason the Python SPRITE now is. GREG, 2026-08-11:
    # "insofar as we do simulations, we must supply the initial seed for the
    # purposes of reproducibility." rsprite2's search is Monte Carlo, and this
    # tool exists to be the GROUND TRUTH the Python implementation is checked
    # against. An unseeded referee that answers differently on Tuesday cannot
    # settle a disagreement -- and a disagreement is the only occasion this tool
    # is ever consulted about.
    set.seed({int(seed)})

    # set_parameters() RAISES for anything it dislikes -- an unattainable
    # mean/SD pair, an argument it cannot coerce, a scale it rejects -- and the
    # condition message is the only way to tell those apart. It is caught
    # separately so the Python side can label it, but see below: a raise here is
    # NOT proof of infeasibility.
    #
    # m_prec/sd_prec MUST be pinned: rsprite2 otherwise infers precision from
    # the literal (4.0 -> 0 decimals) and silently answers an easier question.
    params <- tryCatch(
        set_parameters(
            mean = {r_mean},
            sd = {r_sd},
            n_obs = {r_n},
            min_val = {r_min},
            max_val = {r_max},
            m_prec = {r_decimals},
            sd_prec = {r_decimals}
        ),
        error = function(e) {{ cat(paste("SETUP_FAILED:", conditionMessage(e), "\\n")); NULL }}
    )

    if (!is.null(params)) tryCatch({{
        results <- list()
        for (i in 1:{r_samples}) {{
            dist <- find_possible_distribution(params)
            # find_possible_distribution() returns a LIST
            # (outcome, values, mean, sd, iterations) -- the previous code called
            # as.integer() on that list, so this wrapper never worked.
            if (!is.null(dist) && !is.null(dist$values)) {{
                results[[length(results) + 1]] <- as.integer(dist$values)
            }}
        }}

        if (length(results) > 0) {{
            cat("SUCCESS\\n")
            for (i in seq_along(results)) {{
                cat(paste(results[[i]], collapse = ","), "\\n")
            }}
        }} else {{
            cat("NO_SOLUTIONS\\n")
        }}
    }}, error = function(e) {{
        cat(paste("ERROR:", conditionMessage(e), "\\n"))
    }})
    '''

    result = run_r_code(r_code)

    if not result.get("success"):
        out = _r_unavailable(result, "rsprite2")
        # `severity` MUST be present. The old branch omitted it, so a caller
        # reading `r.get("severity")` got None on an absent engine -- an
        # unavailable cross-check has to answer the severity question with
        # "we do not know", not with silence.
        out["severity"] = "indeterminate"
        out["infeasible"] = False
        out["note"] = (
            "No cross-check was performed; this is NOT an rsprite2 "
            "disagreement and must not downgrade the Python SPRITE result."
        )
        return out

    stdout = result["stdout"]

    if "SETUP_FAILED:" in stdout:
        # AN R EXCEPTION IS A FACT ABOUT R, NEVER A VERDICT ABOUT A PAPER.
        #
        # Every raise out of set_parameters() used to become
        # `infeasible=True, severity="impossible"` -- the strongest claim this
        # system can make, emitted because a subprocess errored. Measured on
        # mean/SD/n triples computed from REAL integer samples (so a sample
        # provably exists): 16.2% came back `impossible` at the values' correct
        # printed precision, 32.8-41.9% at the 2-dp default. Worked example --
        # the sample (1,5,6,7,7,8,9) gives mean 6.1, sd 2.61, n 7 on a 1-9
        # scale, and rsprite2 raised "the mean is not consistent with this
        # number of observations", which the wrapper published as `impossible`.
        # A NaN mean produced the same verdict off the R parser error
        # "object 'nan' not found".
        #
        # rsprite2 does not distinguish "I proved no sample exists" from "I
        # refuse these arguments" in its condition messages, so the honest
        # reading of ANY raise is that the precondition could not be verified:
        # `indeterminate`. Confirming a real infeasibility needs the Python
        # SPRITE's own analytic screen (`_sd_window_feasible`), which returns a
        # proof rather than an exception.
        return {
            "success": False,
            "infeasible": False,
            "severity": "indeterminate",
            "error": stdout.split("SETUP_FAILED:")[1].strip(),
            "r_error": stdout.split("SETUP_FAILED:")[1].strip(),
            "note": (
                "rsprite2's set_parameters() raised. That is not proof of "
                "infeasibility -- measured at 16.2% on statistics taken from real "
                "integer samples -- so no severity above `indeterminate` may rest "
                "on it."
            ),
            "inputs": {"mean": mean, "sd": sd, "n": n},
            "source": "R rsprite2",
        }

    if "ERROR:" in stdout:
        error_msg = stdout.split("ERROR:")[1].strip()
        return {"success": False, "severity": "indeterminate", "error": error_msg}

    if "NO_SOLUTIONS" in stdout:
        return {
            "success": False,
            "error": "No valid distributions found",
            "inputs": {"mean": mean, "sd": sd, "n": n},
        }

    if "SUCCESS" in stdout:
        lines = stdout.strip().split("\n")[1:]  # Skip "SUCCESS" line
        distributions = []
        for line in lines:
            if line.strip():
                dist = [int(x) for x in line.split(",")]
                distributions.append(dist)

        # Analyze distributions
        import numpy as np

        value_counts = {}
        for val in range(scale_min, scale_max + 1):
            counts = [np.sum(d == val) for d in distributions]
            value_counts[val] = {
                "mean_count": float(np.mean(counts)),
                "min_count": int(np.min(counts)),
                "max_count": int(np.max(counts)),
            }

        # Check for bimodal pattern
        is_bimodal = (
            value_counts[scale_min]["mean_count"] > n * 0.2 and
            value_counts[scale_max]["mean_count"] > n * 0.2
        )

        return {
            "success": True,
            "num_distributions": len(distributions),
            "example_distributions": distributions[:5],
            "value_frequencies": value_counts,
            "is_bimodal": is_bimodal,
            "methodology": f"SPRITE via rsprite2: Generated {len(distributions)} valid distributions.",
        }

    return {"success": False, "error": "Unexpected output from R", "raw": stdout}


def r_grim(mean: float, n: int, items: int = 1, decimals: int = 2,
           percentage: bool = False) -> dict:
    """
    Run GRIM using R's canonical `scrutiny` package, as a ground-truth check.

    TWO BUGS LIVED HERE, and together they made this worse than useless.

    1. `scrutiny::grim()` returns a bare logical vector, not a data frame. The
       R code did `result$consistency`, which errors with "$ operator is invalid
       for atomic vectors" -- so EVERY call returned an error. The one tool whose
       job is to cross-check our GRIM against canonical R before we accuse
       anyone had never once produced a verdict.
    2. The Python side then tested `"CONSISTENT" in stdout` FIRST. "INCONSISTENT"
       contains "CONSISTENT", so had the R side been fixed alone, every failing
       case would have been reported as passing -- an inverted ground truth,
       which is far more dangerous than a broken one.

    Args:
        mean: Reported mean.
        n: Sample size.
        items: Number of items (for multi-item scales).
        decimals: Decimal places the mean was PRINTED to. scrutiny infers
            precision from the literal -- `4.0` and `4.00` are different GRIM
            questions -- so this formats the literal accordingly. It was
            previously accepted and silently ignored.
        percentage: `mean` is a PERCENTAGE (a share, 100*k/n), not a mean.
            Converts to the proportion at `decimals + 2` precision, which is
            the same question `grim_test_percentage` asks -- see below.

    Returns:
        {"consistent": bool, "source": "R scrutiny", "mean_literal": str}
        or {"error": ...}.

    THE PERCENTAGE FLAG IS NOT A CONVENIENCE. MEASURED 2026-08-22 on
    10.1177--0093854811403123: the adjudicator cross-checked a
    `grim_percentage` finding ("28% of the other criminal justice
    professionals", n=41, Python verdict `impossible`) by calling this with
    `mean=28, decimals=0`. R answered `consistent: true` -- correctly, to the
    question it was asked, which is "can 41 integers average 28?" (28*41 = 1148,
    an integer; of course they can). That is not the question. The share
    question is "is 28% a possible k/41?", and 11/41 = 26.83, 12/41 = 29.27,
    so it is not. The adjudicator's second call, `mean=0.28, decimals=2`, got
    `consistent: false` and agreed with Python.

    So the engines "disagreed" because they were asked different things -- the
    same trap as `rsprite2` inferring precision from the literal, in another
    shape, and the same rule: a Python-vs-R comparison must PIN THE QUESTION or
    it is not a comparison. A cross-check that silently answers an easier
    question is worse than none, because it reads as exoneration.
    """
    if percentage:
        # A percentage printed at `decimals` dp carries `decimals + 2` dp as a
        # proportion. Identical to grim_test_percentage's conversion, on
        # purpose: the two engines must format the same literal.
        mean = mean / 100
        decimals = (decimals if decimals is not None else 1) + 2
    mean_literal = f"{mean:.{decimals}f}" if decimals is not None else str(mean)

    r_code = f'''
    if (!require("scrutiny", quietly = TRUE)) {{
        cat("ERROR: scrutiny package not installed. Run: install.packages(\'scrutiny\')")
        quit(status = 1)
    }}

    result <- grim(x = {_r_string(mean_literal)}, n = {_r_int(n)}, items = {_r_int(items)})
    cat(if (isTRUE(as.logical(result)[1])) "GRIM_PASS" else "GRIM_FAIL", "\\n")
    '''

    result = run_r_code(r_code)

    if not result.get("success"):
        out = _r_unavailable(result, "scrutiny")
        out["note"] = (
            "No cross-check was performed. Use the Python GRIM result on its "
            "own and say the second engine was unavailable -- this is NOT a "
            "disagreement between engines."
        )
        return out

    stdout = result["stdout"].strip()
    # Unambiguous tokens: neither is a substring of the other.
    if "GRIM_PASS" in stdout:
        return {"success": True, "available": True, "consistent": True,
                "source": "R scrutiny", "mean_literal": mean_literal,
                "asked_as": "percentage_share" if percentage else "mean"}
    if "GRIM_FAIL" in stdout:
        return {"success": True, "available": True, "consistent": False,
                "source": "R scrutiny", "mean_literal": mean_literal,
                "asked_as": "percentage_share" if percentage else "mean"}
    # R ran and exited 0 but printed neither token: a genuine tooling fault,
    # distinct from the engine being absent.
    return {"success": False, "available": True, "unavailable_reason": "r_error",
            "package": "scrutiny",
            "error": stdout or "scrutiny returned no recognisable verdict"}


def r_statcheck(pdf_path: str) -> dict:
    """
    Run statcheck on a PDF to find and verify statistics.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with statcheck results
    """
    r_code = f'''
    if (!require("statcheck", quietly = TRUE)) {{
        cat("ERROR: statcheck package not installed. Run: install.packages('statcheck')")
        quit(status = 1)
    }}

    tryCatch({{
        result <- checkPDF({_r_string(pdf_path)})
        if (is.null(result) || nrow(result) == 0) {{
            cat("NO_STATS_FOUND\\n")
        }} else {{
            # Output as JSON-like format
            cat("STATS_FOUND\\n")
            cat("n_stats:", nrow(result), "\\n")
            cat("n_errors:", sum(result$Error, na.rm=TRUE), "\\n")
            cat("n_decision_errors:", sum(result$DecisionError, na.rm=TRUE), "\\n")

            for (i in 1:nrow(result)) {{
                cat("---\\n")
                cat("raw:", result$Raw[i], "\\n")
                cat("statistic:", result$Statistic[i], "\\n")
                cat("reported_p:", result$Reported.P.Value[i], "\\n")
                cat("computed_p:", result$Computed[i], "\\n")
                cat("error:", result$Error[i], "\\n")
            }}
        }}
    }}, error = function(e) {{
        cat(paste("ERROR:", e$message, "\\n"))
    }})
    '''

    result = run_r_code(r_code, timeout=120)

    if not result.get("success"):
        return _r_unavailable(result, "statcheck")

    stdout = result["stdout"]

    if "ERROR:" in stdout:
        return {"success": False, "error": stdout}

    if "NO_STATS_FOUND" in stdout:
        return {
            "success": True,
            "stats_found": 0,
            "message": "No statistics found in PDF",
        }

    if "STATS_FOUND" in stdout:
        # Parse the output
        lines = stdout.strip().split("\n")
        stats = []
        current_stat = {}

        for line in lines:
            if line.startswith("n_stats:"):
                n_stats = int(line.split(":")[1].strip())
            elif line.startswith("n_errors:"):
                n_errors = int(line.split(":")[1].strip())
            elif line.startswith("n_decision_errors:"):
                n_decision_errors = int(line.split(":")[1].strip())
            elif line == "---":
                if current_stat:
                    stats.append(current_stat)
                current_stat = {}
            elif ":" in line:
                key, val = line.split(":", 1)
                current_stat[key.strip()] = val.strip()

        if current_stat:
            stats.append(current_stat)

        return {
            "success": True,
            "stats_found": n_stats,
            "errors_found": n_errors,
            "decision_errors": n_decision_errors,
            "statistics": stats,
        }

    return {"success": False, "error": "Unexpected output", "raw": stdout}


def normalise_for_statcheck(text: str) -> str:
    """Repair the four extraction artefacts that make a printed statistic
    invisible to statcheck's regexes.

    EVERY ONE OF THESE IS OUR DAMAGE, NOT THE LITERATURE'S. statcheck reports
    "no statistics found", which reads as a fact about the paper; each item
    below is a measured case where it was a fact about our text channel.

    Normalised HERE rather than by patching the vendored package, because a
    `pip install --upgrade` silently reverts a vendored edit and every one of
    these defects is invisible when it returns.
    """
    import html as _html
    import re as _re

    # 1. HTML ENTITIES. MEASURED: 93.8% of p-value inequalities in the
    #    extracted corpus arrive escaped -- `p &lt; .05`, 22,968 occurrences
    #    across 78% of papers -- because the markdown conversion emits
    #    entities. statcheck looks for a literal `<`. Unescaping recovers
    #    51.8% more statistics and 29% more papers, for one function call.
    text = _html.unescape(text or "")

    # 2. CAPITAL `P` IS A P-VALUE TOO. The vendored package hardcodes
    #    lowercase -- `RGX_P = "(p\\s?[<>=]\\s?\\d?\\.\\d+e?-?\\d*)"` -- so a
    #    paper in PNAS/Nature/medical house style yields ZERO.
    #
    #    MEASURED 2026-08-13 over 119 corpus papers carrying p-values: 31 (26%)
    #    use CAPITAL P ONLY. Every one was silently unstatcheckable. Found while
    #    testing Ophir 2009, the candidate list's "highest density of
    #    statcheck-eligible statistics" -- it yielded 0. Scoped to the p-value
    #    context (`P` followed by a comparator and a number) so an ordinary
    #    capital P -- a variable, a panel label -- is untouched.
    text = _re.sub(r"\bP(\s?[<>=]\s?\d*\.?\d)", r"p\1", text)

    # 3. DOCLING RENDERS `<` AS `\` IN SOME PDFs. MEASURED 2026-08-22 on
    #    10.1007--s10803-013-1829-4 (Springer): 15 occurrences of `p \ .001`
    #    and ZERO of `p <`. Every `p < .001` in the paper was invisible.
    #    Repairing them takes statcheck from 26 to 37 statistics (+42%) on that
    #    one paper. Same scoping discipline as the capital-P rule -- only a
    #    backslash sitting between `p` and a number is touched, so a LaTeX
    #    fragment or a path elsewhere in the text is left alone.
    text = _re.sub(r"(\bp\s*)\\(\s*\.?\d)", r"\1<\2", text)

    # 4. RUNS OF WHITESPACE DEFEAT THE REGEX ENTIRELY. statcheck matches a
    #    single optional space between the tokens, so a scanned two-column PDF
    #    whose text layer preserves inter-word padding yields nothing:
    #
    #        'F(2, 33) = 5.76, p = .008'      -> 1 statistic
    #        'F(2,  33)  =  5.76, p  =  .008' -> 0 statistics
    #
    #    MEASURED 2026-08-22 on 10.1037--0022-3514.71.2.230 (Bargh, Chen &
    #    Burrows 1996, an old scan): the whole-text channel found 0 of 4.
    #    Collapsing runs of horizontal whitespace recovers all 4. Line breaks
    #    are NOT collapsed -- statcheck's own line handling depends on them.
    text = _re.sub(r"[ \t\u00a0\u2007\u202f]+", " ", text)

    return text


def python_statcheck(pdf_path: str) -> dict:
    """Run statcheck on a PDF.

    ONE TOOL, ONE ANSWER. This used to be a second implementation wearing the
    same name: it called statcheck's own `checkPDFdir` and then counted raw
    upstream `Error` flags, with NONE of the normalisations in
    `normalise_for_statcheck` and NONE of `python_statcheck_text`'s
    rounding-interval filter. The two entry points disagreed badly on real
    papers (MEASURED 2026-08-22):

      * 10.1007--s10803-013-1829-4 -- this path reported `errors_found: 25`;
        the filtered text path reports 1. Twenty-four of those "errors" were
        p-values correct at their own printed precision.
      * 10.1037--0022-3514.71.2.230 -- this path emitted a mangled
        `t(28 ) = 2.86, p < .0` (the scan's `.01` lost its `1`) and flagged it
        as an error.
      * 10.1177--0093854811403123 -- this path found 1 statistic where the
        repo's own extraction yields 13.

    A model handed `errors_found: 25` and a model handed `errors_found: 1` are
    reading two different papers. So the PDF is read through the repo's own
    extraction (docling, served from the content-hash cache -- by the time a
    stage calls this the paper is already extracted, so it costs nothing) and
    the text is handed to `python_statcheck_text`. Everything downstream --
    the four normalisations, `correct_at_printed_precision`,
    `errors_explained_by_rounding`, the base-rate methodology note -- is
    inherited rather than reimplemented.

    `checkPDFdir` remains as the FALLBACK for a PDF our extractor cannot read,
    so a paper that used to yield statistics still does.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with statcheck results, plus `pdf_reader` naming which
        reader supplied the text.
    """
    from pathlib import Path as PathLib

    pdf_path = PathLib(pdf_path)
    if not pdf_path.exists():
        return {"success": False, "error": f"File not found: {pdf_path}"}

    text = ""
    try:
        from ..extraction.pdf import extract_text_with_tables
        text = (extract_text_with_tables(
            str(pdf_path), max_chars=2_000_000).get("text") or "")
    except Exception:  # noqa: BLE001 -- fall through to the vendored reader
        text = ""

    if text.strip():
        out = python_statcheck_text(text)
        if isinstance(out, dict):
            out["pdf_reader"] = "docling"
            out["pdf_chars"] = len(text)
        return out

    return _statcheck_pdf_via_vendored_reader(pdf_path)


def _statcheck_pdf_via_vendored_reader(pdf_path) -> dict:
    """statcheck's own `checkPDFdir`, for a PDF our extractor cannot read.

    Results go through the SAME rounding-interval filter as the text path, so
    the two readers still answer the same question about the same paper.
    """
    _patch_statcheck()
    try:
        from statcheck.checkdir import checkPDFdir
    except ImportError:
        return {
            "success": False,
            "error": "Python statcheck not installed. Run: pip install statcheck",
        }

    import tempfile
    import shutil
    from pathlib import Path as PathLib

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_pdf = PathLib(tmpdir) / PathLib(pdf_path).name
        shutil.copy(pdf_path, tmp_pdf)

        try:
            results_df, _ = checkPDFdir(tmpdir, subdir=False)
        except Exception as e:
            return {"success": False, "error": f"Statcheck failed: {str(e)}"}

    if results_df is None or len(results_df) == 0:
        return {
            "success": True,
            "stats_found": 0,
            "pdf_reader": "statcheck_pdfminer",
            "message": "No statistics found in PDF",
        }

    out = _statcheck_rows(results_df)
    out["pdf_reader"] = "statcheck_pdfminer"
    return out


#: Set once `_patch_statcheck_sign_bug` has run, so the repair is idempotent and
#: so a caller can assert it happened.
_STATCHECK_SIGN_PATCHED = False

#: WHY THE SIGN REPAIR IS NOT IN FORCE, or None. Same reasoning as
#: `_STATCHECK_PDEC_UNAVAILABLE` below: returning False said "not installed"
#: and threw away WHY, so a caller could not tell a missing dependency from a
#: broken one. `lint-inert` flagged this site as `swallowed_failure` when the
#: shim landed in cf2e3cb, and the ratchet has been one over its pin since.
_STATCHECK_SIGN_UNAVAILABLE: str | None = None


def _patch_statcheck_sign_bug() -> bool:
    """Repair PyPI statcheck 0.0.7's transposed bounds for NEGATIVE statistics.

    THE BUG, reproduced minimally. `error_test` builds the rounding box on the
    SIGNED statistic and then assigns the two computed p-values by position:

        low_stat = test_stat - .5/10**test_dec
        up_stat  = test_stat + .5/10**test_dec
        up_p  = compute_p(test_stat=low_stat, ...)
        low_p = compute_p(test_stat=up_stat, ...)

    For a positive t that is right, because p falls as |t| rises. For a negative
    t it is backwards: `low_stat` has the LARGER magnitude and therefore the
    SMALLER p, so `low_p` and `up_p` arrive swapped and every subsequent
    comparison is made against an inverted interval.

    MEASURED, and it is a false accusation against an honest paper:

        t(20) = -2.00, p = .059  ->  error_test says error=True
        t(20) = +2.00, p = .059  ->  error_test says error=False

    The true interval is [0.0537, 0.0653] in both cases and .059 is inside it.
    Only the sign differs. An independent validation sweep put this at 30.3% of
    honest negative-statistic reports surviving our own guard as
    `errors_found`, against 0 of 952 for the reference R implementation -- the
    single largest false-accusation channel measured anywhere in the toolkit,
    and it is not our arithmetic.

    WHY THE REPAIR LIVES HERE AND NOT IN site-packages. Editing the installed
    package would be invisible to review, absent from the diff, and silently
    undone by the next `pip install`. This wraps the function at import time,
    enforces the ordering its own variable names assert, and leaves a flag a
    test can assert on.

    ORDERING, NOT abs(). Swapping when they arrive transposed is correct for
    every test type and both tail conventions, and it makes no assumption about
    how `compute_p` treats sign -- whereas rewriting the box as |stat| would
    change one-tailed behaviour we have not measured.

    Returns True if the patch is in place. Never raises: statcheck is optional
    and a failure here must degrade to the unpatched engine, not kill a run.
    """
    global _STATCHECK_SIGN_PATCHED
    if _STATCHECK_SIGN_PATCHED:
        return True
    global _STATCHECK_SIGN_UNAVAILABLE
    try:
        from statcheck import error_test as _et_mod
    except Exception as exc:                                 # noqa: BLE001
        _STATCHECK_SIGN_UNAVAILABLE = (
            f"statcheck's internals are not importable: {type(exc).__name__}: {exc}")
        return False

    original = getattr(_et_mod, "error_test", None)
    if original is None or getattr(original, "_fmt_sign_patched", False):
        _STATCHECK_SIGN_PATCHED = original is not None
        return _STATCHECK_SIGN_PATCHED

    def sign_safe(reported_p, test_type, test_stat, df1, df2, p_comparison,
                  test_comparison, p_dec, test_dec, two_tailed, alpha,
                  pZeroError):
        try:
            stat = float(test_stat)
        except (TypeError, ValueError):
            return original(reported_p, test_type, test_stat, df1, df2,
                            p_comparison, test_comparison, p_dec, test_dec,
                            two_tailed, alpha, pZeroError)
        # For a negative statistic the box is transposed. Passing |stat| gives
        # error_test the ordering its own names assume; the p-values it then
        # computes are identical, because compute_p for these tests depends on
        # the magnitude.
        return original(reported_p, test_type, abs(stat), df1, df2,
                        p_comparison, test_comparison, p_dec, test_dec,
                        two_tailed, alpha, pZeroError)

    sign_safe._fmt_sign_patched = True
    sign_safe.__doc__ = (original.__doc__ or "") + "\n\nFMT: sign-safe wrapper."
    _et_mod.error_test = sign_safe

    # REBINDING THE DEFINING MODULE IS NOT ENOUGH, and assuming it was is how a
    # fix ships and changes nothing. `process_stats.py` does
    # `from statcheck.error_test import error_test`, which copies the function
    # object into ITS namespace at import time -- so the real pipeline
    # (st.statcheck -> process_stats) would keep calling the broken original
    # while a test on the defining module reported the patch as installed.
    # Found by a test asserting the other modules see it.
    #
    # So: walk every loaded statcheck module and rebind any name still pointing
    # at the original. `decision_error_test` needs no repair -- it receives
    # `computed_p` as an argument and derives no bounds of its own.
    import sys
    for name, mod in list(sys.modules.items()):
        if not name.startswith("statcheck") or mod is None:
            continue
        for attr in dir(mod):
            try:
                if getattr(mod, attr, None) is original:
                    setattr(mod, attr, sign_safe)
            except Exception:                                # noqa: BLE001
                continue
    _STATCHECK_SIGN_PATCHED = True
    return True


#: Set once `_patch_statcheck_p_dec_bug` has run. Separate from the sign flag:
#: the two repairs are independent and either can be installed without the other.
_STATCHECK_PDEC_PATCHED = False

#: WHY THE REPAIR IS NOT IN FORCE, or None. A silent `except: return` here would
#: hand back upstream's WRONG p_dec with nothing recording that the fix did not
#: apply -- absence rendered as knowledge, on the exact path the fix exists to
#: correct. `lint-inert` flagged both sites in this shim as `swallowed_failure`
#: and it was right. A caller (and `test_inertness`) can read this.
_STATCHECK_PDEC_UNAVAILABLE: str | None = None


def _p_decimals(text: str) -> int | None:
    """Decimal places a printed p-value asserts, including in e-notation.

    R's rule -- `attr(regexpr("\\.\\d+", p), "match.length") - 1` -- counts the
    MANTISSA's decimals and never looks at the exponent, so it calls `1.5e-1`
    (which is 0.15, two decimal places) and `1.5e-2` (0.015, three) both ONE.
    The port is wrong here too, and differently. All three answers for
    `9.9e-4`, whose true precision is 5 decimal places:

        upstream port  2      R      1      correct  5

    Being too FEW is not the harmless direction it looks. `error_test` compares
    the reported p against `round(low_p, p_dec)` and `round(up_p, p_dec)`, so an
    undercount does not merely widen the window -- it COLLAPSES both bounds onto
    a coarse grid, and an honest value lands outside them. Measured over 300
    honest results printed in scientific notation: 203 of 300 flagged as errors
    by the unrepaired reader, 0 of 300 once the precision is computed correctly.

    GREG FITZGERALD PROPOSED THE FIX, 2026-08-27: "would you recommend converting
    it into a decimal for the sake of analysis? This is close enough to exact
    preservation of the printed values that it doesn't violate any of the rules
    for pre-processing." It is not close enough -- it is EXACT. Scientific
    notation asserts precision in the mantissa, and the shifted decimal asserts
    the identical interval:

        1.5e-1  -> 0.15    mantissa window [0.145, 0.155)  = decimal window
        1.50e-1 -> 0.150   mantissa window [0.1495, 0.1505) = decimal window

    So `decimals = mantissa_decimals - exponent`, and the paper's own literal is
    never altered -- only the derived precision.

    THE ONE CASE THAT MUST REFUSE. A positive exponent can drive the count
    negative: `1.5e3` asserts [1450, 1550), and no count of decimal places can
    express a precision COARSER than one unit -- reading it as "1500 at 0 dp"
    gives [1499.5, 1500.5), a window 100x too tight, which is the direction that
    accuses. Returns None there, and the caller leaves upstream's value alone.
    p-values never reach it; this module is not the only future caller.

    DELIBERATELY DIVERGES FROM R, and that is the point. The warrant for the
    surrounding shim is "match R where R is right". Here R is demonstrably
    wrong and the correct answer is checkable by hand.
    """
    from .rounding import decimals_of_text

    s = (text or "").strip()
    if "e" not in s.lower():
        d = decimals_of_text(s)
        return 0 if d is None else d
    try:
        mant, exp = re.split("[eE]", s, maxsplit=1)
        e = int(exp)
    except (ValueError, TypeError):
        return None
    mant_dec = len(mant.split(".")[1]) if "." in mant else 0
    dec = mant_dec - e
    return dec if dec >= 0 else None


def _patch_statcheck_p_dec_bug() -> bool:
    """Restore R's rule for how many decimals a p-value was PRINTED to.

    THE BUG, in the installed package. `helpers_parse_stats.py` splits the
    matched fragment on the comparison operator, then measures the decimals:

        249:  p_value.append(re.split(RGX_COMP, p_raw[i])[1])
        251:  # remove leading/trailing whitespaces      <- comment, NO CODE
        254:  dec = re.search(RGX_DEC, p_value[i]).end() - 2   # not sure

    R does two things this does not:

        p_value <- trimws(p_value, which = "both")
        dec <- attr(regexpr(RGX_DEC, p_value), "match.length") - 1

    `match.length` is position-independent. `.end()` is not -- it equals
    `start + length`, so the port carries the match's START as an error term,
    and R's missing `trimws` is what lets a leading space (which `RGX_P`
    explicitly permits) push that start along. Net error is `start - 1`:

        " .049"    port 3, R 3   right, by cancellation
        " 0.049"   port 4, R 3   INFLATED  -> band 10x too tight, ACCUSES
        ".049"     port 2, R 3   DEFLATED  -> band 10x too loose, MISSES
        "0.049"    port 3, R 3   right, by cancellation

    `p_dec` is the only place the reported p's printed precision enters
    `error_test`'s comparison, so +1 there narrows the acceptance band by a
    factor of ten. This is the same class as the sign bug above and it is
    likewise not our arithmetic.

    SCIENTIFIC NOTATION IS DELIBERATELY LEFT ALONE, and that is not laziness.
    R's rule counts the MANTISSA's decimals and never sees the exponent, so it
    calls both `1.5e-1` (2 dp) and `1.5e-2` (3 dp) one decimal. Applying the
    rule faithfully there manufactures accusations: measured over 1,200 honest
    e-notation results, `errors_found` went 0 -> 17. `rounding.decimals_of_text`
    already refuses this family for the same reason. The warrant for this shim
    is "match R where R is right", not "match R".

    Returns True if the repair is installed (or already was).
    """
    global _STATCHECK_PDEC_PATCHED
    if _STATCHECK_PDEC_PATCHED:
        return True
    global _STATCHECK_PDEC_UNAVAILABLE
    try:
        from statcheck import helpers_parse_stats as _hps
        from statcheck.helpers_parse_stats import extract_pattern
        from statcheck.regex import RGX_P_NS, RGX_NS, RGX_COMP
    except Exception as exc:                                 # noqa: BLE001
        _STATCHECK_PDEC_UNAVAILABLE = (
            f"statcheck's internals are not importable: {type(exc).__name__}: {exc}")
        return False

    original = getattr(_hps, "extract_p_value", None)
    if original is None:
        return False
    if getattr(original, "_fmt_pdec_patched", False):
        _STATCHECK_PDEC_PATCHED = True
        return True

    def r_faithful(raw):
        df = original(raw)
        try:
            p_raw = extract_pattern(txt=raw, pattern=RGX_P_NS)
            # FAIL CLOSED. If our re-extraction does not line up row-for-row
            # with upstream's frame we are not looking at the same statistics,
            # and writing into it by position would corrupt every p_dec rather
            # than repair one. Leave upstream's answer untouched.
            if len(p_raw) != len(df) or "p_dec" not in df.columns:
                return df
            col = df.columns.get_loc("p_dec")
            for i, chunk in enumerate(p_raw):
                if re.search(RGX_NS, chunk, flags=re.IGNORECASE):
                    continue                    # "ns" -> p_dec is NaN by design
                parts = re.split(RGX_COMP, chunk)
                if len(parts) < 2:
                    continue
                s_val = parts[1].strip()                      # R: trimws
                dec = _p_decimals(s_val)
                if dec is None:
                    continue           # coarser than one unit; not expressible
                df.iat[i, col] = dec
        except Exception as exc:                             # noqa: BLE001
            # NEVER FAIL A RUN OVER THIS -- but never hide it either. Upstream's
            # p_dec is returned unrepaired, which is the value that accuses, so
            # a reader of this module must be able to tell that happened.
            global _STATCHECK_PDEC_UNAVAILABLE
            _STATCHECK_PDEC_UNAVAILABLE = (
                f"p_dec left unrepaired on one call: {type(exc).__name__}: {exc}")
            return df
        return df

    r_faithful._fmt_pdec_patched = True
    r_faithful.__doc__ = (original.__doc__ or "") + "\n\nFMT: R-faithful p_dec."
    _hps.extract_p_value = r_faithful

    # THE SAME TRAP THE SIGN SHIM DOCUMENTS. `extract_stats.py` and `st.py` do
    # `from statcheck.helpers_parse_stats import extract_p_value`, copying the
    # object at import time, so rebinding the defining module alone would leave
    # the real pipeline calling the original while a test reported success.
    import sys
    for name, mod in list(sys.modules.items()):
        if not name.startswith("statcheck") or mod is None:
            continue
        for attr in dir(mod):
            try:
                if getattr(mod, attr, None) is original:
                    setattr(mod, attr, r_faithful)
            except Exception:                                # noqa: BLE001
                continue
    _STATCHECK_PDEC_PATCHED = True
    return True


def _patch_statcheck() -> bool:
    """Install every repair we carry for the upstream statcheck port.

    ONE ENTRY POINT ON PURPOSE. The sign shim was called from the text path and
    NOT from `_statcheck_pdf_via_vendored_reader`, so a paper read through
    statcheck's own PDF reader was still scored with the transposed bounds --
    a fix that existed and did not reach half its callers. A single function
    that both paths call is the shape that stops that recurring.
    """
    return _patch_statcheck_sign_bug() and _patch_statcheck_p_dec_bug()


def python_statcheck_text(text: str) -> dict:
    """
    Run statcheck on raw text using the Python implementation.

    This accepts text directly (e.g., from markdown or extracted PDF content)
    instead of requiring a PDF file.

    Args:
        text: Raw text containing statistical results in APA format

    Returns:
        Dictionary with statcheck results
    """
    text = normalise_for_statcheck(text)

    _patch_statcheck()
    try:
        from statcheck.st import statcheck
    except ImportError:
        return {
            "success": False,
            "error": "Python statcheck not installed. Run: pip install statcheck",
        }

    if not text or not text.strip():
        return {"success": False, "error": "Empty text provided"}

    try:
        results_df, _ = statcheck(text)
    except Exception as e:
        return {"success": False, "error": f"Statcheck failed: {str(e)}"}

    if results_df is None or len(results_df) == 0:
        return {
            "success": True,
            "stats_found": 0,
            "message": "No statistics found in text",
        }

    return _statcheck_rows(results_df)


def _statcheck_rows(results_df) -> dict:
    """Turn a statcheck results frame into the tool's result dict.

    SHARED BY BOTH ENTRY POINTS ON PURPOSE. The PDF path used to carry its own
    copy of this loop WITHOUT the `correct_at_printed_precision` filter, and so
    reported 25 errors where this one reports 1 on the same paper.
    """
    stats = []
    n_errors = 0
    n_decision_errors = 0

    for _, row in results_df.iterrows():
        # Handle both R-style and Python-style column names
        reported_p = row.get("Reported_P_Value", row.get("Reported.P.Value", row.get("reported_p", "")))
        computed_p = row.get("Computed_P_Value", row.get("Computed", row.get("computed_p", "")))
        error = row.get("Error", False)
        decision_error = row.get("Decision_Error", row.get("DecisionError", False))

        stat = {
            "raw": str(row.get("Raw", "")),
            "statistic": str(row.get("Statistic", "")),
            "df1": str(row.get("df1", "") if row.get("df1") is not None else ""),
            "df2": str(row.get("df2", "") if row.get("df2") is not None else ""),
            "reported_p": f"{reported_p:.6f}" if isinstance(reported_p, (int, float)) else str(reported_p),
            "computed_p": f"{computed_p:.6f}" if isinstance(computed_p, (int, float)) else str(computed_p),
            "error": bool(error),
            "decision_error": bool(decision_error),
        }
        stats.append(stat)

        # Upstream statcheck compares against the p-value it parsed, not against
        # the precision the p-value was PRINTED at. So `r(51)=-0.167, p=0.232`
        # with a computed p of 0.232008 is flagged as an error, though 0.232 is
        # the correct 3-dp rendering of it. Measured on one real paper: 11 of 33
        # flags (33%) were correct at their own printed precision.
        #
        # This is the same rounding-interval principle the GRIM family uses: a
        # printed number asserts an interval, not a point.
        stat["correct_at_printed_precision"] = _within_printed_precision(
            stat["raw"], reported_p, computed_p
        )
        if stat["error"] and not stat["correct_at_printed_precision"]:
            n_errors += 1
        if stat["decision_error"]:
            n_decision_errors += 1

    n_raw_flags = sum(1 for s in stats if s["error"])
    n_rounding = sum(1 for s in stats if s["error"] and s["correct_at_printed_precision"])

    return {
        "success": True,
        "stats_found": len(stats),
        "errors_found": n_errors,
        "errors_flagged_upstream": n_raw_flags,
        "errors_explained_by_rounding": n_rounding,
        "decision_errors": n_decision_errors,
        "statistics": stats,
        "methodology": (
            f"Python statcheck: extracted {len(stats)} NHST results. Upstream flagged "
            f"{n_raw_flags}; {n_rounding} of those are correct at the precision the p-value was "
            f"printed to and are NOT counted as errors, leaving {n_errors}. "
            f"{n_decision_errors} decision errors (a p-value on the wrong side of its own "
            "significance threshold). Only decision errors change a conclusion; inconsistencies "
            "are near-universal in honest work -- roughly half of clean control papers contain at "
            "least one -- and must never support a misconduct verdict on their own."
        ),
    }


def _within_printed_precision(raw: str, reported_p, computed_p) -> bool:
    """Does the computed p round to the reported p at the precision PRINTED?

    A p printed as `.232` asserts the interval [.2315, .2325); a computed
    .232008 sits inside it and is therefore correctly reported, whatever the
    upstream exact comparison says.
    """
    try:
        rp, cp = float(reported_p), float(computed_p)
    except (TypeError, ValueError):
        return False
    # Recover the printed precision from the literal, not from the parsed float:
    # `p=.05` asserts 2 dp, and treating it as 6 would shrink the interval
    # 10,000-fold and manufacture a discrepancy.
    # ONLY AN EXACT p HAS A ROUNDING INTERVAL. "p < .01" is a bound written
    # exactly: rounding the computed p to the bound's decimals cancelled real
    # errors (`t(15) = 2.75, p < .01`, true p .0149 -> round(.0149, 2) == .01).
    # MEASURED 2026-10-18 on the Wicherts, Bakker & Molenaar (2011) hand coding
    # (benchmarks/pvalue_tools): 31 of 49 labelled errors were flagged by
    # statcheck and then cancelled here.
    match = re.search(r"p\s*=\s*(\d*\.\d+|\d+)", str(raw), re.IGNORECASE)
    if not match:
        return False
    decimals = _rounding.decimals_of_text(match.group(1))
    if decimals is None:
        return False
    return round(cp, decimals) == round(rp, decimals)
