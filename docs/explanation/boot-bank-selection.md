# Boot Bank Selection and Rollback

This page explains how the bootloader chooses a firmware bank and when it rolls back.

## Scope

This is an explanation page (decision flow and behavior).
For canonical data definitions, use:

- [Boot data reference](../reference/boot-data.md)
- [Memory map reference](../reference/memory-map.md)

## Responsibilities

The bank selection logic is responsible for:

1. Selecting a bank to boot
2. Detecting repeated failed boots
3. Rolling back to the alternate bank when needed
4. Falling back to weaker validation when full metadata is unavailable

## Implementation location

- Main entry point: `crispy-bootloader/src/boot.rs`
- Selection function: `select_boot_bank()`

## Selection flow

```text
Start boot
  -> Read BootData
  -> Check rollback condition (attempts >= threshold && not confirmed)
       -> if true: toggle active bank, reset attempts
  -> Try candidate strategies in order:
       1) active bank with CRC validation
       2) alternate bank with CRC validation
       3) active bank with basic vector validation
       4) alternate bank with basic vector validation
       5) default active bank (last-resort boot attempt)
  -> Update BootData in flash
  -> Copy firmware to RAM and jump
```

## Rollback behavior

Rollback is triggered when the current firmware repeatedly fails to confirm boot.

- A boot attempt counter is incremented by the bootloader
- Firmware confirmation marks an image as healthy
- If attempts reach threshold without confirmation, the active bank is toggled

Current threshold in code: `MAX_BOOT_ATTEMPTS = 3`.

## Validation levels

### Full validation

Used when metadata is available:

- Vector table sanity checks
- Size presence
- CRC32 match

### Basic validation

Fallback path when metadata is incomplete:

- Vector table sanity checks only

## BootData fields used by selection logic

The selection logic consumes these fields from `BootData`:

- `active_bank`
- `confirmed`
- `boot_attempts`
- `size_a` / `size_b`
- `crc_a` / `crc_b`

Field definitions and layout are documented in [Boot data reference](../reference/boot-data.md).

## Related decision

- [ADR-0001: Dual-bank firmware update model](adr/ADR-0001-dual-bank-update-model.md)
