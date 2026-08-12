"""Tier-1 red-flag screening — deterministic, no model, sub-millisecond.

This runs on every inbound patient message *before* any LLM call, and
short-circuits the entire turn when it fires. See docs/ARCHITECTURE.md §3.

Design constraints, in priority order:

1.  **Recall over precision.** A missed stroke is unrecoverable; a false alarm
    is an annoyed doctor. When a rule is ambiguous, it fires. Report both
    numbers and say which one you optimised — see docs/IMPLEMENTATION_PLAN.md
    §5.2.
2.  **Deterministic.** No model call, ever. Model quality cannot compromise
    the most safety-critical path in the system.
3.  **Fast.** Runs inline on the request path.

Negation handling is deliberately narrow: it catches direct denials
("no chest pain", "I don't have any chest pain") and nothing subtler.
Ambiguous phrasing escalates by design. Nuance is the tier-2 LLM check's job,
not this module's.

.. warning::
   The rule set below is a **starting point built from widely documented
   emergency warning signs**, not a validated clinical instrument. Have it
   reviewed by a clinician — your project guide, or a doctor they can refer
   you to — before it is used with anything other than synthetic data. Record
   that review in docs/decisions/.

Every change to this module ships with a vignette in
``tests/safety/test_redflag_rules.py``. No exceptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["RULES", "Rule", "ScreenResult", "normalise", "screen"]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreenResult:
    """Outcome of a tier-1 screen."""

    red_flag: bool
    category: str | None = None
    rule_id: str | None = None
    matched_text: str | None = None
    #: Every category that fired, in rule order. Usually one; a message can
    #: legitimately trip several (e.g. stroke + neuro).
    categories: tuple[str, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return self.red_flag


@dataclass(frozen=True)
class Rule:
    """One screening pattern.

    ``rule_id`` is stable and appears in the audit log — never renumber an
    existing rule, only append.

    ``negatable`` is ``False`` for rules that must fire regardless of
    surrounding denial language. See the mental-health block below for the
    reasoning; do not set it lightly.
    """

    rule_id: str
    category: str
    pattern: re.Pattern[str]
    description: str
    negatable: bool = True


def _r(
    rule_id: str,
    category: str,
    pattern: str,
    description: str,
    *,
    negatable: bool = True,
) -> Rule:
    return Rule(rule_id, category, re.compile(pattern), description, negatable)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_APOSTROPHES = str.maketrans({"'": "", "’": "", "ʼ": ""})
_NON_TEXT = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lower-case, strip apostrophes and punctuation, collapse whitespace.

    Patterns are written against this form, so ``don't`` becomes ``dont``.
    """
    text = text.lower().translate(_APOSTROPHES)
    text = _NON_TEXT.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# Negation
# ---------------------------------------------------------------------------

# NOTE: "cant", "cannot", "wont" and "couldnt" are deliberately NOT negation
# cues. In symptom reports they almost always introduce a symptom rather than
# deny one — "I can't breathe", "I can't swallow", "I can't stop the bleeding"
# — and several rules match on them directly. Treating them as denials would
# silently suppress the most urgent messages in the entire rule set.
_NEGATION = re.compile(
    r"\b("
    r"no|not|never|none|nothing|without"
    r"|denies|denied|deny"
    r"|dont|doesnt|didnt|havent|hasnt|hadnt|isnt|arent|wasnt|werent"
    r")\b"
)

#: Characters of preceding context examined for a denial.
_NEGATION_WINDOW = 32


