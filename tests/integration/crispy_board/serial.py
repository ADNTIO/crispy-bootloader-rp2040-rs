# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Serial port utilities."""

import serial
import time


def wait_for_serial_banner(
    port: str, expected_text: str, timeout: float = 10.0,
) -> str:
    """Open a serial port and read until *expected_text* appears.

    Returns the full text read so far (including the matching line).
    Raises ``TimeoutError`` if the text is not found within *timeout* seconds.
    """
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
