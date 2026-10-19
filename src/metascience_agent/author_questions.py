"""What we may fairly ask the authors, and what we may not.

TWO DEFECTS, BOTH FOUND BY GREG IN ONE SENTENCE OF A REAL RUN
(`10.1038--s41537-025-00576-3`, question 7 of 7):

    "Supplementary eTable 5 CONTAINS the BIC and other fit indices used to
     select the four-class solution. Could those values BE REPORTED IN THE MAIN
     TEXT or supplied as a plain CSV, together with the entropy and average
     class-membership probabilities for the 2- to 6-class models?"

Greg:

    "one of the author questions ... sounds insane because it is seeming to
     imply that information can be added to the main text of an article that has
     already been published (and is therefore uneditable) and also seems to be
     impugning the authors for OUR lack of the supplementary materials!"

Both halves are right.

1. AN UNEDITABLE ASK. The article is published. Its main text cannot be
   changed, and a request to change it is not a question anyone can answer -- it
   reads as either ignorance of how publishing works or a demand for a
   correction we have not earned. Everything we want can be SENT to us instead.

2. BLAMING THE AUTHORS FOR OUR OWN GAP. The sentence says eTable 5 CONTAINS the
   values. The authors deposited them. We did not fetch the file. Phrasing our
   retrieval failure as their reporting failure is unfair in the specific way
   this toolkit exists to avoid: it manufactures a criticism out of our own
   limitation, which is a false accusation with extra steps.

GREG'S RULE, which this module implements:

    "for ANY publication for which we are lacking any known supplementary
     materials (well, except preregistrations) the first author question should
     be a polite request for the supplement (on the assumption that the sender
     currently lacks access). To do otherwise would be unfair to the authors."

WHY THIS IS CODE AND NOT ONLY A PROMPT LINE. The prompt is instructed too (see
`prompts/stage2_editorial.md`), but a prompt is a hope. The house failure in
this repo is a rule that was written down, tested once, and then not applied on
the path that matters. So the supplement request is PREPENDED deterministically
whenever the audit says material is missing, and the uneditable-ask detector
runs over every question the model wrote and reports what it finds. The
detector does not rewrite the model's prose -- silently editing an outgoing
question is its own way of shipping something nobody reviewed -- it makes the
defect countable, which is the thing that lets us tell whether the prompt
worked.
"""
from __future__ import annotations

import re

#: Phrases that ask the authors to CHANGE THE PUBLISHED ARTICLE. Each is a
#: request no author can grant: the version of record is fixed, and altering it
#: means a correction notice, which is not ours to ask for and not what we
#: wanted anyway -- we wanted the numbers.
#:
#: Deliberately narrow. It matches asks aimed at the PAPER ("report in the main
#: text", "add to the manuscript"), never asks aimed at US ("could you supply",
#: "could you send", "could you provide"), which are the correct form and by far
#: the commonest. A detector that fired on "provide" would flag almost every
#: legitimate question and be switched off within a week.
_UNEDITABLE_ASKS = (
    r"\b(report(ed|ing)?|includ(e|ed|ing)|add(ed|ing)?|stat(e|ed)|present(ed)?|"
    r"insert(ed)?|list(ed)?|specif(y|ied))\b[^.?!]{0,60}?\bin\s+the\s+"
    r"(main\s+)?(text|manuscript|article|paper|body)\b",
    r"\b(amend|revis(e|ing)|correct(ing)?|updat(e|ing)|edit(ing)?)\b[^.?!]{0,40}?"
    r"\bthe\s+(main\s+)?(text|manuscript|article|paper)\b",
    r"\badd(ed|ing)?\b[^.?!]{0,40}?\bto\s+the\s+(main\s+)?"
    r"(text|manuscript|article|paper)\b",
)
_UNEDITABLE_RE = tuple(re.compile(p, re.I) for p in _UNEDITABLE_ASKS)

#: The one exception Greg carved out. A preregistration is not supplementary
#: material the authors would send on request -- it is a public record that
#: either exists at a registry or does not, and asking for it as a favour
#: misdescribes what it is. Absent preregistrations stay in the findings, where
#: they belong.
PREREGISTRATION_IS_EXEMPT = True


def find_uneditable_asks(questions) -> list[dict]:
    """Questions that ask the authors to change an article already published.

    Returns one record per offending question: its index, its text, and the
    exact span that matched, so a reader can see WHY it was flagged rather than
    taking the flag on trust. An empty list is the normal, good outcome.
    """
    out: list[dict] = []
    for i, q in enumerate(questions or []):
        text = (q.get("question") if isinstance(q, dict) else str(q or "")) or ""
        for rx in _UNEDITABLE_RE:
            m = rx.search(text)
            if m:
                out.append({
                    "index": i,
                    "question": text,
                    "matched": m.group(0),
                    "problem": (
                        "asks the authors to change the PUBLISHED article, which "
                        "cannot be edited. Ask for the values to be SENT instead."
                    ),
                })
                break
    return out


