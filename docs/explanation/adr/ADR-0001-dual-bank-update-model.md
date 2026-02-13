# ADR-0001: Dual-bank firmware update model

- Status: Accepted
- Date: 2026-02-13

## Context

Firmware updates on embedded targets can fail due to power loss, transfer interruption, or invalid images.
A single-bank approach increases bricking risk because the running image is overwritten in place.

## Decision

Use two independent flash banks (`A` and `B`) and persist metadata in `BootData`.
The bootloader selects the active bank, validates it, and can fall back to the alternate bank.

## Consequences

- Safer update path with rollback capability.
- Higher flash usage because two firmware banks are reserved.
- Boot selection logic is more complex (validation strategy, active bank management).

## Alternatives considered

- Single-bank in-place update.
- External recovery-only strategy without rollback metadata.

## References

- `docs/explanation/boot-bank-selection.md`
- `docs/reference/boot-data.md`
- `docs/reference/memory-map.md`
