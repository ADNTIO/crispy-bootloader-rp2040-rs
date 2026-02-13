# Development Methodology

## The Idea

This project is built with an AI coding assistant. A human drives the intent, the AI
helps write the code, and a Raspberry Pi Pico decides if it actually works.

This is a human-in-the-loop AI-assisted development approach: the AI supports
implementation, but final technical decisions remain with a human.

Nothing gets merged into `main` unless it runs on hardware. Period.

From there, we iterate: clean up the code, improve the architecture, refactor —
all with the safety net of tests that run on the actual target.

The goal is to evaluate whether AI-assisted development is effective for embedded
software — and to improve the method along the way.

## How It Works

### AI as a Pair Programmer

The AI writes code, suggests patterns, catches mistakes. The human decides *what* to
build and *why*. Every change is reviewed before it goes in. The AI is a tool, not
the driver.

### Test-Driven, Hardware First

We don't trust "it compiles". We don't even fully trust unit tests on the host.
The Raspberry Pi Pico is the source of truth.

The validation chain looks like this:

1. **Unit tests** — `cargo test` on the host for pure logic (CRC, protocol, parsing)
2. **Integration tests** — pytest talks to the board over USB CDC, exercises the real
   bootloader running on the chip
3. **Deployment tests** — firmware is uploaded via USB, the board reboots, and we verify
   that the new firmware actually runs correctly (bank switching, version reporting,
   rollback behavior)

If step 1 passes but step 3 fails, the change does not get merged.

### Iterate on Quality

The first version of anything is allowed to be rough. Working code on hardware beats
clean code that's never been tested on the target.

Once something works and is merged, we come back and improve it:
- simplify the logic
- extract better abstractions
- clean up naming and structure
- reduce coupling between modules

The tests make this safe. If a refactor breaks something, the integration suite
catches it before it ever reaches `main`.

## The Workflow

```
   define what to build
          │
          ▼
   implement with AI assistance
          │
          ▼
   unit tests pass?  ──no──►  fix
          │ yes
          ▼
   flash to hardware
          │
          ▼
   integration tests pass?  ──no──►  fix
          │ yes
          ▼
   deployment tests pass?  ──no──►  fix
          │ yes
          ▼
   merge to main
          │
          ▼
   iterate: refactor, improve, repeat
```

## Why Bother

The point of this project is to form an opinion on AI-assisted embedded development.
Does it actually help? Where does it fall short? Can the method be improved?

Embedded is not like web dev. You can't mock a flash controller that disables interrupts
for 2ms. You can't simulate USB enumeration timing. The Raspberry Pi Pico *is* the spec.
That makes it a good testbed: if AI-generated code works here, it works for real.

## A Word of Honesty

The code here is not perfect, and it won't pretend to be. I'm still junior in Rust,
and this whole project is a learning process — both for the language and for working
with AI on embedded systems.

If you spot something wrong, something ugly, or something that could be done better:
please say so. Issues, PRs, comments — all welcome. Criticism is how this gets better.

## Concept Reference

For a compact definition of the model used in this project, see:

- [AI-assisted development concept](ai-assisted-development.md)