def supplement_request(audit: dict | None, *, paper_cites: str | None = None) -> dict | None:
    """The polite first question, when we are missing material the paper has.

    Returns a question record in `questions_for_authors` shape, or None when no
    request is warranted.

    WHEN IT FIRES. Only on `audit["missing"] is True` -- the audit's own
    three-valued answer, where True means the paper cites supplementary material
    and we do not hold it. The other two values are deliberately NOT triggers:

      False  the paper cites none, or we have what it cites. Asking anyway
             wastes the one piece of goodwill a cold email gets.
      None   we could not read the paper at all, so we do not know whether it
             cites anything. `supplements.audit` is explicit that None is not
             "no", and a caller that treats it as one has reinstated the bug
             that module documents at length. Here it is equally wrong to treat
             it as "yes": inventing a request for material we have no evidence
             exists is a different way of being unfair to the authors. When we
             cannot read the paper, the honest output is the refusal that is
             already reported elsewhere, not a speculative ask.

    THE WORDING assumes the sender lacks access, which is Greg's instruction and
    is also simply true: the overwhelmingly likely reason we do not have the
    file is a paywall, a broken deposit link, or a repository we did not query
    -- not an author who withheld it. So the sentence carries no reproach, makes
    no claim about what the supplement does or does not contain, and does not
    imply anyone failed to deposit anything.
    """
    if not isinstance(audit, dict) or audit.get("missing") is not True:
        return None

    cited = paper_cites or _cited_phrase(audit)
    question = (
        "Would you be able to send the supplementary material for this paper? "
        f"{cited} but we have not been able to obtain "
        "it, and several of the values we would want to check appear to be "
        "there rather than in the main text. If it is easier, the underlying "
        "summary statistics on their own would be just as useful."
    )
    return {
        "question": question,
        "why": (
            "We do not hold the supplement this paper cites. This is OUR gap -- "
            "the usual causes are a paywall, a dead deposit link, or a "
            "repository we did not query -- and it must be put to the authors "
            "as a request, never as a criticism of their reporting. Placed "
            "first because everything downstream may be answered by the file "
            "itself, and because a reader who sees the later questions without "
            "this one will not know that some of them may already have answers "
            "we simply could not read."
        ),
        "finding_ids": [],
        "generated_by": "pipeline",
        "kind": "supplement_request",
    }


#: A refusal typed `paper` says the publication does not print what a check
#: needed. Most of those are not questions -- "statcheck found zero statistics"
#: is a remark about a reporting style, and putting it to an author as a
#: question is a criticism wearing a question mark.
#:
#: TWO SHAPES ARE. Both are named by the taxonomy's own definition of the
#: bucket ("where the paper CLAIMS to have used something it never prints, that
#: is a question worth putting to the authors") and both are ANSWERABLE by
#: sending a number, which is the test every question here has to pass.
#:
#: MEASURED over 128 distinct `paper` refusals in the archive: 15 match (a) and
#: 10 match (b) once the review's own limits are excluded. The remaining 101
#: stay refusals. A promotion rule that fired on all 128 would fill the
#: Questions page with reproaches.
_STATED_BUT_NOT_SHOWN = re.compile(
    r"\b(?:states?|asserts?|claims?|reports?|says?|declares?|concludes?|"
    r"describes?|names?)\b[^.]{0,150}?\bbut\b[^.]{0,120}?"
    r"\b(?:no|none|never|not)\b", re.I)

_ONLY_IN_A_FIGURE = re.compile(
    r"\bexists?\s+only\s+(?:as|in)\b|"
    r"\bonly\s+as\s+(?:bars?|marks?|a\s+(?:bar|chart|line))|"
    r"\bas\s+(?:bar\s+heights|chart\s+marks)\b", re.I)

#: THE FAIRNESS GUARD, and the reason promotion is gated more tightly than
#: classification. Two archived rows read "No figure of any kind was viewed in
#: this review" -- a statement about OUR pass that mentions charts in passing.
#: Promoted, it becomes a question asking authors to account for a gap we
#: created. Anything that describes the review rather than the article is
#: excluded, whatever bucket it landed in.
_ABOUT_OUR_REVIEW = re.compile(
    r"\bin\s+this\s+review\b|\b(?:was|were|could\s+be)\s+(?:viewed|inspected)\b|"
    r"\bnot\s+run\s+by\s+(?:this|the)\s+review\b|\bour\s+(?:pass|review|sweep)\b",
    re.I)

