# Upload Firmware

This guide shows how to upload a firmware image to bank A or B with `crispy-upload`.

## Prerequisites

- Device running Crispy bootloader
- Device in update mode (USB CDC exposed)
- Firmware `.bin` file

Build sample Rust firmware binary:

```bash
make firmware-bin
```

Artifact:

- `target/thumbv6m-none-eabi/release/crispy-fw-sample-rs.bin`

## 1. Check bootloader status

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 status
```

The status output includes bootloader version (when available), active bank, and bank firmware versions.

## 2. Upload to a bank

Bank A (`0`):

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 upload \
  target/thumbv6m-none-eabi/release/crispy-fw-sample-rs.bin \
  --bank 0 --fw-version 1
```

Bank B (`1`):

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 upload \
  target/thumbv6m-none-eabi/release/crispy-fw-sample-rs.bin \
  --bank 1 --fw-version 1
```

`--version` is still accepted as an alias for backward compatibility, but `--fw-version` (`-V`) is preferred.

## 3. Reboot into selected bank

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 set-bank 0
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 reboot
```

## 4. Optional cleanup

Wipe both banks and boot metadata:

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 wipe
```

## See also

- [CLI reference](../reference/cli-crispy-upload.md)
- [Protocol reference](../reference/protocol.md)
