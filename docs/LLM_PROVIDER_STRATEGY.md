# LLM Provider Strategy

**Question:** the Anthropic API costs money. Can we use something free?

**Short answer:** yes, mostly — and the constraint improves the project rather than weakening it.
Run local models for development, free-tier hosted models for the middle layer, and reserve paid
API calls for the safety-critical nodes and the final evaluation runs. Then report the comparison
as a result.

> **Verify current terms before committing.** Free tiers, rate limits, and pricing change on a
> monthly basis. Everything below describes *categories* of option and how to choose between them.
> Check each provider's current terms yourself rather than trusting the specifics here.

---

## 1. First, know what you are actually spending

Do not optimise a number you have not measured. Before choosing anything, run **one** complete
session turn against a paid API and read the token counts off the response.

Rough shape of a single turn, before caching:

| Stage | Input tokens | Output tokens |
|---|---|---|
| System prompt + patient baseline | ~2,000 | — |
| Five parallel agents | ~7,500 | ~2,000 |
| Risk detection + verifier + summary | ~3,000 | ~1,000 |
| **Total** | **~12,500** | **~3,000** |

At Opus 5 rates that is roughly **13–14 cents per turn**, dropping to perhaps 8 cents once prompt
caching is working on the shared prefix. At Haiku 4.5 rates it is under 3 cents.

Across a whole project — call it 3,000 development turns plus 450 evaluation runs — the honest
range is:

| Approach | Rough total |
|---|---|
| Everything on Opus 5, no caching, careless | $400+ |
| Everything on Haiku 4.5 | ~$80 |
| **Tiered strategy in §3, with caching** | **$40 – 80** |
| Tiered strategy + local dev + academic credits | **~$0** |

Split four ways, the middle option is under $20 each. That may already be acceptable — but the
strategy below gets it close to zero anyway, so there is no reason not to.