def _is_negated(text: str, start: int, end: int) -> bool:
    """True if the match looks like a denial rather than a report.

    Checks two places: the short window of text immediately before the match,
    and the matched span itself — the latter matters for multi-part patterns
    such as ``wound ... pus``, where the denial sits between the two halves
    ("wound but no pus").
    """
    window = text[max(0, start - _NEGATION_WINDOW) : start]

    # Do not let a denial leak across a clause boundary: "no fever. chest pain"
    # is a report of chest pain, not a denial of it.
    for boundary in (" but ", " however ", " although "):
        idx = window.rfind(boundary)
        if idx != -1:
            window = window[idx + len(boundary) :]

    return bool(_NEGATION.search(window)) or bool(_NEGATION.search(text[start:end]))


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    # --- cardiac ----------------------------------------------------------
    _r("CARD-01", "cardiac", r"\bcrushing\b.{0,20}\bchest\b", "Crushing chest pain"),
    _r(
        "CARD-02",
        "cardiac",
        r"\bchest\b.{0,15}\b(pain|pressure|tightness|tight|discomfort|heaviness)\b",
        "Chest pain or pressure",
    ),
    _r(
        "CARD-03",
        "cardiac",
        r"\b(pain|pressure|tightness|discomfort|heaviness)\b.{0,15}\bchest\b",
        "Chest pain or pressure (reversed word order)",
    ),
    _r(
        "CARD-04",
        "cardiac",
        r"\b(pain|ache)\w*\b.{0,40}\b(radiat|spreading|shooting)\w*\b.{0,25}"
        r"\b(arm|jaw|shoulder|neck)\b",
        "Pain radiating to arm, jaw, shoulder or neck",
    ),
    _r("CARD-05", "cardiac", r"\belephant\b.{0,25}\bchest\b", "Weight-on-chest description"),
    # --- stroke -----------------------------------------------------------
    _r(
        "STRK-01",
        "stroke",
        r"\b(face|mouth|smile)\b.{0,25}\b(droop\w*|uneven|lopsided)\b",
        "Facial droop",
    ),
    _r(
        "STRK-02",
        "stroke",
        r"\bdroop\w*\b.{0,20}\b(face|mouth|eyelid)\b",
        "Facial droop (reversed)",
    ),
    _r(
        "STRK-03",
        "stroke",
        r"\b(slurred|slurring)\b.{0,15}\b(speech|words)\b",
        "Slurred speech",
    ),
    _r(
        "STRK-04",
        "stroke",
        r"\b(speech|words)\b.{0,15}\b(slurred|slurring)\b",
        "Slurred speech (reversed)",
    ),
    _r("STRK-05", "stroke", r"\bcant\b.{0,20}\b(speak|talk)\b", "Unable to speak"),
    _r(
        "STRK-06",
        "stroke",
        r"\b(sudden|suddenly)\b.{0,35}\b(weak\w*|numb\w*)\b",
        "Sudden weakness or numbness",
    ),
    _r(
        "STRK-07",
        "stroke",
        r"\b(weak\w*|numb\w*)\b.{0,25}\bone side\b",
        "Unilateral weakness or numbness",
    ),
    _r(
        "STRK-08",
        "stroke",
        r"\b(sudden|suddenly)\b.{0,30}\b(vision|sight)\b",
        "Sudden vision change",
    ),
    # --- respiratory ------------------------------------------------------
    _r("RESP-01", "respiratory", r"\bcan(t|not) breathe\b", "Unable to breathe"),
    _r(
        "RESP-02",
        "respiratory",
        r"\b(severe|serious|really bad|very bad|extreme|badly)\b.{0,25}\bbreath\w*\b",
        "Severe breathing difficulty",
    ),
    _r("RESP-03", "respiratory", r"\bstruggling to breathe\b", "Struggling to breathe"),
    _r("RESP-04", "respiratory", r"\bgasping\b", "Gasping for air"),
    _r(
        "RESP-05",
        "respiratory",
        r"\b(lips|fingers|face|fingernails)\b.{0,20}\b(blue|bluish|grey|gray)\b",
        "Cyanosis",
    ),
    _r("RESP-06", "respiratory", r"\bcan(t|not) catch (my )?breath\b", "Cannot catch breath"),
    # --- haemorrhage ------------------------------------------------------
    _r(
        "BLEED-01",
        "haemorrhage",
        r"\b(cant|cannot|wont|unable to)\b.{0,25}\bstop\b.{0,20}\bbleed\w*\b",
        "Uncontrolled bleeding",
    ),
    _r(
        "BLEED-02",
        "haemorrhage",
        r"\bbleeding\b.{0,20}\b(heavily|badly|a lot|uncontrollab\w*|profusely)\b",
        "Heavy bleeding",
    ),
    _r("BLEED-03", "haemorrhage", r"\bsoaked (through|thru)\b", "Dressing soaked through"),
    _r(
        "BLEED-04",
        "haemorrhage",
        r"\b(vomiting|throwing up|coughing up|spitting up)\b.{0,15}\bblood\b",
        "Haematemesis or haemoptysis",
    ),
    _r("BLEED-05", "haemorrhage", r"\bblood\b.{0,20}\b(pouring|gushing)\b", "Profuse bleeding"),
    # --- neurological -----------------------------------------------------
    _r("NEUR-01", "neuro", r"\bworst headache\b", "Worst-ever headache"),
    _r("NEUR-02", "neuro", r"\bthunderclap\b", "Thunderclap headache"),
    _r(
        "NEUR-03",
        "neuro",
        r"\b(sudden|suddenly)\b.{0,25}\b(severe|intense|worst|blinding)\b.{0,20}\bheadache\b",
        "Sudden severe headache",
    ),
    _r("NEUR-04", "neuro", r"\bseizure\w*\b", "Seizure"),
    _r(
        "NEUR-05",
        "neuro",
        r"\b(passed out|blacked out|fainted|lost consciousness|unconscious|unresponsive)\b",
        "Loss of consciousness",
    ),
    # --- anaphylaxis ------------------------------------------------------
    _r(
        "ANA-01",
        "anaphylaxis",
        r"\bthroat\b.{0,25}\b(closing|closed|swell\w*|tight\w*)\b",
        "Throat closing or swelling",
    ),
    _r(
        "ANA-02",
        "anaphylaxis",
        r"\b(tongue|lips|face)\b.{0,20}\bswell\w*\b",
        "Facial, lip or tongue swelling",
    ),
    _r("ANA-03", "anaphylaxis", r"\bcan(t|not) swallow\b", "Unable to swallow"),
    _r(
        "ANA-04", "anaphylaxis", r"\bhives\b.{0,40}\bbreath\w*\b", "Hives with breathing difficulty"
    ),
    # --- sepsis / wound infection ----------------------------------------
    _r(
        "SEP-01",
        "sepsis",
        r"\b(fever|temperature)\b.{0,40}\b(confus\w*|disorient\w*|delirious)\b",
        "Fever with confusion",
    ),
    _r(
        "SEP-02",
        "sepsis",
        r"\b(confus\w*|disorient\w*|delirious)\b.{0,40}\b(fever|temperature)\b",
        "Fever with confusion (reversed)",
    ),
    _r(
        "SEP-03",
        "sepsis",
        r"\b(shaking|violent|uncontrollable)\b.{0,15}\b(chills|shivering|rigors)\b",
        "Rigors",
    ),
    _r(
        "SEP-04",
        "sepsis",
        r"\b(wound|incision|surgical site|stitches)\b.{0,30}"
        r"\b(pus|foul|red streaks|spreading redness)\b",
        "Wound infection signs",
    ),
    # --- mental health crisis --------------------------------------------
    #
    # Every rule in this block is NON-NEGATABLE, by deliberate clinical
    # choice. Negation around suicidality is genuinely ambiguous: "I don't
    # want to live" is a disclosure, while "I don't want to hurt myself" is a
    # denial, and no regex distinguishes them reliably. MHC-05 also matches on
    # "dont" itself, so negation checking would suppress it outright.
    #
    # The cost of a false positive here is a welfare check. The cost of a
    # false negative is not recoverable. We accept the false positives.
    _r(
        "MHC-01",
        "mental_health_crisis",
        r"\b(want|wanting|going|plan|planning|thinking about)\b.{0,25}"
        r"\b(kill|harm|hurt)\w*\b.{0,15}\bmyself\b",
        "Expressed intent of self-harm",
        negatable=False,
    ),
    _r("MHC-02", "mental_health_crisis", r"\bsuicidal\b", "Suicidal ideation", negatable=False),
    _r(
        "MHC-03",
        "mental_health_crisis",
        r"\bend my( own)? life\b",
        "Suicidal ideation",
        negatable=False,
    ),
    _r(
        "MHC-04",
        "mental_health_crisis",
        r"\btake my own life\b",
        "Suicidal ideation",
        negatable=False,
    ),
    _r(
        "MHC-05",
        "mental_health_crisis",
        r"\bdont want to (live|be here|wake up)\b",
        "Passive suicidal ideation",
        negatable=False,
    ),
    _r(
        "MHC-06",
        "mental_health_crisis",
        r"\bbetter off dead\b",
        "Passive suicidal ideation",
        negatable=False,
    ),
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def screen(text: str) -> ScreenResult:
    """Screen an inbound patient message for emergency red flags.

    Returns immediately-usable structure; the caller is responsible for
    raising the escalation and for showing the patient the emergency number.
    See docs/ARCHITECTURE.md §4.
    """
    if not text or not text.strip():
        return ScreenResult(red_flag=False)

    normalised = normalise(text)

    first: Rule | None = None
    first_match: re.Match[str] | None = None
    categories: list[str] = []

    for rule in RULES:
        match = rule.pattern.search(normalised)
        if match is None:
            continue
        if rule.negatable and _is_negated(normalised, match.start(), match.end()):
            continue
        if first is None:
            first, first_match = rule, match
        if rule.category not in categories:
            categories.append(rule.category)

    if first is None or first_match is None:
        return ScreenResult(red_flag=False)

    return ScreenResult(
        red_flag=True,
        category=first.category,
        rule_id=first.rule_id,
        matched_text=first_match.group(0),
        categories=tuple(categories),
    )
