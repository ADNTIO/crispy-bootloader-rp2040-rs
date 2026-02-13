# CLI Reference: crispy-upload

`crispy-upload` is the host CLI used to manage the bootloader over USB CDC.

## Syntax

```bash
crispy-upload [--version|-v] [--port <PORT>] <COMMAND>
```

`--port` is required for all commands except `bin2uf2`.

## Show Tool Version

```bash
crispy-upload --version
```

## Commands

### `status`

Get current bootloader status:

```bash
crispy-upload --port /dev/ttyACM0 status
```

Typical output:

```text
Bootloader Status:
  Bootloader:  1.2.3
  Active bank: 0 (A)
  Version A:   5
  Version B:   4
  State:       UpdateMode
```

On older bootloader builds, `Bootloader` may be shown as `unknown`.

### `upload <FILE> [--bank <0|1>] [--fw-version <N>]`

Upload a firmware binary to a target bank:

```bash
crispy-upload --port /dev/ttyACM0 upload firmware.bin --bank 0 --fw-version 1
```

`--version` remains accepted as an alias of `--fw-version` for backward compatibility.
Use `-V` as the short form for firmware version.

### `set-bank <BANK>`

Select active bank for next boot:

```bash
crispy-upload --port /dev/ttyACM0 set-bank 1
```

### `wipe`

Wipe both firmware banks and reset boot metadata:

```bash
crispy-upload --port /dev/ttyACM0 wipe
```

### `reboot`

Reboot device:

```bash
crispy-upload --port /dev/ttyACM0 reboot
```

### `bin2uf2 <INPUT> <OUTPUT> [--base-address <HEX>] [--family-id <HEX>]`

Convert a raw binary into UF2:

```bash
crispy-upload bin2uf2 input.bin output.uf2 --base-address 0x10000000 --family-id 0xE48BFF56
```
