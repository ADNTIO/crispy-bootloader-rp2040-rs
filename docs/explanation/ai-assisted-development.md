# AI-Assisted Development Concept

This project follows a human-in-the-loop AI-assisted development model.

## Definition

- AI acts as a pair programmer (drafting code, proposing options, surfacing issues).
- A human keeps final authority on intent, architecture, acceptance criteria, and merge decisions.
- Real hardware validation is required for embedded runtime behavior.

## Why this model here

- Embedded behavior is timing-sensitive and hardware-dependent.
- Host-only validation is useful but not sufficient.
- Human review plus hardware tests reduce risk from AI-generated errors.

## Repository application

Implementation workflow and quality gates are documented in:

- [Development methodology](development-methodology.md)

## Related documentation

- [Architecture](architecture.md)
- [Architecture decisions index](architecture-decisions.md)