**Measure your own numbers and put them in the report.** "Cost per session" is one of your
evaluation metrics ([`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §5.2) and a measured figure
is worth more than any estimate here.

---

## 2. Two things that cost nothing and are already in the design

Worth stating plainly, because it changes how much the model choice actually matters:

**Tier-1 red-flag screening is deterministic rules, not a model.** Your most safety-critical path —
the one that catches chest pain and stroke symptoms in under a second — does not call an LLM at
all. Model quality cannot compromise it. See [`ARCHITECTURE.md`](ARCHITECTURE.md) §3.

**Drug interaction checking is a database lookup, not a model.** RxNorm and openFDA are free public
APIs. This was already a safety decision; it is also a cost decision.

So the components where a weaker model does the most damage are the ones that were never going to
be model calls. That is not an accident — it is why the architecture separates deterministic
services from agent nodes.

---

## 3. The tiered strategy

Your nodes have genuinely different requirements. Treat them differently.

| Tier | Nodes | Requirement | Recommended source |
|---|---|---|---|
| **0 — no model** | Tier-1 red flags, drug interaction, adherence arithmetic, scheduling | Determinism | Code and public APIs. Free. |
| **1 — mechanical** | Intent classification, slot extraction, yes/no parsing, normalising a drug name | Format compliance, not reasoning | **Local model.** Free. |
| **2 — conversational** | Patient check-in dialogue, clarifying questions, plain-language patient output | Fluency, warmth, some judgement | **Free-tier hosted API**, or local if quality holds |
| **3 — safety-critical** | Risk detection, tier-2 red flag, verifier, SOAP summary | Reasoning quality you will defend in the viva | **Paid API**, at least for the evaluation runs |

Tier 3 is perhaps 20–25% of your calls. Paying for only that tier is where most of the saving comes
from.

You can go further: run tiers 1–3 entirely on free models during development and switch tier 3 to a
paid model **only for the final evaluation runs that produce your report numbers**. That is a few
hundred calls, not a few thousand — likely under $10 total.

---

## 4. Free options, by category

### 4.1 Local models — Ollama

The most reliable "free" because it does not depend on anyone's terms of service.

```bash
# install Ollama, then:
ollama pull llama3.1:8b
ollama serve
```

**Hardware:** an 8B model at 4-bit quantisation needs roughly 5–6 GB of RAM and runs acceptably on
a 16 GB laptop without a GPU. A GPU makes it several times faster but is not required. One team
member's machine can serve the whole team over the local network during development.

**Which model:** check what is current when you read this — the small-model landscape moves fast.
As a starting point, look at the Llama, Qwen, Mistral, Gemma, and Phi families in the 7–14B range.
Prefer whichever has the strongest instruction-following and JSON-mode support, not the highest
benchmark score.

**The real limitation is structured output.** Small local models are noticeably worse at emitting
valid JSON against a schema, and your entire agent design depends on that
([`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §1.3). Mitigate with Ollama's `format: json`
mode, or a constrained-decoding library such as Outlines. Budget real time for this — it is the
main friction of going local, and it is worth knowing before you commit.

**An advantage worth putting in the report:** with local inference, patient data never leaves the
machine. For a healthcare system that is a defensible privacy property, not a compromise. It also
means your PHI redaction layer has nothing to redact at the LLM boundary in local mode — a point
you can make in the design chapter.

### 4.2 Free tiers of hosted APIs

Several providers offer genuinely usable free tiers — typically rate-limited by requests per minute
and per day rather than hard-capped. Providers worth checking: Google AI Studio, Groq, Mistral,
Cohere, OpenRouter's free model endpoints, and Hugging Face Inference.

**What to check before you rely on one:**

| Question | Why it matters |
|---|---|
| Requests per minute? | Your fan-out fires five agents *concurrently* — a 10 RPM limit means one turn per minute |
| Requests per day? | Caps how much you can test in a session |
| Does it support JSON schema / structured output? | Non-negotiable for your agent design |
| Is data used for training? | **Critical.** Even with synthetic data, check — and state your answer in the report |
| Does it require a payment method on file? | Some "free" tiers do |

That fourth row deserves attention. Several free tiers fund themselves by training on submitted
data. Since you will be using Synthea-generated synthetic patients rather than real records this is
not a breach — but a healthcare project that cannot say where its data went has a hole in its
ethics section. Check, and write down the answer.

### 4.3 Academic and student credits — highest leverage, lowest effort

**Do this first. It costs one email and may solve the problem entirely.**

- **GitHub Student Developer Pack** — bundles credits across a range of providers; free with a
  student email
- **Azure for Students** — free credit on sign-up, no card required, and Azure serves Claude models
  through Microsoft Foundry, so this can fund your tier-3 calls directly
- **Google Cloud** and **AWS** student programmes — similar shape
- **Direct request to providers.** Most model providers have education or research credit
  programmes, and many will grant credits for a supervised university project on request. A short
  email from your guide's institutional address describing the project has a genuinely good hit
  rate. Ask for enough to cover evaluation, not the whole project — a modest, specific request is
  more likely to be granted than an open-ended one.

---

## 5. Make it a configuration choice, not a rewrite

This is the part that matters engineering-wise, and you should do it in Phase 3 regardless of which
provider you pick.

LangGraph is provider-agnostic. Every node should receive a chat model through a factory rather
than constructing one, so that swapping providers — or running different tiers on different
providers — is a config change:

```python
# app/core/llm.py
from enum import Enum

class Tier(str, Enum):
    MECHANICAL = "mechanical"      # tier 1
    CONVERSATIONAL = "conversational"  # tier 2
    CRITICAL = "critical"          # tier 3

def get_model(tier: Tier):
    """Resolve a chat model for a node's tier from settings.

    Every node calls this. No node constructs a client directly, so
    switching providers is an .env change and never a code change.
    """
    provider = settings.provider_for(tier)   # "ollama" | "gemini" | "anthropic" | ...
    ...
```

Then in `.env`:

```
LLM_MECHANICAL=ollama:llama3.1:8b
LLM_CONVERSATIONAL=ollama:llama3.1:8b
LLM_CRITICAL=anthropic:claude-opus-5
```

**Three things this buys you beyond cost control:**

1. Development runs entirely offline and free; evaluation runs against whatever you choose.
2. If a free tier changes its terms mid-project — which happens — you change one line, not the
   codebase.
3. It makes §6 possible.

---

## 6. Turn the constraint into a results chapter

This is the strongest reason to build provider-agnostically, and it is worth more marks than the
money saved.

Once model choice is a config value, you can run **the identical evaluation set across several
models** and report the comparison:

| Model | Red-flag recall | Triage agreement | Groundedness | p95 latency | Cost / session |
|---|---|---|---|---|---|
| Local 8B | | | | | $0 |
| Free-tier hosted | | | | | $0 |
| Paid frontier | | | | | |

That table answers a question nobody else in your cohort will have asked: **how much model quality
does a clinical follow-up system actually need, and where does it stop mattering?**

If the local model matches the frontier model on triage agreement but collapses on verifier catch
rate, that is a genuine finding about where reasoning quality is load-bearing in a safety pipeline.
It sits naturally alongside the verifier and RAG ablations already planned in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §5.3, and it is the kind of result that makes a
project report worth reading.

A single-model project reports "our system works." A multi-model comparison reports "here is what
the system needs in order to work." The second is a better project.

---

## 7. Recommendation

1. **Send the academic credits email this week.** Highest leverage, one email, may end the problem.
2. **Install Ollama and build Phase 3 against a local model.** Most of your development loop is
   testing whether the graph routes correctly, not whether the medical reasoning is excellent.
3. **Write `app/core/llm.py` as a tiered factory from the first node**, not as a refactor later.
4. **Budget roughly $20–50 of paid API for tier-3 evaluation runs** and treat it as a project
   expense. If the credits come through, it is zero.
5. **Report which model produced which number**, always. A weaker model with an honestly labelled
   result is fine. An unlabelled result is not.

---

## 8. What not to do

- **Do not degrade tier-0 to save money.** Red-flag rules and the drug database stay deterministic.
  They are already free.
- **Do not report accuracy figures without naming the model that produced them.** This is the one
  thing here that would genuinely damage the project.
- **Do not put a real API key in a free-tier signup you have not read the data-use terms for.**
- **Do not let the model choice slip past Phase 3.** Discovering in February that the local model
  cannot hold a JSON schema is recoverable; discovering it in April is not.
