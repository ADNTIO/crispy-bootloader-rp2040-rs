# Architecture Decisions (ADR)

This page tracks architecture decisions for the project using ADRs (Architecture Decision Records).

## Status

- `Accepted`: decision currently in force
- `Superseded`: replaced by another ADR
- `Proposed`: under discussion

## Decision log

| ADR | Title | Status | Date |
| --- | --- | --- | --- |
| [ADR-0001](adr/ADR-0001-dual-bank-update-model.md) | Dual-bank firmware update model | Accepted | 2026-02-13 |
| [ADR-0002](adr/ADR-0002-ram-buffered-upload.md) | RAM-buffered upload before flash write | Accepted | 2026-02-13 |
| [ADR-0003](adr/ADR-0003-cooperative-services-and-events.md) | Cooperative services + event bus | Accepted | 2026-02-13 |

## Add a new ADR

1. Create a new file in `docs/explanation/adr/` named `ADR-XXXX-short-title.md`.
1. Use this structure:

```md
# ADR-XXXX: Title

- Status: Proposed | Accepted | Superseded
- Date: YYYY-MM-DD

## Context

## Decision

## Consequences

## Alternatives considered

## References
```

1. Add it to the table above.
