# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""SWD flash and UF2 flash operations."""

import shutil
import subprocess
import time
from pathlib import Path

from crispy_board.constants import (
    BOOT2_ADDR,
    BOOT2_SIZE,
    BOOT_DATA_ADDR,
    BOOT_DATA_SECTOR_SIZE,
    CHIP,
    RAM_UPDATE_FLAG_ADDR,
    RAM_UPDATE_MAGIC,
)
from crispy_board.discovery import find_rpi_rp2_mount
from crispy_board.probe import download_binary, run


def flash_elf(elf_path: Path) -> bool:
    """Flash an ELF file to the device via SWD."""
    print(f"Flashing {elf_path} via SWD...")
    result = run("download", "--chip", CHIP, str(elf_path))
    if not result.success:
        print(f"Flash failed: {result.output}")
    return result.success


def erase_flash() -> bool:
    """Erase the entire flash via SWD."""
    print("Erasing flash...")
    result = run("erase", "--chip", CHIP)
    if not result.success:
        print(f"Erase failed: {result.output}")
    return result.success


def reset_device() -> bool:
    """Reset the device via SWD."""
    return run("reset", "--chip", CHIP).success


def erase_boot_data() -> bool:
    """Erase boot data sector via SWD to invalidate firmware metadata."""
    result = download_binary(
        b"\xFF" * BOOT_DATA_SECTOR_SIZE, BOOT_DATA_ADDR,
    )
    if not result.success:
        print(f"Failed to erase boot data: {result.output}")
    return result.success


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
    run(
        "write", "--chip", CHIP, "b32",
        hex(RAM_UPDATE_FLAG_ADDR), hex(RAM_UPDATE_MAGIC),
    )

    # Reset device
    result = run("reset", "--chip", CHIP)
    if not result.success:
        print(f"Failed to reset: {result.output}")
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
    print("Forcing BOOTSEL mode (invalidating boot2 via SWD)...")

    result = download_binary(b"\x00" * BOOT2_SIZE, BOOT2_ADDR)
    if not result.success:
        print(f"Failed to invalidate boot2: {result.output}")
        return False

    # Reset — ROM finds invalid boot2 → BOOTSEL
    result = run("reset", "--chip", CHIP)
    if not result.success:
        print(f"Failed to reset after boot2 erase: {result.output}")
        return False

    return True


def flash_uf2(uf2_path: Path, timeout: float = 15.0) -> bool:
    """Flash a UF2 file via BOOTSEL mass-storage mode.

    1. Forces BOOTSEL mode (invalidate boot2 + reset via SWD).
    2. Waits for the ``RPI-RP2`` drive to appear.
    3. Copies the UF2 file; the RP2040 reboots automatically.
    """
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
