# Testing Strategy

**Question:** should we write the test pipelines before implementing?

**Answer:** build the *infrastructure* now — timeboxed to about three days. Write comprehensive
*tests* now only for the red-flag rules, where the tests are the specification. Everything else gets
tests alongside the code, because you do not yet know the shape of what you are testing.

> **The failure mode to avoid.** A team with a nine-month window and a large scope spends three
> weeks building beautiful test infrastructure, writes tests against an imagined API, then discovers
> in October that the real API is different and throws half of them away. Timebox this. Three days,
> the list in §4, then start Phase 2.

---

## 1. Tests and evaluations are different things

This is the distinction that matters most in an LLM system, and conflating the two gives you either
flaky CI or no quality measurement at all.

| | Tests | Evaluations |
|---|---|---|
| **Question** | Does the code do what it says? | Is the system clinically good enough? |
| **Determinism** | Must be deterministic | Inherently non-deterministic |
| **Speed** | Seconds | Minutes to hours |
| **Run when** | Every push | Weekly, and before each review |
| **Gates a merge?** | Yes | No |
| **Model involved?** | **Stubbed, never real** | Real, that is the point |
| **Lives in** | `backend/tests/` | [`../eval/`](../eval/) |

**No test in CI may call a real model API.** It costs money, it is slow, and it is non-deterministic
— a test that fails 5% of the time trains the team to ignore red builds, which is worse than having
no tests. Model quality belongs in `eval/`, on its own cadence.

---

## 2. What to test at each layer

Your architecture separates deterministic services from agent nodes
([`ARCHITECTURE.md`](ARCHITECTURE.md) §5). That split is also the testing strategy.

### Layer 1 — Deterministic logic · test hard, aim high

`services/redflag_rules.py`, `services/drug_lookup.py`, adherence arithmetic, scheduling windows,
the `doctor_patient_link` authorisation guard.

These are ordinary functions with ordinary tests, and this is where correctness is genuinely
verifiable. **Push for high coverage here and nowhere else.** A missed branch in the red-flag rules
is a patient-safety issue, not a code-quality issue.

### Layer 2 — Graph structure · test the path, not the prose

You cannot assert on what a model says. You *can* assert on what your graph does with it, by
stubbing the model and checking which nodes ran.

```python
def test_red_flag_short_circuits_before_any_model_call(stub_llm):
    state = make_turn_state(raw_input="crushing chest pain radiating to my left arm")
    result = run_turn(state)

    assert result["red_flag"] is True
    assert result["escalation_raised"] is True
    assert stub_llm.call_count == 0      # tier 1 is deterministic — no model, ever


def test_verifier_retries_at_most_twice_then_falls_back(stub_llm):
    stub_llm.verifier_always_fails()
    result = run_turn(make_turn_state())

    assert result["verifier_attempts"] == 2
    assert result["used_safe_fallback"] is True
    assert result["flagged_for_human_review"] is True
```

These are the highest-value tests in the whole project, because they verify the **safety
properties** of the architecture rather than the behaviour of any individual component. They are
also fast and completely deterministic.

Things worth asserting here:

- Tier-1 red flag escalates and short-circuits, with zero model calls
- The clarification loop is capped at 2 rounds and then escalates
- The verifier retries at most twice, then falls back safely
- Doctor output is *not* emitted on a routine turn
- A missing `doctor_patient_link` is rejected before any data is read
- Every terminal path writes to the timeline and to `audit_log`

### Layer 3 — Agent outputs · validate the schema, not the content

An agent test asserts that the output *parses into its Pydantic model* and that required fields are
populated. It does not assert that the model said something specific.

```python
def test_symptom_agent_emits_valid_report(stub_llm):
    stub_llm.respond_with(SYMPTOM_FIXTURE)
    report = symptom_node(make_turn_state())["findings"][-1]

    parsed = SymptomReport.model_validate(report)   # raises if the contract broke
    assert parsed.urgency in {"routine", "watch", "urgent", "emergency"}
```

### Layer 4 — API and integration · a thin layer of real ones

A handful of end-to-end tests against a real test database with a stubbed model. Enough to catch
migration drift and broken wiring — not a second full suite.

---

## 3. `app/core/llm.py` is your test seam

The tiered model factory from [`LLM_PROVIDER_STRATEGY.md`](LLM_PROVIDER_STRATEGY.md) §5 was designed
for cost control. It is also the single injection point that makes everything in §2 possible:

```python
# conftest.py
@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    """Replace every model with a scripted stub. No network, no cost, no flake."""
    stub = StubChatModel()
    monkeypatch.setattr(
        "app.core.llm._build",                       # NOT get_model — see below
        lambda provider, model, tier: stub._bind(tier),
    )
    return stub
```

Because no node ever constructs a client directly, one fixture stubs the entire system. **This is
the strongest argument for writing that factory before the first node**, rather than as a later
refactor — it is not just about swapping providers, it is what makes the codebase testable at all.

