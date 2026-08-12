# Backend

FastAPI · LangGraph · PostgreSQL 16 + pgvector · Python 3.11+

Design reference: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
Build schedule: [`../docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md)

---

## Planned layout

Create directories as you fill them — do not scaffold empty folders.

```
backend/
├── app/
│   ├── main.py               FastAPI entrypoint
│   ├── core/                 config, settings, security, JWT
│   ├── db/
│   │   ├── models/           SQLAlchemy models (one file per domain)
│   │   └── session.py        engine, session factory
│   ├── schemas/              Pydantic request/response + agent output models
│   ├── api/
│   │   ├── deps.py           shared dependencies, auth guards
│   │   └── routes/           one module per resource
│   ├── agents/
│   │   ├── graph.py          LangGraph assembly — the whole turn
│   │   ├── state.py          TurnState (ARCHITECTURE.md §6)
│   │   └── nodes/            one file per node
│   ├── services/
│   │   ├── drug_lookup.py    RxNorm / openFDA — deterministic
│   │   ├── redflag_rules.py  tier-1 screen — deterministic
│   │   ├── notifications.py  in-app, email, later SMS
│   │   ├── scheduler.py      APScheduler jobs
│   │   └── redaction.py      PHI redaction at LLM egress and in logs
│   └── evaluation/           hooks that emit metrics from live runs
├── alembic/                  migrations
└── tests/
```

### Two rules about this layout

**`services/` is for deterministic code. `agents/nodes/` is for model calls.** If a file in
`services/` starts calling the Anthropic API, something has gone wrong — most likely the drug
lookup, which must never be model-generated
([`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §1 row 6).

**Every clinical read is gated on `doctor_patient_link`.** Put that check in `api/deps.py` as a
dependency and use it everywhere, rather than re-implementing the check per route. One missed
route is a data breach.

---

## Environment variables

Copy to `backend/.env` — which is gitignored and must stay that way.

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://mediagent:dev@localhost:5432/mediagent` | |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | **Never commit.** Rotate immediately if leaked. |
| `JWT_SECRET` | long random string | Generate per environment, do not reuse |
| `JWT_EXPIRE_MINUTES` | `60` | |
| `RXNORM_BASE_URL` | `https://rxnav.nlm.nih.gov/REST` | Public, no key |
| `OPENFDA_API_KEY` | optional | Raises the rate limit |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | | Phase 2 notifications |
| `ENVIRONMENT` | `dev` \| `test` \| `prod` | Gates redaction and log verbosity |
| `LOG_LEVEL` | `INFO` | |

Document any new variable here in the same PR that introduces it.

---

## Local setup

Once `docker-compose.yml` and `requirements.txt` exist (Phase 1):

```bash
docker compose up -d db
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

API docs at `http://localhost:8000/docs`.

---

## Conventions

- **Migrations, never `create_all()`.** Every schema change is an Alembic revision, reviewed like
  code.
- **Clinical tables are append-only.** Correct by inserting a new row. `audit_log` is written by a
  database trigger so application code cannot bypass it.
- **Agent outputs are Pydantic models**, parsed via the SDK's structured-output helper — not JSON
  strings you parse yourself.
- **Never log raw patient utterances.** Log the session ID and the structured finding. `redaction.py`
  exists for this and it is not optional.
- **Tests for every red-flag rule.** That module is the safety floor; it is the one place where a
  regression is a patient-safety issue rather than a bug.
