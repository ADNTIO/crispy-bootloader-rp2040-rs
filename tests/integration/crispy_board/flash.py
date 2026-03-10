# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

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
    print(f"Flashing {elf_path} via SWD...")
    result = run("download", "--chip", CHIP, str(elf_path))
    if not result.success:
        print(f"Flash failed: {result.output}")
    return result.success


def erase_flash() -> bool:
    print("Erasing flash...")
    result = run("erase", "--chip", CHIP)
    if not result.success:
        print(f"Erase failed: {result.output}")
    return result.success


def reset_device() -> bool:
    return run("reset", "--chip", CHIP).success


def erase_boot_data() -> bool:
    result = download_binary(
        b"\xFF" * BOOT_DATA_SECTOR_SIZE, BOOT_DATA_ADDR,
    )
    if not result.success:
        print(f"Failed to erase boot data: {result.output}")
    return result.success


def enter_update_mode_via_swd() -> bool:
    """Erase boot data + write RAM magic + reset to enter update mode."""
    print("Entering update mode via SWD...")

    if not erase_boot_data():
        print("Warning: failed to erase boot data, trying magic only")

    # RAM magic may or may not survive the race with reset
    run(
        "write", "--chip", CHIP, "b32",
        hex(RAM_UPDATE_FLAG_ADDR), hex(RAM_UPDATE_MAGIC),
    )

    result = run("reset", "--chip", CHIP)
    if not result.success:
        print(f"Failed to reset: {result.output}")
        return False

    time.sleep(3.0)
    return True


def force_bootsel_mode() -> bool:
    """Invalidate boot2 (first 256 bytes) via SWD so ROM enters BOOTSEL."""
    print("Forcing BOOTSEL mode (invalidating boot2 via SWD)...")

    result = download_binary(b"\x00" * BOOT2_SIZE, BOOT2_ADDR)
    if not result.success:
        print(f"Failed to invalidate boot2: {result.output}")
        return False

    result = run("reset", "--chip", CHIP)
    if not result.success:
        print(f"Failed to reset after boot2 erase: {result.output}")
        return False

    return True


def flash_uf2(uf2_path: Path, timeout: float = 15.0) -> bool:
    """Force BOOTSEL, wait for RPI-RP2 drive, copy UF2."""
    if not force_bootsel_mode():
        return False

    time.sleep(2.0)

    try:
        mount = find_rpi_rp2_mount(timeout=timeout)
    except TimeoutError:
        print("RPI-RP2 mass-storage not found")
        return False

    print(f"Copying {uf2_path.name} to {mount} ...")
    shutil.copy2(str(uf2_path), str(mount / uf2_path.name))
    subprocess.run(["sync"], check=True)

    print("UF2 copied — waiting for device reboot ...")
    time.sleep(3.0)
    return True
