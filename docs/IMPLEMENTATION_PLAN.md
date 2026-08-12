# MediAgent — Implementation Plan

Team 11 · 4/4 CSD-C · Guide: Mr. Y. Bheem Shankar
Planning horizon: **Aug 2026 → Apr 2027** (two semesters, four people)

Architecture and diagrams: [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## 0. The one decision to make before any code

Your abstract describes longitudinal post-consultation follow-up. Your v1 diagram described
single-pass intake triage with doctor matching. These are different products.

`ARCHITECTURE.md` reconciles them by treating your diagram as **one turn** inside a **follow-up
loop**, which preserves both your abstract and your diagram work. **Get your guide to sign off on
that framing in week one.** If they prefer the intake/triage product instead, that is a legitimate
choice — but the abstract needs rewriting, and every phase below shifts.

Do not start Phase 1 until this is settled.

---

## 1. Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + Vite + TypeScript, Tailwind | Two dashboards: patient, doctor |
| Backend | FastAPI (Python 3.11+), SQLAlchemy, Alembic | Matches your abstract |
| Database | **PostgreSQL 16 + pgvector**, via Docker Compose | From day one — see below |
| Orchestration | **LangGraph** | Not CrewAI — see below |
| LLM | Anthropic API — `claude-opus-5` default | Routing table in §2 |
| Scheduler | APScheduler (simple) or Celery + Redis (if you need retries/queues) | Start with APScheduler |
| Drug data | RxNorm + openFDA | Deterministic lookup, cached locally |
| Synthetic data | Synthea | See §5 |

### 1.1 LangGraph over CrewAI

Your abstract offers both. Pick LangGraph:

- **Conditional edges** model your red-flag branch and output gate directly.
- **Bounded cycles** model the verifier retry loop — CrewAI has no clean equivalent.
- **Interrupts** give you human-in-the-loop doctor approval as a first-class construct.
- **Checkpointing** to Postgres gives you resumable, multi-day sessions almost free, which is
  exactly what the follow-up loop needs.

CrewAI's role-playing abstraction makes control flow emergent rather than explicit. For a clinical
system where you must be able to say *why* a given output was produced, explicit and auditable wins.
That sentence belongs in your report.

### 1.2 Postgres from day one, with pgvector

Skip the "SQLite now, Postgres later" path. You will lose a week to the migration in February,
which is exactly when you cannot afford it. Run Postgres in Docker Compose from week one.

Use the `pgvector` extension for the Evidence Agent's embeddings. This removes an entire second
service — Chroma, Pinecone, Weaviate — from your architecture, your deployment story, and your
report. One database, one backup, one connection string.

### 1.3 Structured outputs everywhere

Define every agent's output as a Pydantic model and use the SDK's parsing helper. You get a
validated object instead of a JSON string you have to defend against:

```python
from pydantic import BaseModel
from typing import Literal

class SymptomReport(BaseModel):
    symptoms: list[str]
    onset_hours_ago: int | None
    pain_scale: int | None          # 0-10
    urgency: Literal["routine", "watch", "urgent", "emergency"]
    confidence: float
    uncertain_fields: list[str]

response = client.messages.parse(
    model="claude-opus-5",
    max_tokens=4096,
    messages=[...],
    output_format=SymptomReport,
)
report = response.parsed_output      # a validated SymptomReport
```

For the drug-interaction tool, set `strict: True` on the tool definition so parameters are
schema-guaranteed at the API layer.

### 1.4 Prompt caching

Every agent in the fan-out shares the same patient-context prefix. Cache it:

```python
system=[{
    "type": "text",
    "text": AGENT_SYSTEM_PROMPT + patient_baseline_block,
    "cache_control": {"type": "ephemeral"},
}]
```

Cache reads cost roughly a tenth of normal input. Two rules that will otherwise cost you a day:

- **Caching is a prefix match.** Any byte change anywhere in the prefix invalidates everything
  after it. Keep timestamps, session IDs, and UUIDs *after* the breakpoint.
- **Verify it works.** Check `response.usage.cache_read_input_tokens`. If it is zero across
  repeated calls, something volatile is leaking into the prefix.

### 1.5 API details that will otherwise cost you an afternoon

- `temperature`, `top_p`, and `top_k` are **rejected** on current models — a 400, not a warning.
  Steer with prompting instead.
- Thinking is **on by default** on `claude-opus-5`. Control depth with
  `output_config={"effort": "high"}` — levels are `low` / `medium` / `high` / `xhigh` / `max`.
- Assistant-turn prefills return a 400. Use structured outputs instead.
- Set `max_tokens` generously (~16000 non-streaming) — hitting the cap truncates mid-thought.

---

## 2. Model routing

> **Full treatment, including free and local options:**
> [`LLM_PROVIDER_STRATEGY.md`](LLM_PROVIDER_STRATEGY.md)

Nodes are grouped into four tiers by what they actually need. Only tier 3 requires a frontier
model, and it is roughly a quarter of your calls.

| Tier | Nodes | Source |
|---|---|---|
| 0 — no model | Tier-1 red flags, drug interaction, adherence arithmetic | Deterministic code + free public APIs |
| 1 — mechanical | Intent classification, slot extraction, normalisation | Local model via Ollama — free |
| 2 — conversational | Check-in dialogue, clarifying questions, patient output | Free-tier hosted API, or local |
| 3 — safety-critical | Risk detection, tier-2 red flag, verifier, SOAP summary | Paid API, at minimum for evaluation runs |

Paid reference rates, for the tier-3 budget:

| Model | Input / MTok | Output / MTok |
|---|---|---|
| `claude-opus-5` | $5.00 | $25.00 |
| `claude-sonnet-5` | $3.00 | $15.00 |
| `claude-haiku-4-5` | $1.00 | $5.00 |

Rates as of mid-2026; Sonnet 5 carries a reduced introductory rate through 31 Aug 2026.

**Resolve every model through a tiered factory** (`app/core/llm.py`), so provider choice is an
`.env` value and never a code change. Do this from the first node, not as a later refactor — it is
what makes the multi-model comparison in §5.3 possible.

Use the token-counting endpoint on a real transcript before quoting anyone a cost figure. Do not
estimate.

---

## 3. Phases

Sequenced so you have a demonstrable system at every review, not only at the end. Note that
**the product works with zero AI by the end of Phase 2** — that is deliberate.

### Phase 1 — Scope lock and skeleton
**Mid Aug → end Aug 2026 · 2 weeks**

- Guide sign-off on the follow-up framing (§0)
- Repo, Docker Compose (Postgres + pgvector), FastAPI skeleton, React + Vite skeleton
- CI running tests on push
- Schema + Alembic migrations for every table in `ARCHITECTURE.md` §7
- JWT auth, three roles; `doctor_patient_link` gates every clinical read
- `audit_log` written by a database trigger, not application code

**Ship:** login works, both dashboards render empty, every write appears in the audit log.

---

### Phase 2 — The non-AI spine
**Sep → mid Oct 2026 · 4 weeks**

- **First three days: test harness and CI** — see [`TESTING_STRATEGY.md`](TESTING_STRATEGY.md) §4.
  Timeboxed. Includes the `gitleaks` pre-commit hook and the red-flag vignette suite.
- Doctor: register a patient, create a care plan, prescribe, set follow-up cadence
- Patient: view prescriptions, log symptoms via form, mark doses taken
- Scheduler firing dose reminders and overdue check-in alerts
- Notification layer behind an interface — in-app and email first; SMS/WhatsApp only if time allows

**Ship:** the entire product works with no AI at all.

> This is your demo-day insurance policy. If an API key fails or the network drops during your
> final presentation, you still have a working system to show. Do not skip it and do not compress it.

---

### Phase 3 — First agent and the safety floor
**Mid Oct → mid Nov 2026 · 4 weeks**

- LangGraph skeleton: typed `TurnState`, Postgres checkpointer, one node
- Patient Interaction Agent — conversational check-in, slot-filling into structured records
- **Tier-1 deterministic red-flag screen**, plus the LLM classifier as a second pass
- Escalation ladder with acknowledgement and timeout (`ARCHITECTURE.md` §4)
- PHI redaction at the LLM boundary and in application logs

**Ship (mid-project review):** a patient can chat, symptoms land in the database as structured rows,
red flags escalate and are acknowledged.

---

### Phase 4 — Multi-agent fan-out
**Dec 2026 → Jan 2027 · 4 weeks**

- Parallel nodes: symptom analysis, medication adherence, trend-vs-baseline
- Drug interaction as a **deterministic RxNorm/openFDA lookup**, cached locally
- Evidence Agent over pgvector, against a corpus you can name and defend
- Verifier node with the bounded retry loop and the human-escalation fallback
- Risk Detection comparing against the patient's own baseline, not a population average

**Ship:** the full architecture running end to end.

---

### Phase 5 — Closing the doctor loop
**Feb 2027 · 3 weeks**

- Summary Agent producing a SOAP note with citations back to source check-ins
- Doctor dashboard: risk-ranked queue, adherence view, AI summaries with approve / edit / override
- Output gating so the doctor is not notified on routine turns
- Every doctor override written to the audit log

**Ship:** the loop closes. Patient → agents → doctor → back to the patient.

> Those overrides are not just a feature. The diff between the AI-generated SOAP note and the
> doctor-approved version is a measurable quality signal, and it is the most credible evaluation
> data you will have. Start capturing it the day the dashboard works.

---

### Phase 6 — Evaluation and write-up
**Mar → Apr 2027 · 4 weeks**

- Build and run the eval set (§5), tabulate results
- Ablations: with and without the verifier, with and without RAG grounding
- Latency (p50, p95) and cost per session — measured, not estimated
- Report, demo video, viva preparation

**Ship:** final submission.

---

## 4. Work split (four people)

Rotate so nobody owns exactly one thing — but a primary owner per area prevents drift:

| Area | Scope |
|---|---|
| Backend + data | FastAPI, schema, migrations, auth, audit log, scheduler |
| Agents + orchestration | LangGraph, agent prompts, structured outputs, verifier |
| Frontend | Both dashboards, chat interface, escalation UI |
| Safety + evaluation | Red-flag rules, drug DB integration, eval set, metrics, ablations |

The safety/evaluation role is the one most often left until March and is the one that earns the most
marks. Staff it from Phase 3.

---

## 5. Evaluation

Most final-year AI projects show a screen recording and stop. Numbers are what get remembered.
**Start collecting them in Phase 3, not Phase 6.**

### 5.1 Data, without an ethics committee

- **Synthea** — open-source synthetic patient generator. Realistic histories, medication lists,
  conditions. No IRB, no credentialing. Will populate your database with hundreds of plausible
  patients in an afternoon. **Use this.**
- **Hand-written vignettes** — 100–150 clinical scenarios with known correct urgency labels, for
  triage accuracy. Have your guide sanity-check a sample.
- **MIMIC-IV** — richer, but PhysioNet credentialing takes weeks. Only start that process if you
  are confident you will need it.

### 5.2 Metrics

| Metric | Target | Why it matters |
|---|---|---|
| **Red-flag recall** | Near 100% | The headline number |
| Red-flag precision | Report honestly | Will be lower — that is correct |
| Triage-band agreement | vs. labelled vignettes | Your accuracy claim |
| RAG groundedness | % of clinical claims traceable to a source | Hallucination rate, inverted |
| Verifier catch rate | # ungrounded claims blocked | Quantifies your safety layer |
| Adherence prediction | vs. logged ground truth | Medication Agent value |
| SOAP edit distance | AI draft vs. doctor-approved | Real quality signal |
| Latency p50 / p95 | Per turn | Include the tier-1 screen separately |
| Cost per session | Measured tokens | Not estimated |

**Red-flag recall is not a symmetric metric, and you should say so explicitly.** Tune the threshold
toward recall at the cost of precision — a missed stroke is unrecoverable, a false alarm is an
annoyed doctor. Stating that tradeoff and its justification in one sentence demonstrates you
understand the clinical stakes better than any accuracy figure will.

### 5.3 The ablation that writes your results chapter

Run the identical eval set three ways:

1. Full system
2. **Verifier disabled**
3. **RAG disabled**

If the verifier blocks a measurable number of ungrounded claims, you have quantified the value of
your own safety architecture. That is a far stronger result than "the system works," and it is the
kind of finding that turns a project report into something publishable.

**Then sweep the model tier as a second axis.** Because provider is a config value (§2), you can
run the same eval set on a local 8B model, a free-tier hosted model, and a paid frontier model:

| Model | Red-flag recall | Triage agreement | Groundedness | p95 latency | Cost / session |
|---|---|---|---|---|---|
| Local 8B | | | | | $0 |
| Free-tier hosted | | | | | $0 |
| Paid frontier | | | | | |

This answers a question nobody else in your cohort will have asked: *how much model quality does a
clinical follow-up system actually need, and where does it stop mattering?* If the local model
matches on triage but collapses on verifier catch rate, that is a real finding about where
reasoning quality is load-bearing in a safety pipeline.

Always name the model that produced a number. An unlabelled accuracy figure is the one reporting
mistake that would genuinely damage the project.

---

## 6. Scope boundaries

Decide these now and write them into the report. Stating them plainly *strengthens* the project —
it demonstrates you understand what an AI system should not be trusted with.

- **Not a diagnostic device.** The system triages and reports; it does not diagnose. Say so in the
  UI and in the abstract.
- **No autonomous prescribing or dose changes.** Ever, at any confidence score. This is the hardest
  boundary and the most important one.
- **Doctor-in-the-loop for anything clinical.** The AI drafts, a human approves. Log both.
- **Emergency instruction always visible** — 108 on every screen, not gated behind a triage decision.
- **Explicit consent at enrolment**, with a revocation path and a stated data-retention period.
- **India's DPDP Act 2023** is your governing framework — cite it. Mention HIPAA only as design
  inspiration, not as something you comply with.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Scope is large for four people in nine months | Phase ordering: cut from Phase 5–6 inward, never the spine |
| Drug DB integration underestimated | Start the RxNorm spike in Phase 3, not Phase 4 |
| RAG corpus never actually curated | Name and freeze the corpus in Phase 1; 30 documents beats 3000 unread ones |
| Evaluation deferred to March | Assign an owner in Phase 3; capture agent findings from the first turn |
| API cost surprises | Token-count a real transcript in Phase 3 and extrapolate |
| One person becomes the LangGraph bottleneck | Pair on the first two nodes so at least two people can debug the graph |

**If you fall behind, cut features — not evaluation.** A smaller system with real measured results
scores better than a larger one with a screen recording.
