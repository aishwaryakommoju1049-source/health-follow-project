"""Tiered model factory — the single place a chat model is constructed.

Two jobs:

1.  **Cost control.** Nodes ask for a *tier*, not a provider. Which provider
    serves each tier is an .env value, so development can run entirely on a
    free local model while evaluation runs against a paid one.
    See docs/LLM_PROVIDER_STRATEGY.md.

2.  **Testability.** Because no node ever constructs a client directly, a
    single fixture can stub every model in the system:

        monkeypatch.setattr("app.core.llm.get_model", lambda tier: stub)

    See docs/TESTING_STRATEGY.md §3.

**No node may import a provider SDK directly.** If you find yourself doing
that, add the provider here instead.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.core.config import settings


class Tier(str, Enum):
    """What a node needs from a model, not which model it gets."""

    #: Intent classification, slot extraction, normalisation. Format
    #: compliance matters; reasoning does not.
    MECHANICAL = "mechanical"

    #: Patient dialogue, clarifying questions, plain-language output.
    CONVERSATIONAL = "conversational"

    #: Risk detection, tier-2 red flag, verifier, SOAP summary. Reasoning
    #: quality you will defend in the viva.
    CRITICAL = "critical"


@runtime_checkable
class ChatModel(Protocol):
    """The minimal surface every node may rely on.

    Deliberately narrow and framework-neutral: when LangChain models are
    wired in (Phase 3), they are adapted to this here rather than leaking
    their interface into every node.
    """

    def invoke(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        system: str | None = None,
    ) -> Any:
        """Run a single completion.

        If ``schema`` is given, the return value is an instance of it.
        Otherwise a string.
        """
        ...


_TIER_SETTING = {
    Tier.MECHANICAL: "llm_mechanical",
    Tier.CONVERSATIONAL: "llm_conversational",
    Tier.CRITICAL: "llm_critical",
}


def spec_for(tier: Tier) -> str:
    """Return the configured ``provider:model`` string for a tier."""
    spec: str = getattr(settings, _TIER_SETTING[tier])
    return spec


def _build(provider: str, model: str, tier: Tier) -> ChatModel:
    """Construct a client for one provider. **This is the test seam.**

    Kept separate from ``get_model`` on purpose. Python resolves module-level
    globals at call time, so patching ``app.core.llm._build`` intercepts every
    node regardless of how it imported ``get_model`` — including the common
    ``from app.core.llm import get_model``, which binds the original function
    into the importing module and would defeat a patch on ``get_model``
    itself.

    Phase 3 wires the real adapters here.
    """
    raise NotImplementedError(
        f"No provider adapter for {provider!r} (tier={tier.value}, model={model!r}).\n"
        f"Wire it up in app/core/llm.py — see docs/LLM_PROVIDER_STRATEGY.md §5.\n"
        f"If you hit this in a test, the stub_llm fixture was not applied."
    )


def get_model(tier: Tier) -> ChatModel:
    """Resolve a chat model for the given tier.

    Every node calls this. No node constructs a client itself.
    """
    spec = spec_for(tier)
    provider, _, model = spec.partition(":")

    if not model:
        raise ValueError(
            f"Malformed model spec {spec!r} for tier {tier.value}. "
            f"Expected '<provider>:<model>', e.g. 'ollama:llama3.1:8b'."
        )

    return _build(provider, model, tier)
