"""Tier-1 red-flag screening tests.

The vignettes in ``vignettes.py`` are the specification; this module is the
harness that runs them. Deterministic, no database, no model, milliseconds.

Every change to ``app/services/redflag_rules.py`` ships with a vignette.
"""

from __future__ import annotations

import pytest

from app.services.redflag_rules import RULES, normalise, screen

from .vignettes import KNOWN_LIMITATIONS, MUST_ESCALATE, MUST_NOT_ESCALATE

pytestmark = pytest.mark.safety


# ---------------------------------------------------------------------------
# The specification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utterance", "expected_category"),
    MUST_ESCALATE,
    ids=[u[:48] for u, _ in MUST_ESCALATE],
)
def test_must_escalate(utterance: str, expected_category: str) -> None:
    result = screen(utterance)

    assert result.red_flag is True, (
        f"MISSED RED FLAG — this is a patient-safety regression.\n"
        f"  utterance: {utterance!r}\n"
        f"  normalised: {normalise(utterance)!r}"
    )
    assert expected_category in result.categories, (
        f"Escalated, but under the wrong category.\n"
        f"  expected: {expected_category}\n"
        f"  got:      {result.categories} (via {result.rule_id})"
    )


@pytest.mark.parametrize(
    "utterance",
    MUST_NOT_ESCALATE,
    ids=[u[:48] for u in MUST_NOT_ESCALATE],
)
def test_must_not_escalate(utterance: str) -> None:
    result = screen(utterance)

    assert result.red_flag is False, (
        f"False positive — routine message escalated.\n"
        f"  utterance:  {utterance!r}\n"
        f"  normalised: {normalise(utterance)!r}\n"
        f"  rule:       {result.rule_id} ({result.category})\n"
        f"  matched:    {result.matched_text!r}\n"
        f"Do NOT fix this by weakening a MUST_ESCALATE rule."
    )


@pytest.mark.parametrize(
    ("utterance", "should_escalate", "reason"),
    KNOWN_LIMITATIONS,
    ids=[u[:48] for u, _, _ in KNOWN_LIMITATIONS],
)
@pytest.mark.xfail(reason="Known tier-1 limitation; tier-2 is expected to catch it.", strict=True)
def test_known_limitations(utterance: str, should_escalate: bool, reason: str) -> None:
    """Documented gaps in the rule-based screen.

    ``strict=True`` means these turn into failures if they start passing —
    at which point move the vignette into the main corpus and delete it here.
    """
    assert screen(utterance).red_flag is should_escalate


# ---------------------------------------------------------------------------
# Properties of the screen itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_blank_input_does_not_escalate(blank: str) -> None:
    assert screen(blank).red_flag is False


def test_screening_is_case_and_punctuation_insensitive() -> None:
    variants = [
        "Crushing chest pain radiating down my left arm.",
        "CRUSHING CHEST PAIN RADIATING DOWN MY LEFT ARM",
        "crushing  chest   pain, radiating down my left arm!!!",
    ]
    results = [screen(v) for v in variants]

    assert all(r.red_flag for r in results)
    assert len({r.rule_id for r in results}) == 1, "Same content, different rule fired"


def test_apostrophe_forms_are_equivalent() -> None:
    assert screen("I can't breathe").red_flag is screen("I cant breathe").red_flag
    assert screen("I can’t breathe").red_flag is True  # curly apostrophe


def test_result_carries_provenance() -> None:
    """An escalation must be explainable — the audit log records the rule."""
    result = screen("This is the worst headache of my life.")

    assert result.rule_id is not None
    assert result.category is not None
    assert result.matched_text


def test_multiple_categories_are_all_reported() -> None:
    result = screen(
        "My face is drooping and I suddenly cannot feel my left arm, "
        "and there is crushing pressure in my chest."
    )
    assert result.red_flag is True
    assert {"stroke", "cardiac"} <= set(result.categories)


# ---------------------------------------------------------------------------
# Invariants on the rule table
# ---------------------------------------------------------------------------


def test_rule_ids_are_unique() -> None:
    ids = [r.rule_id for r in RULES]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Duplicate rule ids: {duplicates}. IDs appear in the audit log."


def test_every_rule_has_a_description() -> None:
    missing = [r.rule_id for r in RULES if not r.description.strip()]
    assert not missing, f"Rules without a description: {missing}"


def test_every_category_has_at_least_one_vignette() -> None:
    """A rule category with no vignette is untested safety code."""
    covered = {category for _, category in MUST_ESCALATE}
    declared = {rule.category for rule in RULES}
    assert declared <= covered, f"Categories with no MUST_ESCALATE vignette: {declared - covered}"


def test_mental_health_rules_are_never_negated() -> None:
    """Deliberate clinical choice — see the block comment in redflag_rules.py.

    If this test fails, someone has made suicidality suppressible by
    surrounding denial language. That is not a refactor; revert it.
    """
    mhc = [r for r in RULES if r.category == "mental_health_crisis"]
    assert mhc, "Mental-health rules disappeared from the table"
    assert all(r.negatable is False for r in mhc)


def test_screen_is_fast_enough_for_the_request_path() -> None:
    """Tier 1 runs inline on every inbound message; it must stay sub-millisecond."""
    import time

    sample = "Crushing chest pain radiating down my left arm, and I feel dizzy."
    start = time.perf_counter()
    for _ in range(1000):
        screen(sample)
    per_call_ms = time.perf_counter() - start  # 1000 calls => seconds == ms/call

    assert per_call_ms < 1.0, f"{per_call_ms:.3f} ms per call — too slow for the request path"
