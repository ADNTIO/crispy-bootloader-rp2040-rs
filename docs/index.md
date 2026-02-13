# Crispy Bootloader Documentation

A minimal A/B bootloader for RP2040 with USB CDC firmware update support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Flash Layout (2MB)                          │
├─────────────────────────────────────────────────────────────────────┤
│ 0x10000000 │ BOOT2 (256B)                                           │
│ 0x10000100 │ Bootloader (64KB)                                      │
│ 0x10010000 │ Firmware Bank A (768KB)                                │
│ 0x100D0000 │ Firmware Bank B (768KB)                                │
│ 0x10190000 │ BootData (4KB)                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Documentation Index

### Guides

| Document | Description |
|----------|-------------|
| [Development Methodology](DEVELOPMENT_METHODOLOGY.md) | AI-assisted, test-driven, iterative approach |
| [Boot Bank Selection](boot-bank-selection.md) | A/B bank selection and rollback mechanism |

### Crates

| Crate | Description |
|-------|-------------|
| `crispy-bootloader` | Main bootloader binary for RP2040 |
| `crispy-common` | Shared types, protocol, and flash utilities |
| `crispy-upload` | Host CLI tool for firmware upload |
| `crispy-fw-sample-rs` | Sample firmware in Rust |
| `crispy-fw-sample-cpp` | Sample firmware in C++ |
| `crispy-sdk-cpp` | C++ SDK for Crispy bootloader |

## Prerequisites

The build system uses `rust-objcopy` (from `cargo-binutils`) instead of `arm-none-eabi-objcopy`
to convert ELF files to raw binaries. Install the required tools:

```bash
make install-tools
```

This installs:
- `llvm-tools-preview` rustup component (provides the LLVM objcopy backend)
- `cargo-binutils` (provides the `rust-objcopy` frontend)

## Quick Start

### Building

```bash
# Show all available targets
make help

# Build everything
make all

# Build bootloader only
make bootloader

# Build upload tool
make upload

# Build .bin files
make bootloader-bin firmware-bin

# Build bootloader UF2 (for BOOTSEL flashing)
make bootloader-uf2
```

### Flashing Bootloader

```bash
# Mount the RP2040 in BOOTSEL mode, then:
cp target/thumbv6m-none-eabi/release/crispy-bootloader.uf2 /media/$USER/RPI-RP2/
```

### Uploading Firmware

```bash
# Upload to bank A
crispy-upload --port /dev/ttyACM0 upload crispy-fw-sample-rs.bin --bank 0 --version 1

# Check status
crispy-upload --port /dev/ttyACM0 status

# Reboot device
crispy-upload --port /dev/ttyACM0 reboot
```

## Protocol

The bootloader communicates over USB CDC using a binary protocol:

- **Encoding**: COBS (Consistent Overhead Byte Stuffing)
- **Serialization**: postcard (serde-based)
- **Baud rate**: 115200 (ignored for USB CDC)

### Commands

| Command | Description |
|---------|-------------|
| `GetStatus` | Get bootloader status and versions |
| `StartUpdate` | Begin firmware upload to a bank |
| `DataBlock` | Send firmware data chunk (1KB max) |
| `FinishUpdate` | Complete upload and verify CRC |
| `SetActiveBank` | Set active bank without upload |
| `WipeAll` | Reset boot data (invalidate firmware) |
| `Reboot` | Reboot the device |

### Responses

| Response | Description |
|----------|-------------|
| `Ack(status)` | Acknowledgement with status code |
| `Status{...}` | Bootloader status information |

## Update Modes

### USB CDC Update Mode

Triggered by:
- Holding GP2 low during boot
- Setting RAM magic flag `0x0FDA7E00` at `0x2003BFF0`

### Runtime Update

Firmware can request update mode by:
1. Writing magic to RAM flag address
2. Triggering a software reset

## Memory Map

### RAM Layout

```
0x20000000 - 0x2003BFEF : Application RAM
0x2003BFF0 - 0x2003BFF3 : Update flag (magic: 0x0FDA7E00)
0x2003C000 - 0x2003FFFF : Reserved
```

### Firmware Execution

Firmware is copied from flash to RAM before execution:
- Base address: `0x20000000`
- Max size: 192KB

## Testing

```bash
# Run all tests
cargo test -p crispy-common --features std
```

## License

MIT License - See [LICENSE](../LICENSE) for details.
