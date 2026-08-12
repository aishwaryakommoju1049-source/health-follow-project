# Diagrams

**The current diagrams live in [`../ARCHITECTURE.md`](../ARCHITECTURE.md)** as Mermaid blocks, not
in this folder. This folder holds diagram *sources* that cannot be expressed as Mermaid, plus
superseded versions kept for the record.

---

## Contents

| File | What it is |
|---|---|
| `v1-original.json` | Lucidchart export of the first workflow diagram — *Clinical Intake Orchestration* |
| `v1-original.png` | Rendered image of the same |

Both files are byte-identical to the originals; only the filenames changed (they were
`Blank diagram.json` and `Blank diagram.png`).

---

## Why v1 is kept

v1 is **superseded, not wrong.** It described a single request-to-response pass; the system needed
to be a loop over many such passes. Its pipeline survives essentially intact as "one session turn"
inside the v2 architecture.

Keep it because:

- The v1 → v2 delta table in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §1 references it directly.
- Showing a design that evolved for stated reasons is stronger in a report than presenting a final
  design as if it arrived fully formed. The report's design chapter should show both.

---

## Adding a diagram

Prefer Mermaid inside the relevant Markdown file. It diffs, it reviews, and it cannot drift out of
sync with the document that explains it.

Put a file here only when Mermaid genuinely cannot express what you need — a UI mockup, a
hand-drawn sketch, a screenshot. If you do:

- Commit the **editable source**, not just an exported image
- Name it `<topic>-v<n>.<ext>`
- Add a row to the table above saying what it shows and which document references it

For print-quality exports of the Mermaid diagrams, see [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
§8.
