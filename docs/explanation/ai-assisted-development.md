# AI-Assisted Development Concept

This project follows a human-in-the-loop AI-assisted development model.

## Definition

- AI is used as a pair programmer for implementation support (drafting code, proposing refactors, surfacing issues).
- A human keeps decision authority on intent, architecture, validation, and merge criteria.
- Real hardware validation is the release gate for embedded behavior.

## Why this model here

- Embedded constraints are hardware-dependent and timing-sensitive.
- Host-only checks are useful but not sufficient.
- Human review plus hardware tests reduce risk from AI-generated mistakes.

## How it is applied in this repository

- Feature intent and acceptance criteria are human-defined.
- Code is reviewed before merge.
- Unit tests, integration tests, and deployment tests are used as quality gates.
- Changes affecting runtime behavior are expected to be validated on RP2040 hardware.

## Related documentation

- [Development methodology](development-methodology.md)
- [Architecture](architecture.md)
- [Architecture decisions index](architecture-decisions.md)
