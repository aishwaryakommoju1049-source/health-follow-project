# Frontend

React 18 · Vite · TypeScript · Tailwind CSS

Two distinct applications sharing one codebase and one build: the **patient app** and the
**doctor dashboard**. They have almost no screens in common and very different design
requirements — do not try to share components beyond primitives.

---

## Planned layout

```
frontend/
├── index.html
├── src/
│   ├── main.tsx
│   ├── routes.tsx            role-gated routing
│   ├── lib/
│   │   ├── api.ts            typed client, generated from the OpenAPI schema
│   │   └── auth.ts           token handling, role guards
│   ├── components/           shared primitives only — Button, Field, Card
│   ├── patient/
│   │   ├── CheckIn.tsx       the conversational check-in
│   │   ├── Medications.tsx   prescriptions + mark-as-taken
│   │   └── History.tsx       the patient's own timeline
│   └── doctor/
│       ├── Queue.tsx         risk-ranked patient list
│       ├── PatientDetail.tsx timeline, adherence, trend
│       └── ReviewNote.tsx    SOAP note with approve / edit / override
└── tests/
```

Generate `lib/api.ts` from the backend's OpenAPI schema rather than hand-writing types. FastAPI
publishes it at `/openapi.json`; that keeps the two sides from drifting.

---

## Design requirements that are not negotiable

These come from [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §4 and
[`../docs/IMPLEMENTATION_PLAN.md`](../docs/IMPLEMENTATION_PLAN.md) §6. They are safety
requirements, not styling preferences.

- **The emergency number 108 is visible on every patient screen.** Not behind a menu, not gated on
  a triage result, not conditional on anything. Put it in the persistent layout.
- **When a red flag fires, the patient sees the emergency instruction immediately** — without
  waiting for a clinician to acknowledge. The two branches run in parallel.
- **Nothing AI-generated reaches a patient labelled as clinical advice.** Plain language, framed as
  "what to do next," with the doctor-review status shown.
- **Doctor overrides are a first-class action**, not an edge case buried in a menu. Approving,
  editing, and rejecting an AI summary should be equally easy, because the edit data is an
  evaluation metric.
- **Show uncertainty.** When an agent reports low confidence, the interface says so rather than
  rendering a guess with the same weight as a fact.

---

## Accessibility

Patients using this may be unwell, elderly, or on a low-end phone.

- Minimum 16px body text; never rely on colour alone to convey urgency
- Every interactive element keyboard-reachable with a visible focus state
- Test at 360px width — assume a budget Android phone, not a laptop
- Respect `prefers-reduced-motion`

---

## Local setup

Once `package.json` exists (Phase 2):

```bash
npm install
npm run dev
```

Expects the backend at `http://localhost:8000`; override with `VITE_API_BASE_URL` in
`frontend/.env.local` (gitignored).
