# Boot Bank Selection & Rollback

This document describes the boot bank selection logic used by the bootloader
to choose which firmware bank to boot from, and the automatic rollback mechanism.

## Overview

The crispy-bootloader implements an A/B firmware update scheme with automatic rollback.
The bank selection logic is responsible for:

1. Selecting the correct firmware bank to boot
2. Tracking boot attempts to detect boot loops
3. Automatically rolling back to a known-good firmware if the current one fails
4. Gracefully degrading validation when metadata is unavailable

## Implementation

The bank selection logic lives in `crispy-bootloader/src/boot.rs`, in the
`select_boot_bank()` function. It combines hardware-level validation (flash reads,
CRC computation, vector table checks) with the decision logic in a single module.

```
┌─────────────────────────────────────────────────────────────┐
│                    crispy-bootloader                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    boot.rs                           │   │
│  │  - select_boot_bank()   bank selection + rollback    │   │
│  │  - validate_bank_with_crc()  full CRC validation     │   │
│  │  - validate_bank()      basic vector table check     │   │
│  │  - load_and_jump()      copy to RAM + jump           │   │
│  │  - run_normal_boot()    main boot entry point        │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │ uses                              │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │               crispy-common/protocol.rs              │   │
│  │  - BootData struct (persisted in flash)              │   │
│  │  - Flash layout constants                            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Boot Flow

```
                    ┌─────────────────┐
                    │   Start Boot    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Check Rollback  │
                    │   Condition     │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ attempts >= 3   │           │ attempts < 3    │
    │ && !confirmed   │           │ || confirmed    │
    └────────┬────────┘           └────────┬────────┘
             │                             │
             ▼                             │
    ┌─────────────────┐                    │
    │  Toggle Bank    │                    │
    │  Reset Attempts │                    │
    └────────┬────────┘                    │
             │                             │
             └──────────────┬──────────────┘
                            │
                            ▼
            ┌───────────────────────────────┐
            │    Try Strategies in Order    │
            │                               │
            │  1. Primary bank + CRC check  │
            │  2. Fallback bank + CRC check │
            │  3. Primary bank (vector only)│
            │  4. Fallback bank (vector only│
            │  5. Default (primary anyway)  │
            └───────────────┬───────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Update BootData│
                   │  in Flash       │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Copy to RAM    │
                   │  + Jump         │
                   └─────────────────┘
```

## Rollback Mechanism

The bootloader tracks boot attempts to detect boot loops:

1. **Boot Attempts Counter**: Incremented each boot, stored in `BootData`
2. **Confirmation Flag**: Set by firmware after successful initialization
3. **Rollback Threshold**: `MAX_BOOT_ATTEMPTS = 3`

### Rollback Condition

```rust
// crispy-bootloader/src/boot.rs
if bd.boot_attempts >= MAX_BOOT_ATTEMPTS && bd.confirmed == 0 {
    bd.active_bank = toggle_bank(bd.active_bank);
    bd.boot_attempts = 0;
}
```

If the firmware boots 3 times without confirming (calling the confirm API), the bootloader
assumes the firmware is broken and switches to the other bank.

### Firmware Confirmation

Firmware must call the bootloader's confirm API after successful initialization:

```rust
// In firmware, after successful boot
let confirmed = crispy_common::flash::confirm_boot(); // returns bool
```

This sets `confirmed = 1` in `BootData`, preventing rollback even if `boot_attempts`
exceeds the threshold. Returns `false` if `BootData` is invalid.

## Validation Levels

### Full CRC Validation (`validate_bank_with_crc`)

The strongest validation, requires:
- Non-zero firmware size in BootData
- Valid vector table (SP and reset vector in RAM range)
- CRC32 checksum matches stored value

### Basic Validation (`validate_bank`)

Fallback validation when CRC data is unavailable:
- Valid vector table only (SP and reset vector point to RAM)
- Used when firmware was loaded without metadata

## Strategy Priority

The `select_boot_bank()` function tries strategies in this order:

| Priority | Strategy | Validation | Bank |
|----------|----------|------------|------|
| 1 | Primary + CRC | Full CRC32 | Active bank |
| 2 | Fallback + CRC | Full CRC32 | Alternate bank |
| 3 | Primary + basic | Vector table | Active bank |
| 4 | Fallback + basic | Vector table | Alternate bank |
| 5 | Default | None | Active bank |

This ensures:
- Prefer the active bank when valid
- Fall back to alternate bank if primary fails
- Degrade gracefully from CRC to basic validation
- Always attempt to boot something (default case)

## BootData Structure

Defined in `crispy-common/src/protocol.rs`, persisted in flash at `BOOT_DATA_ADDR` (0x10190000):

```rust
#[repr(C)]
#[derive(Clone, Copy)]
pub struct BootData {
    pub magic: u32,        // 0xB007DA7A
    pub active_bank: u8,   // 0 = A, 1 = B
    pub confirmed: u8,     // 1 = confirmed good
    pub boot_attempts: u8, // rollback after 3
    pub _reserved0: u8,
    pub version_a: u32, // firmware version in bank A
    pub version_b: u32, // firmware version in bank B
    pub crc_a: u32,     // CRC32 of bank A firmware
    pub crc_b: u32,     // CRC32 of bank B firmware
    pub size_a: u32,    // size of firmware in bank A
    pub size_b: u32,    // size of firmware in bank B
}
```

Total size: 32 bytes (fixed, `repr(C)`)

## Example Scenarios

### Scenario 1: Normal Boot

```
BootData: active_bank=0, attempts=0, confirmed=0
Bank A: CRC valid
Bank B: CRC valid

Result: Boot Bank A, attempts=1
```

### Scenario 2: Primary CRC Invalid

```
BootData: active_bank=0, attempts=0, confirmed=0
Bank A: CRC invalid
Bank B: CRC valid

Result: Boot Bank B, attempts=1, active_bank=1
```

### Scenario 3: Boot Loop Detection

```
BootData: active_bank=0, attempts=3, confirmed=0
Bank A: CRC valid
Bank B: CRC valid

Result: Rollback to Bank B, attempts=1, active_bank=1
```

### Scenario 4: Confirmed Firmware

```
BootData: active_bank=0, attempts=5, confirmed=1
Bank A: CRC valid

Result: Boot Bank A, attempts=6 (no rollback due to confirmed=1)
```

## Related ADR

- [ADR-0001: Dual-bank firmware update model](adr/ADR-0001-dual-bank-update-model.md)
