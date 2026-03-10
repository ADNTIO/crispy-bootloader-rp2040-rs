# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""USB device and serial port discovery with polling."""

import glob as _glob
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, TypeVar

from crispy_board.constants import DEFAULT_VID, PID_BOOTLOADER

T = TypeVar("T")


def poll_until(
    predicate: Callable[[], "T | None"],
    timeout: float,
    interval: float = 0.5,
    description: str = "",
) -> "T":
    """Poll *predicate* until it returns a truthy value, or raise TimeoutError.

    Args:
        predicate: Callable returning a value (found) or None (not yet).
        timeout: Maximum time to wait in seconds.
        interval: Sleep between attempts in seconds.
        description: Human-readable description for the TimeoutError message.
    """
    start = time.time()
    while time.time() - start < timeout:
        result = predicate()
        if result is not None:
            return result
        time.sleep(interval)
    raise TimeoutError(
        f"{description or 'Condition'} not met within {timeout}s"
    )


def find_rpi_rp2_mount(timeout: float = 15.0) -> Path:
    """Wait for the RPI-RP2 mass-storage drive and return its mount point.

    Polls ``/proc/mounts`` for a filesystem whose mount path contains
    ``RPI-RP2``.  If the drive appears as a block device but is not yet
    mounted, attempts to mount it via ``udisksctl``.

    Raises ``TimeoutError`` if the drive is not found within *timeout* seconds.
    """

    def _check() -> "Path | None":
        # Fast path: check /proc/mounts
        try:
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and "RPI-RP2" in parts[1]:
                        return Path(parts[1])
        except OSError:
            pass

        # Slow path: find unmounted block device via lsblk and mount it
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,LABEL,MOUNTPOINT"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for dev in _walk_lsblk(data.get("blockdevices", [])):
                    if dev.get("label") == "RPI-RP2":
                        mp = dev.get("mountpoint")
                        if mp:
                            return Path(mp)
                        # Try auto-mount
                        name = dev["name"]
                        subprocess.run(
                            ["udisksctl", "mount", "-b", f"/dev/{name}"],
                            capture_output=True, text=True, timeout=10,
                        )
        except (OSError, subprocess.TimeoutExpired):
            pass

        return None

    return poll_until(_check, timeout, description="RPI-RP2 drive")


def _walk_lsblk(devices):
    """Recursively yield devices from a ``lsblk -J`` tree."""
    for dev in devices:
        yield dev
        for child in dev.get("children", []):
            yield child
            yield from _walk_lsblk(child.get("children", []))


def find_firmware_port(
    pid: str, timeout: float = 10.0, vid: str = DEFAULT_VID,
) -> str:
    """Find a serial port by USB VID/PID via sysfs.

    Args:
        pid: USB Product ID (hex string, e.g. "000a").
        timeout: How long to poll before raising TimeoutError.
        vid: USB Vendor ID (hex string, defaults to "2e8a").
    """

    def _check() -> "str | None":
        for port in _glob.glob("/dev/ttyACM*"):
            try:
                tty_name = os.path.basename(port)
                sys_path = f"/sys/class/tty/{tty_name}/device/.."

                with open(f"{sys_path}/idVendor", "r") as f:
                    found_vid = f.read().strip()
                with open(f"{sys_path}/idProduct", "r") as f:
                    found_pid = f.read().strip()

                if found_vid == vid and found_pid == pid:
                    return port
            except (FileNotFoundError, IOError):
                continue
        return None

    return poll_until(
        _check, timeout, description=f"USB device {vid}:{pid}",
    )


def find_bootloader_port(timeout: float = 10.0) -> str:
    """Find the serial port for the Crispy Bootloader by USB ID."""
    return find_firmware_port(pid=PID_BOOTLOADER, timeout=timeout)
