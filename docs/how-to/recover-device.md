# Recover a Device

Use this guide when the board is in a bad state (boot loop, invalid bank, failed update).

Hardware wiring reference:

- [Hardware test setup (Picoprobe + Pico target)](hardware-test-setup.md)

## 1. Force update mode

Choose one method:

- Hardware: hold `GP2` low during reset.
- Firmware command: send `bootload` on firmware serial console.
- SWD utility:

```bash
make update-mode
```

## 2. Inspect bootloader state

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 status
```

## 3. Reset boot metadata and banks

```bash
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 wipe
```

Then upload a known-good firmware:

```bash
make firmware-bin
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 upload \
  target/thumbv6m-none-eabi/release/crispy-fw-sample-rs.bin --bank 0 --fw-version 1
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 set-bank 0
cargo run --release -p crispy-upload-rs -- --port /dev/ttyACM0 reboot
```

## 4. Last resort: reflash bootloader

Reflash the bootloader UF2 through BOOTSEL mode:

- [Flash the bootloader for the first time](../tutorials/first-bootloader-flash.md)
