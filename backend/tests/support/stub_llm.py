"""A scripted stand-in for a chat model.

No test in CI may call a real model API — it costs money, it is slow, and it
is non-deterministic. A test that fails 5% of the time trains the team to
ignore red builds, which is worse than having no tests.
See docs/TESTING_STRATEGY.md §1.

Because every node resolves its model through ``app.core.llm.get_model``, one
fixture replaces every model in the system. Typical use::

    def test_verifier_gives_up_after_two_attempts(stub_llm):
        stub_llm.always("REJECT")
        result = run_turn(make_turn_state())
        assert result["verifier_attempts"] == 2
        assert stub_llm.call_count == 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.core.llm import Tier


@dataclass(frozen=True)
class Call:
    """One recorded invocation."""

    tier: Tier
    prompt: str
    system: str | None
    schema: type[BaseModel] | None


class StubExhaustedError(RuntimeError):
    """Raised when the stub is asked for more responses than were scripted.

    This is deliberately loud: silently returning a default would let a test
    pass while the code under test made unexpected extra model calls.
    """


@dataclass
class StubChatModel:
    """Records every call; returns whatever you scripted."""

    calls: list[Call] = field(default_factory=list)
    _queue: list[Any] = field(default_factory=list)
    _always: Any = None
    _always_set: bool = False

    # -- scripting ---------------------------------------------------------

    def respond_with(self, *responses: Any) -> StubChatModel:
        """Queue responses, returned in order, one per call."""
        self._queue.extend(responses)
        return self

    def always(self, response: Any) -> StubChatModel:
        """Return the same response for every call, without limit."""
        self._always = response
        self._always_set = True
        return self

    def reset(self) -> None:
        self.calls.clear()
        self._queue.clear()
        self._always = None
        self._always_set = False

    # -- the ChatModel protocol -------------------------------------------

    def invoke(
        self,
        prompt: str,
        *,
        schema: type[BaseModel] | None = None,
        system: str | None = None,
    ) -> Any:
        self.calls.append(Call(tier=self._tier, prompt=prompt, system=system, schema=schema))

        if self._queue:
            response = self._queue.pop(0)
        elif self._always_set:
            response = self._always
        else:
            raise StubExhaustedError(
                f"StubChatModel received an unscripted call (#{len(self.calls)}).\n"
                f"  tier:   {self._tier.value}\n"
                f"  prompt: {prompt[:120]!r}\n"
                f"Script it with .respond_with(...) or .always(...), or assert on "
                f"call_count if the extra call is the bug."
            )

        if schema is not None and isinstance(response, dict):
            return schema.model_validate(response)
        return response

    # -- assertions --------------------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def calls_for(self, tier: Tier) -> list[Call]:
        return [c for c in self.calls if c.tier == tier]

    def assert_never_called(self) -> None:
        assert not self.calls, (
            f"Expected no model calls, got {len(self.calls)}: {[c.tier.value for c in self.calls]}"
        )

    # -- internal ----------------------------------------------------------

    #: Set by the ``stub_llm`` fixture each time ``get_model`` is called, so
    #: recorded calls carry the tier the caller asked for.
    _tier: Tier = Tier.CRITICAL

    def _bind(self, tier: Tier) -> StubChatModel:
        self._tier = tier
        return self
