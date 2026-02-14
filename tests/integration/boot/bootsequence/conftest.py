# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Fixtures for bootsequence tests (require RP2040 hardware via SWD/USB)."""

import subprocess
import time

import pytest

from hardware import (
    enter_update_mode_via_swd,
    find_bootloader_port,
    flash_elf,
    reset_device,
)


@pytest.fixture(scope="session")
def flashed_device(project_root, skip_flash):
    """
    Ensure device has bootloader flashed.

    This fixture:
    1. Builds bootloader if necessary
    2. Flashes the bootloader ELF via SWD
    3. Resets the device

    Note: Firmware is NOT flashed here - it will be uploaded via USB
    protocol during tests to test the real update workflow.
    """
    if skip_flash:
        print("Skipping flash (--skip-flash)")
        return True

    target_dir = project_root / "target" / "thumbv6m-none-eabi" / "release"
    bootloader_elf = target_dir / "crispy-bootloader"

    # Build if necessary
    if not bootloader_elf.exists():
        print("Bootloader not found, building...")
        result = subprocess.run(
            [
                "cargo", "build", "--release",
                "-p", "crispy-bootloader",
                "-p", "crispy-fw-sample-rs",
                "--target", "thumbv6m-none-eabi",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to build: {result.stderr}")

    if not bootloader_elf.exists():
        pytest.fail(f"Bootloader ELF not found: {bootloader_elf}")

    # Flash only bootloader (firmware will be uploaded via USB during tests)
    if not flash_elf(bootloader_elf):
        pytest.fail("Failed to flash bootloader")

    # Reset device - bootloader will enter update mode since no valid firmware
    reset_device()
    time.sleep(2.0)

    return True


@pytest.fixture(scope="session")
def device_in_update_mode(flashed_device):
    """
    Ensure device is in bootloader update mode.

    Uses SWD to write RAM magic flag and reset.
    """
    if not enter_update_mode_via_swd():
        pytest.fail("Failed to enter update mode via SWD")
    return True


@pytest.fixture
def transport(device_in_update_mode):
    """
    Create a transport connection to the device in update mode.

    This is function-scoped so each test that modifies bootloader state
    gets a fresh connection. The fixture resets the bootloader via SWD
    before creating the connection.
    """
    from crispy_protocol.transport import Transport

    # Reset bootloader to Idle state via SWD
    enter_update_mode_via_swd()

    # Find the bootloader port
    try:
        port = find_bootloader_port(timeout=10.0)
    except TimeoutError:
        pytest.fail("Bootloader serial port not found after reset")

    # Give device time to enumerate USB
    time.sleep(0.5)

    transport = Transport(port, timeout=5.0)
    yield transport
    transport.close()
