# ADR-0002: RAM-buffered upload before flash write

- Status: Accepted
- Date: 2026-02-13

## Context

The RP2040 executes code directly from external flash via XIP (Execute In Place).
The flash controller uses a single SSI bus shared between XIP reads and flash program/erase commands.

During a flash erase or program operation, the SSI bus switches to command mode and **XIP is unavailable**.
Any instruction fetch from flash while the bus is busy causes the CPU to stall or triggers a HardFault.
This includes interrupt handlers: if a USB interrupt fires while flash is being written, the handler code (located in flash) cannot execute.

This makes **simultaneous flash writes and USB communication physically impossible** without relocating all USB-critical code to RAM.

## Decision

Separate the firmware upload into two distinct phases:

1. **Receive phase**: all firmware data blocks are received over USB and stored in a RAM buffer. The flash controller is idle, so XIP and USB work normally.
2. **Write phase** (`FinishUpdate`): USB communication is paused, flash is erased and programmed from the RAM buffer. CRC is validated on RAM data before write and on flash data after write.

## Consequences

- USB remains fully responsive during the entire receive phase.
- Flash integrity is verified both before and after writing.
- **Firmware size is limited to the RAM buffer size** (currently 192 KB out of 264 KB total SRAM). This is the primary constraint of this approach.

## Alternatives considered

- **Incremental flash writes during transfer**: would require copying the USB driver and all its dependencies into RAM (`#[link_section = ".data"]`) to avoid XIP conflicts. Fragile, hard to maintain, and increases RAM usage for code.
- **Immediate page-by-page writes with retry logic**: same XIP conflict. Adds protocol complexity with retry/NACK handling for packets lost during flash operations.
- **DMA-based flash writes**: the RP2040 SSI peripheral does not support DMA for flash program/erase commands; DMA only works for XIP reads.

## References

- RP2040 Datasheet, Section 4.10 (SSI / XIP)
- `docs/explanation/architecture.md`
- `docs/reference/protocol.md`
