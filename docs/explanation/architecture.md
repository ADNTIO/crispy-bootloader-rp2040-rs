# Bootloader Architecture

## Scope

This page explains the high-level architecture of the Crispy RP2040 bootloader.
It focuses on system shape and design intent, not on full API/constant listings.

For canonical technical details, use:

- [Memory map reference](../reference/memory-map.md)
- [Protocol reference](../reference/protocol.md)
- [Boot data reference](../reference/boot-data.md)

## System model

The bootloader implements an A/B update model:

- Two firmware banks in flash (`A`, `B`)
- Boot metadata (`BootData`) persisted in flash
- Firmware copied from flash to RAM before jump

This model supports rollback and safer updates when an uploaded firmware is invalid.

## Update lifecycle

The update flow is organized into explicit phases:

1. `Idle`: device is in update mode and accepts commands
2. `Receiving`: firmware blocks are staged in RAM
3. `FinishUpdate`: staged firmware is persisted to flash and verified
4. `Reboot`: next boot selects bank and jumps to firmware

The decision to stage in RAM and persist on `FinishUpdate` is documented in ADR-0002.

## Execution model

The runtime follows a cooperative service loop (single-threaded):

- USB transport service (I/O)
- Trigger service (entry conditions)
- Update service (state machine + command handling)
- LED service (status signaling)

Services communicate via events to keep responsibilities separated and transitions explicit.

## Bank selection and rollback

Bank selection logic is detailed separately in:

- [Boot bank selection and rollback](boot-bank-selection.md)

## Architecture decisions

Architecture-impacting decisions are tracked as ADRs:

- [Architecture decisions index](architecture-decisions.md)
- [ADR-0001: Dual-bank firmware update model](adr/ADR-0001-dual-bank-update-model.md)
- [ADR-0002: RAM-buffered upload before flash write](adr/ADR-0002-ram-buffered-upload.md)
- [ADR-0003: Cooperative services + event bus](adr/ADR-0003-cooperative-services-and-events.md)

## Implementation anchors

- Bank selection: `crispy-bootloader/src/boot.rs`
- Update state machine and services: `crispy-bootloader/src/main.rs`
- Shared protocol and layout constants: `crispy-common/src/protocol.rs`
