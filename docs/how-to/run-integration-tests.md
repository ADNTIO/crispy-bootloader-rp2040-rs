# Run Integration Tests

Integration tests run against real hardware over USB CDC.

## Prerequisites

- RP2040 board connected
- Optional SWD probe for flash/reset automation
- Python environment in `scripts/python/`

Recommended first:

- [Hardware test setup (Picoprobe + Pico target)](hardware-test-setup.md)

## Option 1: End-to-end script

```bash
./scripts/test-integration.sh --device /dev/ttyACM0
```

Common flags:

- `--skip-build`: reuse existing artifacts
- `--skip-flash`: skip flashing step
- `--verbose`: verbose output

## Option 2: Pytest directly

```bash
cd scripts/python
uv run pytest tests/test_integration.py -v --device /dev/ttyACM0
```

## Environment variables

| Variable | Description |
| --- | --- |
| `CRISPY_DEVICE` | USB serial port (for example `/dev/ttyACM0`) |
| `CRISPY_SKIP_BUILD` | Skip build when set to `1` |
| `CRISPY_SKIP_FLASH` | Skip flashing when set to `1` |

## Deployment tests

```bash
make test-deployment
```

This runs a full hardware flow: erase, flash bootloader, upload Rust and C++ firmware, switch banks, reboot, wipe.
