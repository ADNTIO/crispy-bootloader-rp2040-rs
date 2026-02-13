# Crispy RP2040 — Bootloader + Firmware

> **⚠️ AI-Assisted Development**: This bootloader is being developed with AI assistance
> under human supervision. Every iteration is tested and validated on real hardware before merging.
> See [Development Methodology](docs/DEVELOPMENT_METHODOLOGY.md) for the approach and
> [Architecture](docs/ARCHITECTURE.md) for design decisions.

A/B bootloader for RP2040 (Raspberry Pi Pico) written in Rust. The bootloader copies firmware
from flash to RAM before executing it, and supports two banks for safe over-the-air updates
via USB CDC.

```
         FLASH (2MB)                          RAM (256KB)
  ┌─────────────────────┐
  │  BOOT2 (256B)       │
  ├─────────────────────┤
  │  Bootloader (64KB)  │──── selects A or B
  ├─────────────────────┤          │
  │  FW Bank A (768KB)  │──┐       │
  ├─────────────────────┤  ├───────┼───► copy ───► ┌──────────────────┐
  │  FW Bank B (768KB)  │──┘       │               │ Firmware (192KB) │
  ├─────────────────────┤          │               │ runs from RAM    │
  │  BOOT_DATA (4KB)    │ ◄────────┘               │ @ 0x20000000     │
  └─────────────────────┘    active bank           └──────────────────┘
```

Firmware updates are performed via USB CDC using `crispy-upload`, or via SWD with `probe-rs`.

> **Note:** Since firmware runs from RAM, standard probe-rs cannot set breakpoints (Cortex-M0+
> FPB only covers flash addresses). This project requires a
> [custom probe-rs fork](https://github.com/fmahon/probe-rs/tree/feat/software-breakpoints)
> that adds software breakpoint support. Install it with `make install-probe-rs`.

## Project Structure

```
crispy-bootloader/     # RP2040 bootloader (flash → RAM copy, A/B bank selection)
crispy-fw-sample-rs/   # Sample Rust firmware (runs from RAM @ 0x20000000)
crispy-fw-sample-cpp/  # Sample C++ firmware (Pico SDK)
crispy-sdk-cpp/        # C++ SDK for Crispy bootloader
crispy-common/         # Shared Rust crate (board init, flash operations)
crispy-upload/         # Host tool to manage the bootloader (upload, wipe, ...)
scripts/               # Utility scripts (flash, build, python)
linker_scripts/        # Memory layouts for bootloader and firmware
```

## Prerequisites

```bash
# Install rust-objcopy (cargo-binutils) and llvm-tools
make install-tools
```

## Quick Start

```bash
# Show all available targets
make help

# Build everything (ELF + BIN + UF2)
make all

# Show crispy-upload usage
cargo run --release -p crispy-upload -- --help
```

## Testing

### Unit Tests

```bash
make test
```

### Integration Tests (hardware)

Integration tests require a physical RP2040 board connected via SWD probe.

```bash
# Full run: build, flash, and test
./scripts/test-integration.sh --device /dev/ttyACM0

# Or using environment variables
export CRISPY_DEVICE=/dev/ttyACM0
./scripts/test-integration.sh
```

You can also run pytest directly from `scripts/python/`:

```bash
cd scripts/python
python -m pytest tests/test_integration.py -v --device /dev/ttyACM0
```

#### Environment Variables

| Variable            | Description                           | Example        |
| ------------------- | ------------------------------------- | -------------- |
| `CRISPY_DEVICE`     | Serial port of the bootloader         | `/dev/ttyACM0` |
| `CRISPY_SKIP_BUILD` | Skip cargo build step (`1` to enable) | `1`            |
| `CRISPY_SKIP_FLASH` | Skip SWD flashing (`1` to enable)     | `1`            |

These work with both `test-integration.sh` and `pytest`. CLI flags (`--device`,
`--skip-build`, `--skip-flash`) take precedence over environment variables.

#### CI Runner Example

For a self-hosted runner with a board permanently connected:

```bash
export CRISPY_DEVICE=/dev/ttyACM0
export CRISPY_SKIP_BUILD=1
export CRISPY_SKIP_FLASH=1
python -m pytest tests/test_integration.py -v
```

## License

MIT — Copyright (c) 2026 ADNT Sàrl
