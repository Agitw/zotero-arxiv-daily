# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `CONTEXT.md` at the repo root, if it exists.
- `docs/adr/`, if it exists. Read ADRs that touch the area you are about to work in.

If any of these files do not exist, proceed silently. Do not flag their absence and do not suggest creating them upfront. Producer skills can create them later when terms or decisions actually get resolved.

## File structure

This is a single-context repo:

```text
/
|-- CONTEXT.md
|-- docs/
|   `-- adr/
`-- src/
```

## Use the glossary's vocabulary

When your output names a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in `CONTEXT.md`.

If the concept you need is not in the glossary yet, either reconsider whether you are inventing language the project does not use, or note the glossary gap for a future documentation pass.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding the decision.
