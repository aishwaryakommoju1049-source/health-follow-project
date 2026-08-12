# Documentation

| File | What it covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design, all diagrams, component spec, graph state, data model |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Stack decisions, six-phase schedule, evaluation plan, scope boundaries, risks |
| [`LLM_PROVIDER_STRATEGY.md`](LLM_PROVIDER_STRATEGY.md) | Free vs. paid models, tiered routing, cost estimates, provider-agnostic setup |
| [`project-proposal.pdf`](project-proposal.pdf) | The submitted abstract — original filename `FINAL YEAR PROJECT.pdf` |
| [`decisions/`](decisions/) | Short records of non-obvious architectural choices |
| [`diagrams/`](diagrams/) | Diagram sources, including the superseded v1 Lucidchart export |

---

## Reading order

**New to the project:** `ARCHITECTURE.md` §1 (what changed from v1 and why) → §2 (system loop) →
§3 (session turn). That is the whole design in about ten minutes.

**Picking up a build task:** `IMPLEMENTATION_PLAN.md` §3 for your phase, then the relevant rows of
`ARCHITECTURE.md` §5 for the components you are touching.

**Writing the report:** `ARCHITECTURE.md` §1 is written as a design-decisions table you can adapt
directly. `IMPLEMENTATION_PLAN.md` §5 is the evaluation chapter.

---

## Conventions

- **Diagrams are Mermaid, inside the Markdown.** Not separate image files. This keeps them
  reviewable in a diff — a changed edge shows up as a changed line, which a PNG cannot do.
  Rendering instructions are in `ARCHITECTURE.md` §8.
- **Docs are versioned with the code.** If a PR changes behaviour the architecture describes, it
  updates the doc in the same PR. A doc that drifts is worse than no doc.
- **Section numbers are stable.** Other files and the report cite them. Add subsections rather than
  renumbering.
