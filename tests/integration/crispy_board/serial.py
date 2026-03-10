# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import serial
import time


def wait_for_serial_banner(
    port: str, expected_text: str, timeout: float = 10.0,
) -> str:
    """Read from serial port until *expected_text* appears or timeout."""
    start = time.time()
    buf = ""
    with serial.Serial(port, baudrate=115200, timeout=1) as ser:
        while time.time() - start < timeout:
            raw = ser.read(ser.in_waiting or 1)
            if raw:
                buf += raw.decode(errors="replace")
                if expected_text in buf:
                    return buf
    raise TimeoutError(
        f"Banner '{expected_text}' not found on {port} within {timeout}s"
    )
