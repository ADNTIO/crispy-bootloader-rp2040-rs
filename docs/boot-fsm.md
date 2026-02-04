# Boot Bank Selection FSM

This document describes the Finite State Machine (FSM) used by the bootloader to select which firmware bank to boot from.

## Overview

The crispy-bootloader implements an A/B firmware update scheme with automatic rollback. The boot FSM is responsible for:

1. Selecting the correct firmware bank to boot
2. Tracking boot attempts to detect boot loops
3. Automatically rolling back to a known-good firmware if the current one fails
4. Gracefully degrading validation when metadata is unavailable

## Architecture

The FSM is implemented as pure logic in `crispy-common/src/boot_fsm.rs`, separate from hardware-dependent code. This allows:

- Unit testing on the host without embedded hardware
- Clear separation between decision logic and hardware operations
- Reusability across different bootloader implementations

```
┌─────────────────────────────────────────────────────────────┐
│                    crispy-bootloader                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    boot.rs                           │   │
│  │  - Hardware validation (flash reads, CRC compute)    │   │
│  │  - Memory layout from linker symbols                 │   │
│  │  - Jump to firmware                                  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │ uses                              │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │                  boot_fsm.rs                         │   │
│  │  (re-exports from crispy-common)                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    crispy-common                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               boot_fsm.rs (pure logic)               │   │
│  │  - BankInfo, BankPair, BootDecision types            │   │
│  │  - BootStrategy enum                                 │   │
│  │  - select_boot_bank_fsm() - main FSM function        │   │
│  │  - needs_rollback(), toggle_bank(), etc.             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Types

### BankInfo

Information about a single firmware bank:

```rust
struct BankInfo {
    addr: u32,      // Flash address of the bank
    crc: u32,       // Expected CRC32 checksum
    size: u32,      // Firmware size in bytes
    bank_id: u8,    // Bank identifier (0 = A, 1 = B)
}
```

### BankValidation

Validation results computed by hardware-level code:

```rust
struct BankValidation {
    crc_valid: bool,    // Full CRC32 validation passed
    basic_valid: bool,  // Basic vector table validation passed
}
```

### BankPair

A pair of banks with their validation results:

```rust
struct BankPair {
    primary: BankInfo,
    primary_validation: BankValidation,
    fallback: BankInfo,
    fallback_validation: BankValidation,
}
```

### BootDecision

The immutable result of the FSM decision:

```rust
struct BootDecision {
    flash_addr: u32,    // Address to boot from
    active_bank: u8,    // Which bank was selected
    boot_attempts: u8,  // Updated attempt counter
    confirmed: u8,      // Confirmation status
}
```

### BootStrategy

The four boot strategies, tried in priority order:

```rust
enum BootStrategy {
    PrimaryWithCrc,    // Primary bank with full CRC validation
    FallbackWithCrc,   // Fallback bank with full CRC validation
    PrimaryBasic,      // Primary bank with basic validation only
    FallbackBasic,     // Fallback bank with basic validation only
}
```

## FSM Flow

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
                   ┌─────────────────┐
                   │  Create BankPair │
                   │  (primary/fallback)
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Validate Banks  │
                   │ (hardware layer)│
                   └────────┬────────┘
                            │
                            ▼
            ┌───────────────────────────────┐
            │    Try Strategies in Order    │
            │                               │
            │  1. PrimaryWithCrc            │
            │  2. FallbackWithCrc           │
            │  3. PrimaryBasic              │
            │  4. FallbackBasic             │
            │  5. Default (primary anyway)  │
            └───────────────┬───────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  BootDecision   │
                   │  - flash_addr   │
                   │  - active_bank  │
                   │  - boot_attempts│
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Update BootData│
                   │  in Flash       │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Jump to        │
                   │  Firmware       │
                   └─────────────────┘
```

## Rollback Mechanism

The bootloader tracks boot attempts to detect boot loops:

1. **Boot Attempts Counter**: Incremented each boot, stored in `BootData`
2. **Confirmation Flag**: Set by firmware after successful initialization
3. **Rollback Threshold**: `MAX_BOOT_ATTEMPTS = 3`

### Rollback Condition

```rust
fn needs_rollback(bd: &BootData) -> bool {
    bd.boot_attempts >= MAX_BOOT_ATTEMPTS && bd.confirmed == 0
}
```

If the firmware boots 3 times without confirming (calling the confirm API), the bootloader assumes the firmware is broken and switches to the other bank.

### Firmware Confirmation

Firmware must call the bootloader's confirm API after successful initialization:

```rust
// In firmware, after successful boot
crispy_common::flash::confirm_boot();
```

This sets `confirmed = 1` in `BootData`, preventing rollback even if `boot_attempts` exceeds the threshold.

## Validation Levels

### Full CRC Validation

The strongest validation, requires:
- Valid `BootData` with correct magic number
- Non-zero firmware size
- Valid vector table (SP and reset vector in RAM range)
- CRC32 checksum matches stored value

### Basic Validation

Fallback validation when CRC data is unavailable:
- Valid vector table only
- Used when firmware was loaded without metadata

## Strategy Priority

The FSM tries strategies in this order:

| Priority | Strategy | Validation | Bank |
|----------|----------|------------|------|
| 1 | PrimaryWithCrc | CRC | Active |
| 2 | FallbackWithCrc | CRC | Alternate |
| 3 | PrimaryBasic | Vector table | Active |
| 4 | FallbackBasic | Vector table | Alternate |
| 5 | Default | None | Active |

This ensures:
- Prefer the active bank when valid
- Fall back to alternate bank if primary fails
- Degrade gracefully from CRC to basic validation
- Always attempt to boot something (default case)

## BootData Structure

```rust
#[repr(C)]
struct BootData {
    magic: u32,        // 0xB007DA7A
    active_bank: u8,   // 0 = A, 1 = B
    confirmed: u8,     // 1 = confirmed good
    boot_attempts: u8, // Rollback after 3
    _reserved0: u8,
    version_a: u32,    // Firmware version in bank A
    version_b: u32,    // Firmware version in bank B
    crc_a: u32,        // CRC32 of bank A firmware
    crc_b: u32,        // CRC32 of bank B firmware
    size_a: u32,       // Size of firmware in bank A
    size_b: u32,       // Size of firmware in bank B
}
```

Total size: 32 bytes (fixed, repr(C))

## Testing

The FSM is fully unit tested in `crispy-common/tests/boot_fsm_tests.rs`:

```bash
cargo test -p crispy-common --features std
```

Test coverage includes:
- Bank toggling
- Metadata extraction
- Rollback conditions
- All boot strategies
- Full FSM integration scenarios

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
