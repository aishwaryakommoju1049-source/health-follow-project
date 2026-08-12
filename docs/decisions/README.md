# Design decisions

Short records of choices that were not obvious, so that in March nobody has to reconstruct the
reasoning from memory — and so the viva question *"why did you use X instead of Y?"* has a written
answer.

One file per decision: `NNNN-short-title.md`, numbered in the order they were made. Never edit a
decision once it is merged — if it changes, write a new one that supersedes it and link both ways.
The trail of superseded decisions is itself useful.

---

## Log

| # | Decision | Status |
|---|---|---|
| 0001 | LangGraph over CrewAI for orchestration | Accepted — rationale in `IMPLEMENTATION_PLAN.md` §1.1 |
| 0002 | PostgreSQL + pgvector from day one, no SQLite phase | Accepted — §1.2 |
| 0003 | Drug interactions from RxNorm/openFDA, never model-generated | Accepted — `ARCHITECTURE.md` §1 row 6 |
| 0004 | Two-tier red-flag screening, deterministic tier first | Accepted — §1 row 5 |
| 0005 | PHI redaction at the LLM egress boundary, not at ingest | Accepted — §1 row 4 |
| 0006 | Tiered LLM routing; provider resolved from config, not hardcoded | Accepted — [`../LLM_PROVIDER_STRATEGY.md`](../LLM_PROVIDER_STRATEGY.md) |

> These five are currently recorded inline in the architecture and plan documents rather than as
> separate files. Split them out into full records when you write the report — each one maps to a
> paragraph you will need anyway.

---

## Template

```markdown
# NNNN — <Title>

**Status:** Proposed | Accepted | Superseded by NNNN
**Date:** YYYY-MM-DD
**Deciders:** <names>

## Context
What forced a choice? What constraint or requirement made the default insufficient?

## Options considered
1. **<Option>** — what it would mean in practice.
2. **<Option>** — ditto.

## Decision
What we chose, stated plainly.

## Why
The reasoning. Be specific about the tradeoff accepted, not just the benefit gained.

## Consequences
What this makes easy. What it makes hard. What we will have to revisit if it turns out wrong.
```

---

## When to write one

Write a record when the answer to *"why is it like this?"* is not visible in the code:

- Choosing between two libraries or services that both work
- Accepting a known limitation on purpose
- A safety or clinical boundary (these are the most important ones to record)
- Anything an examiner is likely to ask about

Do **not** write one for routine implementation detail. If the code explains itself, let it.
