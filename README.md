# MediAgent

**An Agentic AI-Based Intelligent Patient Follow-Up and Healthcare Assistance System**

Final year project · Team 11 · 4/4 CSD-C
Guide: Mr. Y. Bheem Shankar · Aug 2026 – Apr 2027

---

## What this is

MediAgent monitors patients **after** they have consulted a registered doctor. It initiates
contact on a schedule, collects daily health updates, tracks medication adherence, detects
deterioration against the patient's own baseline, escalates red flags to their assigned doctor,
and produces clinical summaries for review.

It is a **follow-up** system, not an intake or symptom-checker system. That distinction drives the
entire architecture — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §1.

**MediAgent is not a diagnostic device.** It triages and reports; a human clinician approves
anything clinical. It never prescribes or alters a dose. See
[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) §6 for the full scope boundaries.

---

## Team

| Roll No | Name |
|---|---|
| A23126551161 | K. Bhavya Aishwarya |
| A23126551168 | M. Zarafsha Abbas |
| A23126551149 | I. Bhavan Sai |
| A23126551179 | T. Namanan Shri Vasthav |

---

## Repository layout

```
MedAgent/
├── docs/            Architecture, plan, proposal, diagrams, design decisions
├── backend/         FastAPI + LangGraph + PostgreSQL
├── frontend/        React + Vite — patient and doctor dashboards
└── eval/            Evaluation datasets, vignettes, metrics, results
```

Each directory has its own `README.md` explaining what belongs there and how it is organised.

---

## Start here

| If you want to… | Read |
|---|---|
| Understand the system | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Know what to build and when | [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) |
| See the original submitted abstract | [`docs/project-proposal.pdf`](docs/project-proposal.pdf) |
| Understand why a choice was made | [`docs/decisions/`](docs/decisions/) |
| Set up the backend | [`backend/README.md`](backend/README.md) |

---

## Status

**Phase 1 — Scope lock and skeleton.** Nothing is implemented yet.

Before any code is written, the framing in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §1 needs
sign-off from the project guide. See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
§0.

| Phase | Window | Status |
|---|---|---|
| 1 · Scope lock and skeleton | Aug 2026 | In progress |
| 2 · Non-AI spine | Sep – Oct 2026 | Not started |
| 3 · First agent, safety floor | Oct – Nov 2026 | Not started |
| 4 · Multi-agent fan-out | Dec 2026 – Jan 2027 | Not started |
| 5 · Doctor loop | Feb 2027 | Not started |
| 6 · Evaluation and write-up | Mar – Apr 2027 | Not started |

---

## Working agreements

- **Branch per feature**, PR into `main`. No direct pushes to `main`.
- **Never commit secrets.** API keys live in `backend/.env`, which is gitignored. If you commit one
  by accident, rotate it immediately — removing the commit is not enough.
- **Clinical data tables are append-only.** Correct by writing a new row, never by updating an old
  one. This is what makes the audit log trustworthy.
- **Record decisions.** When you make a non-obvious architectural choice, add a short file to
  [`docs/decisions/`](docs/decisions/). Future-you in March will not remember why.
