# Hardware Test Setup (Picoprobe + Pico Target)

This guide documents a practical hardware setup for integration and deployment tests.

## Goal

Use one RP2040 board as a debug probe (Picoprobe firmware) and one raspberry pi nano board as the target.

The host PC is connected by USB to:

- the probe board
- the target board

In addition, the probe UART is connected to target UART pins `1-3`, and probe SWD is connected to target SWD.

## Realistic wiring diagram

```text
 PC USB #1 ------------------------------> Probe Pico (Picoprobe firmware)
 PC USB #2 ------------------------------> Target Pico (device under test)


 Probe Pico header pins (physical)                 Target Pico header pins (physical)
 ------------------------------------------------  -----------------------------------
 pin 4  (GP2  / SWCLK) -------------------------->  SWCLK debug pin
 pin 5  (GP3  / SWDIO) <------------------------->  SWDIO debug pin
 pin 8  (GND) ----------------------------------->  GND debug pin

 pin 6  (GP4  / UART TX) ------------------------>  pin 2 (GP1 / UART0_RX)
 pin 7  (GP5  / UART RX) <------------------------  pin 1 (GP0 / UART0_TX)
 pin 8  (GND) ----------------------------------->  pin 3 (GND)
```

## Connection table

### UART wiring to target Pico (requested pin set `1-3`)

| Target Pico pin | Signal           | Connect to probe |
| --------------- | ---------------- | ---------------- |
| `1`             | `GP0 / UART0_TX` | Probe `RX`       |
| `2`             | `GP1 / UART0_RX` | Probe `TX`       |
| `3`             | `GND`            | Probe `GND`      |

### SWD wiring to target Pico debug pins

| Target signal | Connect to probe     |
| ------------- | -------------------- |
| `SWCLK`       | Probe `SC` / `SWCLK` |
| `SWDIO`       | Probe `SD` / `SWDIO` |
| `GND`         | Probe `GND`          |

On Pico/Pico W, SWD uses dedicated debug pads/pins (not the `1..40` GPIO header).

## If the probe is another Pico running `debugprobe_on_pico`

Probe Pico mapping with physical pin numbers:

| Probe Pico physical pin | GPIO  | Role                               |
| ----------------------- | ----- | ---------------------------------- |
| `4`                     | `GP2` | `SWCLK`                            |
| `5`                     | `GP3` | `SWDIO`                            |
| `6`                     | `GP4` | `UART TX` (to target RX pin `2`)   |
| `7`                     | `GP5` | `UART RX` (from target TX pin `1`) |
| `8`                     | `GND` | Ground                             |

## Practical notes

- Keep a common ground between probe and target before attaching signal lines.
- UART must be crossed (`TX -> RX`, `RX -> TX`).
- SWDIO is bidirectional; connect it as a single data line between probe and target.
- Keep both boards at `3.3V` logic.
- For this repository:
  - integration tests mainly use target USB CDC
  - deployment tests use SWD operations (`probe-rs`) and USB behavior checks

## References

- Raspberry Pi Debug Probe docs (wiring, UART pin `1-3`, SWD cable labels):  
  https://www.raspberrypi.com/documentation/microcontrollers/debug-probe.html
- `debugprobe_on_pico` GPIO mapping (`board_pico_config.h`):  
  https://raw.githubusercontent.com/raspberrypi/debugprobe/master/include/board_pico_config.h
