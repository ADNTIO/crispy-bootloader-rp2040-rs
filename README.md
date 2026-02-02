# Crispy RP2040 — Bootloader + Firmware

Rust workspace for Raspberry Pi Pico (RP2040) with an A/B bootloader that copies firmware from flash to RAM.

## Project Structure

```
crispy-bootloader/   # RP2040 bootloader (flash → RAM copy, A/B bank selection)
crispy-fw-sample/    # Sample firmware (linked for RAM execution at 0x20000000)
crispy-common/       # Shared crate (board init, LED blink)
linker_scripts/      # Memory layouts for bootloader and firmware
```

## Prerequisites

- [Rust](https://rustup.rs/) with `thumbv6m-none-eabi` target:
  ```bash
  rustup target add thumbv6m-none-eabi
  ```
- `arm-none-eabi-objcopy` (for creating the combined binary):
  ```bash
  # Ubuntu/Debian
  sudo apt install gcc-arm-none-eabi
  ```
- Custom probe-rs with software breakpoint support (see below)

## Build

```bash
# Build bootloader + firmware
cargo build --release -p crispy-bootloader -p crispy-fw-sample

# Create combined binary (bootloader + firmware bank A)
./scripts/build-combined.sh

# Check formatting
cargo fmt --all -- --check
```

## Custom probe-rs (required for debugging)

This project runs firmware from RAM (0x20000000+). The Cortex-M0+ FPB hardware breakpoint unit
only supports flash addresses, so standard probe-rs **cannot set breakpoints** in the firmware.

We use a [fork of probe-rs](https://github.com/fmahon/probe-rs/tree/feat/software-breakpoints)
that adds software breakpoint support — it injects `BKPT` instructions into RAM, enabling
breakpoints in RAM-resident code via DAP (VSCode) and GDB.

```bash
cargo install probe-rs-tools \
  --git https://github.com/fmahon/probe-rs.git \
  --branch feat/software-breakpoints \
  --locked --force
```

Verify: `probe-rs --version`

## Flash & Run

```bash
# Flash the combined binary via SWD
probe-rs download --chip RP2040 --binary-format bin --base-address 0x10000000 \
  target/thumbv6m-none-eabi/release/combined.bin

# Or flash UF2 via BOOTSEL mode (requires picotool)
./scripts/flash.sh
```

## Debugging (VSCode)

Install the [probe-rs](https://marketplace.visualstudio.com/items?itemName=probe-rs.probe-rs-debugger) VSCode extension. Three debug configurations are provided:

- **Debug Bootloader** — Launch: builds, flashes, halts at bootloader entry
- **Debug Firmware (via bootloader)** — Attach: full boot chain, then attach to running firmware
- **Debug Firmware (direct RAM)** — Attach: loads firmware directly to RAM for fast iteration

## Memory Layout

```
Flash (2MB):
  0x10000000  BOOT2 (256B)
  0x10000100  Bootloader (16KB)
  0x10004100  FW Bank A (768KB)
  0x100C4100  FW Bank B (768KB)
  0x10184100  BOOT_DATA (4KB)

RAM (256KB):
  0x20000000  Firmware code (192KB, copied by bootloader)
  0x20030000  Firmware data/BSS/stack (48KB)
  0x2003C000  Bootloader data/BSS/stack (16KB)
```

## License

MIT — Copyright (c) 2026 ADNT Sàrl