> **Patch `_build`, never `get_model`.** Nodes will naturally write
> `from app.core.llm import get_model`, which binds the *original* function object into the
> importing module at import time — a patch on `app.core.llm.get_model` never reaches them, and the
> stub silently fails to apply. `get_model` therefore delegates to a module-level `_build`, which
> Python resolves at call time, so patching it intercepts every caller regardless of import style.
> `tests/test_smoke.py` imports `get_model` by name on purpose, to keep that guarantee under test.

The fixture is `autouse`. A test that reaches a real provider by accident should fail loudly, not
quietly spend money.

---

## 4. What to build now — the three-day list

### Day 1 · Harness

- `pytest`, `pytest-asyncio`, `pytest-cov`
- A **separate test database** in `docker-compose.yml`, migrated by Alembic on session start
- Transactional fixture: each test runs in a transaction that is rolled back afterwards, so tests
  cannot see each other's data
- `StubChatModel` and the `stub_llm` fixture above
- Fixture factories for the core entities — patient, doctor, care plan, prescription
- **One trivial passing test**, to prove the whole pipeline runs end to end

### Day 2 · CI and guardrails

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: mediagent_test
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r backend/requirements.txt -r backend/requirements-dev.txt
      - run: ruff check backend/
      - run: mypy backend/app
      - run: pytest backend/tests -v --cov=app --cov-report=term-missing
        env:
          DATABASE_URL: postgresql+psycopg://postgres:test@localhost:5432/mediagent_test
          ANTHROPIC_API_KEY: "test-key-never-used"   # asserts no test calls the real API
```

Then add **pre-commit hooks**, and put the secrets scanner first:

- `gitleaks` — **the highest-value automation on this project right now.** You have four people, a
  live API key, and a public-ish repo. A scanner that blocks the commit is worth more than any test
  in this document.
- `ruff` — lint and format
- `mypy` — on `app/` only
- A hook rejecting `.env` files outright

### Day 3 · The red-flag vignette suite

This is the one place where **test-first is unambiguously correct**, because the tests *are* the
specification. Write the vignettes before writing a single rule.

```python
# tests/safety/test_redflag_rules.py
MUST_ESCALATE = [
    ("crushing chest pain radiating to my left arm", "cardiac"),
    ("sudden weakness on one side and my speech is slurred", "stroke"),
    ("I can't stop the bleeding from the wound", "haemorrhage"),
    ("severe difficulty breathing since this morning", "respiratory"),
    ("worst headache of my life, came on suddenly", "neuro"),
    # ... target 40-60 across the categories in your care plans
]

MUST_NOT_ESCALATE = [
    "mild soreness at the incision site, about the same as yesterday",
    "I forgot my evening tablet",
    "slight headache after reading for a few hours",
    # ... near-misses matter more than obvious negatives
]

@pytest.mark.parametrize("utterance,category", MUST_ESCALATE)
def test_escalates(utterance, category):
    result = screen(utterance)
    assert result.red_flag is True
    assert result.category == category

@pytest.mark.parametrize("utterance", MUST_NOT_ESCALATE)
def test_does_not_escalate(utterance):
    assert screen(utterance).red_flag is False
```

Two notes:

**Spend your effort on the near-misses.** "Mild soreness, same as yesterday" versus "the pain is
much worse than yesterday" is where a rule table actually earns or loses its precision. Obvious
positives are easy and teach you little.

**These vignettes seed your evaluation set.** The same scenarios drive the tier-2 LLM red-flag
evaluation in [`../eval/`](../eval/) — one written for CI, one for measurement. Write them once,
use them twice.

---

## 5. What *not* to build now

| Don't | Why |
|---|---|
| Comprehensive tests for LangGraph nodes | You have not written one. You do not know what `TurnState` really needs. Those tests get rewritten. |
| Frontend component tests | Nothing exists to test. Add them from Phase 2, alongside components. |
| A mocking layer for RxNorm/openFDA | Record real responses as fixtures when you integrate, in Phase 3–4. Do not invent the shape now. |
| Coverage thresholds in CI | Enforce coverage on `services/` in Phase 3. A global gate on an empty repo just blocks merges. |
| Load or performance tests | Latency is an evaluation metric, measured in Phase 6, not a CI gate. |
| Contract tests between frontend and backend | Generate the client from the OpenAPI schema instead — the schema is the contract. |

---

## 6. Rules for the rest of the project

- **Every red-flag rule change ships with a vignette.** Non-negotiable. That module is the safety
  floor.
- **Every bug fix starts with a failing test** that reproduces it. This is where test-first is
  cheapest and most valuable — you already know the contract.
- **No test calls a real model API.** If a test needs one, it belongs in `eval/`.
- **No real patient data in fixtures**, ever. Synthea output or hand-written synthetic only.
- **Green CI merges.** A tolerated red build becomes a permanently red build within two weeks.
- **A skipped test is a bug with a comment.** Delete it or fix it; do not accumulate them.

---

## 7. Where this sits in the schedule

This is three days at the **start of Phase 2**
([`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §3) — before the non-AI spine, not before
Phase 1's schema work, since the fixtures need tables to exist.

The Phase 2 deliverable is unchanged: *the entire product works with no AI at all*. Test
infrastructure supports that milestone; it does not replace it.
