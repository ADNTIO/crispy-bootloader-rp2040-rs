# ADR-0003: Cooperative services + event bus

- Status: Accepted
- Date: 2026-02-13

## Context

The bootloader needs USB polling, trigger detection, update processing, and status indication.
For this scope, an RTOS or multicore scheduling would increase complexity and debugging cost.

## Decision

Use a single-threaded cooperative service loop with specialized services
(USB transport, trigger checks, update state management, LED behavior),
and communicate transitions through an event bus.

## Consequences

- Predictable execution model and lower integration complexity.
- Clear ownership boundaries between services.
- Throughput and latency depend on disciplined polling and queue sizing.

## Alternatives considered

- RTOS task model.
- Monolithic loop without service boundaries.

## References

- `docs/explanation/architecture.md`