#: Fixed and deliberately claimless. The one thing it asserts -- that we could
#: not find the values in the article as published -- is a fact about US, and it
#: is true by construction: it is why the check was refused. Everything specific
#: rides in the VERBATIM refusal text, attributed to the review that wrote it,
#: rather than being paraphrased into an accusation by a template.
_REQUEST = (
    "Would you be able to share the underlying values for this? Our reading of "
    "the article as published did not locate them, though they may well be "
    "somewhere we did not look, or in material we were not able to obtain. "
    "Summary statistics on their own would be enough."
)


def promotable_refusals(not_checked) -> list[dict]:
    """Refusals that are legitimately questions for the authors.

    A check we declined to run because the paper does not print an input is not,
    by itself, a criticism -- but where the paper SAYS it did something and does
    not show the numbers, or where the numbers exist only as marks on a chart,
    asking for them is both fair and answerable. Those are the only two shapes
    promoted; everything else stays where it is.

    The question text is FIXED (see `_REQUEST`). The pipeline does not write
    prose about a paper it has not verified: the specific claim stays quoted,
    verbatim, as the review's own words.
    """
    from .viewer_facts import classify_refusal

    out: list[dict] = []
    for row in (not_checked or []):
        if not isinstance(row, dict):
            continue
        reason = " ".join(str(row.get("reason") or "").split())
        if not reason or classify_refusal(reason)["key"] != "paper":
            continue
        if _ABOUT_OUR_REVIEW.search(reason):
            continue
        if _STATED_BUT_NOT_SHOWN.search(reason):
            shape = "stated_but_not_shown"
        elif _ONLY_IN_A_FIGURE.search(reason):
            shape = "only_in_a_figure"
        else:
            continue
        location = str(row.get("location") or "").strip()
        out.append({
            "question": (f"{location}: {_REQUEST}" if location else _REQUEST),
            "why": (
                "Promoted from a check this review could not run. The review "
                f"recorded: “{reason}” That is quoted rather than "
                "paraphrased, because the sentence is this review's reading and "
                "not a verified fact about the article -- if it is mistaken, the "
                "answer is simply that the values are where we did not look."
            ),
            "finding_ids": [],
            "generated_by": "pipeline",
            "kind": "unreported_value_request",
            "shape": shape,
            "location": location,
            "refusal_reason": reason,
        })
    return out


def _cited_phrase(audit: dict) -> str:
    """One clause naming what the paper cites, from the audit's own counts.

    Kept vague where the audit is vague. Naming "eTable 5" when the audit only
    counted references would be us asserting a specific about a file we have
    never opened.
    """
    n = audit.get("reference_count") or 0
    styles = audit.get("styles") or {}
    if styles:
        named = ", ".join(sorted(str(k) for k in styles)[:3])
        return f"The article refers to supplementary material ({named})"
    if n:
        return (f"The article refers to supplementary material in "
                f"{n} place{'s' if n != 1 else ''}")
    return "The article refers to supplementary material"


def apply(report_obj: dict | None, audit: dict | None) -> dict:
    """Prepend the supplement request; append promoted refusals; report any
    uneditable asks.

    Mutates `report_obj["questions_for_authors"]` in place and returns a summary
    for the run record. Idempotent: a request already present (by `kind`) is not
    added twice, because `write_review_outputs` re-annotates results assembled
    by other paths and a question list that grows on every pass would be worse
    than the bug this fixes.

    ORDER IS THE ARGUMENT. The supplement request goes FIRST because the file
    may answer everything below it. Promoted refusals go LAST because they are
    derived rather than written -- the model looked at the paper and chose not
    to ask these, and a pipeline-generated request should not outrank a
    reviewer's own judgement about what matters.
    """
    summary = {"supplement_request_added": False, "uneditable_asks": [],
               "promoted_refusals": 0}
    if not isinstance(report_obj, dict):
        return summary

    questions = report_obj.get("questions_for_authors")
    if not isinstance(questions, list):
        questions = []

    summary["uneditable_asks"] = find_uneditable_asks(questions)

    already = any(isinstance(q, dict) and q.get("kind") == "supplement_request"
                  for q in questions)
    if not already:
        req = supplement_request(audit)
        if req is not None:
            questions.insert(0, req)
            summary["supplement_request_added"] = True

    # Keyed on the refusal text, not merely on `kind`: a report re-annotated on
    # a second pass must not gain a duplicate of each promoted row, and there
    # can legitimately be several of them.
    seen = {q.get("refusal_reason") for q in questions
            if isinstance(q, dict) and q.get("kind") == "unreported_value_request"}
    for cand in promotable_refusals(report_obj.get("not_checked")):
        if cand["refusal_reason"] in seen:
            continue
        seen.add(cand["refusal_reason"])
        questions.append(cand)
        summary["promoted_refusals"] += 1

    report_obj["questions_for_authors"] = questions
    return summary
