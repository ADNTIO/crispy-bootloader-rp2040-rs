# Run Integration Tests

Integration tests run against real hardware over USB CDC.

## Prerequisites

- RP2040 board connected
- SWD probe for flash/reset automation

Recommended first:

- [Hardware test setup (Picoprobe + Pico target)](hardware-test-setup.md)

## Integration tests

```bash
CRISPY_DEVICE=/dev/ttyACM0 make test-integration
```

Or using pytest directly:

```bash
cd tests/integration
uv run pytest boot/bootsequence/ -v --device /dev/ttyACM0
```

## Deployment tests

```bash
CRISPY_DEVICE=/dev/ttyACM0 make test-deployment
```

This runs a full hardware flow: erase, flash bootloader, upload Rust and C++ firmware, switch banks, reboot, wipe.

## Environment variables

| Variable | Description |
| --- | --- |
| `CRISPY_DEVICE` | USB serial port (for example `/dev/ttyACM0`) |
| `CRISPY_SKIP_BUILD` | Skip build when set to `1` |
| `CRISPY_SKIP_FLASH` | Skip flashing when set to `1` |
