# Development Methodology

## The Idea

This project is built with an AI coding assistant. A human drives the intent, the AI
helps write the code, and a real RP2040 board decides if it actually works.

Nothing gets merged into `main` unless it runs on hardware. Period.

From there, we iterate: clean up the code, improve the architecture, refactor —
all with the safety net of tests that run on the actual target.

## How It Works

### AI as a Pair Programmer

The AI writes code, suggests patterns, catches mistakes. The human decides *what* to
build and *why*. Every change is reviewed before it goes in. The AI is a tool, not
the driver.

### Test-Driven, Hardware First

We don't trust "it compiles". We don't even fully trust unit tests on the host.
The RP2040 is the source of truth.

The validation chain looks like this:

1. **Unit tests** — `cargo test` on the host for pure logic (CRC, protocol, parsing)
2. **Integration tests** — pytest talks to the board over USB CDC, exercises the real
   bootloader running on the chip
3. **Deployment tests** — firmware is uploaded via USB, the board reboots, and we verify
   that the new firmware actually runs correctly (bank switching, version reporting,
   rollback behavior)
4. **Manual check** — the developer looks at the board and confirms it does what it should

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

Embedded is not like web dev. You can't mock a flash controller that disables interrupts
for 2ms. You can't simulate USB enumeration timing. The hardware *is* the spec.

This approach gives us:
- **Fast iterations** thanks to AI assistance
- **Real confidence** because every merge is hardware-proven
- **Sustainable quality** because we refactor with a safety net
- **Clean history** where each commit on `main` is a known-working state
