# Evaluation

Full plan: [`../docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md) §5

> **This directory is the difference between a good project and a demo.** Most final-year AI
> projects show a screen recording and stop. Start filling this in **Phase 3**, not Phase 6 —
> retrofitting evaluation in March is how teams run out of time.

---

## Planned layout

```
eval/
├── datasets/
│   ├── synthea/          generator config + seed (output/ is gitignored)
│   └── README.md         provenance of every dataset
├── vignettes/
│   ├── redflag/          scenarios with known-correct escalation labels
│   ├── triage/           scenarios with known-correct urgency bands
│   └── adherence/        medication-pattern scenarios
├── runners/              scripts that execute a metric against the live system
└── results/
    ├── raw/              gitignored — full run dumps
    └── *.md              committed summary tables, one per run
```

**Commit the summary, gitignore the dump.** A Markdown table of results diffs cleanly and goes
straight into the report; a 200MB JSON dump does neither.

---

## Data sources

| Source | Use | Access |
|---|---|---|
| **Synthea** | Synthetic patients with histories, medications, conditions | Open source, no approval. **Start here.** |
| **Hand-written vignettes** | Triage and red-flag ground truth | Write 100–150; have the guide sanity-check a sample |
| MIMIC-IV | Richer real-world data | PhysioNet credentialing takes weeks — only start if genuinely needed |

**No real patient data enters this repository, ever.** The `.gitignore` has a backstop rule for
this, but the rule is the policy, not the file.

Record where every dataset came from in `datasets/README.md`. "Where did your evaluation data come
from?" is a guaranteed viva question.

---

## Metrics

| Metric | Target | Why it matters |
|---|---|---|
| **Red-flag recall** | Near 100% | The headline number |
| Red-flag precision | Report honestly | Will be lower — that is correct |
| Triage-band agreement | vs. labelled vignettes | Your accuracy claim |
| RAG groundedness | % of clinical claims traceable to a source | Hallucination rate, inverted |
| Verifier catch rate | Ungrounded claims blocked | Quantifies the safety layer |
| Adherence prediction | vs. logged ground truth | Medication Agent value |
| SOAP edit distance | AI draft vs. doctor-approved | Real quality signal |
| Latency p50 / p95 | Per turn | Report the tier-1 screen separately |
| Cost per session | Measured tokens | Measured, never estimated |

### On red-flag recall

**This metric is deliberately asymmetric, and say so in the report.** Tune the threshold toward
recall at the cost of precision: a missed stroke is unrecoverable, a false alarm is an annoyed
doctor. Report both numbers, state which one you optimised, and explain why in one sentence.

That sentence demonstrates you understand the clinical stakes better than any accuracy figure will.

---

## The ablation that writes your results chapter

Run the identical eval set three ways:

1. Full system
2. **Verifier disabled**
3. **RAG disabled**

If the verifier blocks a measurable number of ungrounded claims, you have quantified the value of
your own safety architecture. That is a far stronger result than "the system works," and it is
what turns a project report into something worth publishing.

**Then sweep the model tier as a second axis** — local 8B, free-tier hosted, paid frontier — across
the same eval set. See [`../docs/LLM_PROVIDER_STRATEGY.md`](../docs/LLM_PROVIDER_STRATEGY.md) §6.
Every result table must name the model that produced it.

---

## Free evaluation data you are already generating

Two sources cost nothing extra because Phase 4 and 5 produce them anyway:

- **`agent_findings`** — every structured agent output, from the first turn onwards
- **Doctor overrides** — the diff between the AI-drafted SOAP note and the approved version

Both are already in the schema ([`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §7). Make sure
nothing prunes them.
