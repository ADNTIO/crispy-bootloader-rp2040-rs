# Flash the Bootloader for the First Time

This tutorial gets a fresh RP2040 board running the Crispy bootloader.

## Prerequisites

- RP2040 board (for example Raspberry Pi Pico)
- USB cable
- Rust toolchain
- `cargo-binutils` + `llvm-tools-preview`

Install tools:

```bash
make install-tools
```

## 1. Build bootloader UF2

```bash
make bootloader-uf2
```

Expected artifact:

- `target/thumbv6m-none-eabi/release/crispy-bootloader.uf2`

## 2. Flash via BOOTSEL mode

1. Hold `BOOTSEL` while plugging or resetting the board.
2. Mount the `RPI-RP2` drive.
3. Copy the UF2 file:

```bash
cp target/thumbv6m-none-eabi/release/crispy-bootloader.uf2 /media/$USER/RPI-RP2/
```

## 3. Verify bootloader is alive

```bash
cargo run --release -p crispy-upload -- --port /dev/ttyACM0 status
```

You should see bootloader version, active bank, and firmware bank version fields.

## Next steps

- [Upload firmware](../how-to/upload-firmware.md)
- [Run integration tests](../how-to/run-integration-tests.md)
