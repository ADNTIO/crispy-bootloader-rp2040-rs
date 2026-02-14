# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Hardware helper functions for integration tests.

Provides probe-rs wrappers, SWD flashing utilities, USB device discovery,
and serial helpers.  Shared by bootsequence and deployment tests.
"""

import os
import subprocess
import time
from pathlib import Path

# Constants matching crispy-common-rs/src/protocol.rs
RAM_UPDATE_FLAG_ADDR = 0x2003_BFF0
RAM_UPDATE_MAGIC = 0x0FDA_7E00
CHIP = "rp2040"


def run_probe_rs(*args):
    """Run a probe-rs command and return (success, output)."""
    cmd = ["probe-rs"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def flash_elf(elf_path: Path) -> bool:
    """Flash an ELF file to the device via SWD."""
    print(f"Flashing {elf_path} via SWD...")
    success, output = run_probe_rs("download", "--chip", CHIP, str(elf_path))
    if not success:
        print(f"Flash failed: {output}")
    return success


def erase_flash() -> bool:
    """Erase the entire flash via SWD."""
    print("Erasing flash...")
    success, output = run_probe_rs("erase", "--chip", CHIP)
    if not success:
        print(f"Erase failed: {output}")
    return success


def reset_device() -> bool:
    """Reset the device via SWD."""
    success, _ = run_probe_rs("reset", "--chip", CHIP)
    return success


def erase_boot_data() -> bool:
    """Erase boot data sector via SWD to invalidate firmware metadata."""
    import tempfile

    boot_data_addr = 0x1019_0000
    sector = b"\xFF" * 4096
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(sector)
        blank_path = f.name
    try:
        success, output = run_probe_rs(
            "download", "--chip", CHIP,
            "--binary-format", "bin",
            "--base-address", hex(boot_data_addr),
            blank_path,
        )
        if not success:
            print(f"Failed to erase boot data: {output}")
        return success
    finally:
        Path(blank_path).unlink(missing_ok=True)


def enter_update_mode_via_swd() -> bool:
    """Enter bootloader update mode by erasing boot data and resetting.

    Two-layer approach:
    1. Erase boot data so the bootloader finds no valid firmware
    2. Write RAM magic as a belt-and-suspenders trigger
    3. Reset — bootloader enters update mode either via magic or
       because no firmware exists (fallback in main loop)
    """
    print("Entering update mode via SWD...")

    # Erase boot data — ensures bootloader can't boot any firmware
    if not erase_boot_data():
        print("Warning: failed to erase boot data, trying magic only")

    # Write RAM magic (may or may not survive the race with reset)
    run_probe_rs(
        "write", "--chip", CHIP, "b32",
        hex(RAM_UPDATE_FLAG_ADDR), hex(RAM_UPDATE_MAGIC)
    )

    # Reset device
    success, output = run_probe_rs("reset", "--chip", CHIP)
    if not success:
        print(f"Failed to reset: {output}")
        return False

    # Wait for bootloader to initialize USB
    time.sleep(3.0)
    return True


def force_bootsel_mode() -> bool:
    """Force RP2040 into BOOTSEL mode by invalidating boot2 via SWD.

    Writes zeros over the boot2 area (first 256 bytes at 0x10000000) so
    the ROM CRC check fails, then resets.  The ROM bootloader enters USB
    mass-storage mode (BOOTSEL) because it cannot find a valid stage-2.
    """
    import tempfile

    print("Forcing BOOTSEL mode (invalidating boot2 via SWD)...")

    zeros = b"\x00" * 256
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(zeros)
        blank_path = f.name
    try:
        success, output = run_probe_rs(
            "download", "--chip", CHIP,
            "--binary-format", "bin",
            "--base-address", "0x10000000",
            blank_path,
        )
        if not success:
            print(f"Failed to invalidate boot2: {output}")
            return False
    finally:
        Path(blank_path).unlink(missing_ok=True)

    # Reset — ROM finds invalid boot2 → BOOTSEL
    success, output = run_probe_rs("reset", "--chip", CHIP)
    if not success:
        print(f"Failed to reset after boot2 erase: {output}")
        return False

    return True


def find_rpi_rp2_mount(timeout: float = 15.0) -> Path:
    """Wait for the RPI-RP2 mass-storage drive and return its mount point.

    Polls ``/proc/mounts`` for a filesystem whose mount path contains
    ``RPI-RP2``.  If the drive appears as a block device but is not yet
    mounted, attempts to mount it via ``udisksctl``.

    Raises ``TimeoutError`` if the drive is not found within *timeout* seconds.
    """
    import json

    start = time.time()
    while time.time() - start < timeout:
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

        time.sleep(0.5)

    raise TimeoutError(f"RPI-RP2 drive not found within {timeout}s")


def _walk_lsblk(devices):
    """Recursively yield devices from a ``lsblk -J`` tree."""
    for dev in devices:
        yield dev
        for child in dev.get("children", []):
            yield child
            yield from _walk_lsblk(child.get("children", []))


def flash_uf2(uf2_path: Path, timeout: float = 15.0) -> bool:
    """Flash a UF2 file via BOOTSEL mass-storage mode.

    1. Forces BOOTSEL mode (invalidate boot2 + reset via SWD).
    2. Waits for the ``RPI-RP2`` drive to appear.
    3. Copies the UF2 file; the RP2040 reboots automatically.
    """
    import shutil

    if not force_bootsel_mode():
        return False

    # Give time for USB mass-storage enumeration
    time.sleep(2.0)

    try:
        mount = find_rpi_rp2_mount(timeout=timeout)
    except TimeoutError:
        print("RPI-RP2 mass-storage not found")
        return False

    print(f"Copying {uf2_path.name} to {mount} ...")
    shutil.copy2(str(uf2_path), str(mount / uf2_path.name))
    subprocess.run(["sync"], check=True)

    # Device reboots automatically after UF2 is written
    print("UF2 copied — waiting for device reboot ...")
    time.sleep(3.0)
    return True


def find_bootloader_port(timeout: float = 10.0) -> str:
    """Find the serial port for the Crispy Bootloader by USB ID."""
    return find_firmware_port(pid="000a", timeout=timeout)


def find_firmware_port(pid: str, timeout: float = 10.0, vid: str = "2e8a") -> str:
    """Find a serial port by USB VID/PID via sysfs.

    Args:
        pid: USB Product ID (hex string, e.g. "000a").
        timeout: How long to poll before raising TimeoutError.
        vid: USB Vendor ID (hex string, defaults to "2e8a").
    """
    import glob as _glob

    start = time.time()
    while time.time() - start < timeout:
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
        time.sleep(0.5)

    raise TimeoutError(f"USB device {vid}:{pid} not found within {timeout}s")


def wait_for_serial_banner(
    port: str, expected_text: str, timeout: float = 10.0
) -> str:
    """Open a serial port and read until *expected_text* appears.

    Returns the full text read so far (including the matching line).
    Raises ``TimeoutError`` if the text is not found within *timeout* seconds.
    """
    import serial

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


def run_crispy_upload(
    project_root: "Path", port: str, *args: str
) -> "tuple[bool, str, str]":
    """Execute ``cargo run -p crispy-upload-rs -- <args>`` and return results.

    Returns:
        (success, stdout, stderr)
    """
    cmd = [
        "cargo", "run", "--release", "-p", "crispy-upload-rs", "--",
        "--port", port,
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=project_root, capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0, result.stdout, result.stderr
