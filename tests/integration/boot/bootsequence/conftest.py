# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import time

import pytest

from crispy_board import (
    build_packages,
    enter_update_mode_via_swd,
    find_bootloader_port,
    flash_elf,
    reset_device,
)


@pytest.fixture(scope="session")
def flashed_device(project_root, skip_flash):
    """Ensure device has bootloader flashed (firmware uploaded via USB during tests)."""
    if skip_flash:
        print("Skipping flash (--skip-flash)")
        return True

    target_dir = project_root / "target" / "thumbv6m-none-eabi" / "release"
    bootloader_elf = target_dir / "crispy-bootloader"

    if not bootloader_elf.exists():
        print("Bootloader not found, building...")
        result = build_packages(
            project_root,
            ["crispy-bootloader", "crispy-fw-sample-rs"],
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to build: {result.stderr}")

    if not bootloader_elf.exists():
        pytest.fail(f"Bootloader ELF not found: {bootloader_elf}")

    if not flash_elf(bootloader_elf):
        pytest.fail("Failed to flash bootloader")

    reset_device()
    time.sleep(2.0)

    return True


@pytest.fixture(scope="session")
def device_in_update_mode(flashed_device):
    if not enter_update_mode_via_swd():
        pytest.fail("Failed to enter update mode via SWD")
    return True


@pytest.fixture
def transport(device_in_update_mode):
    """Function-scoped transport: resets bootloader via SWD before each test."""
    from crispy_protocol.transport import Transport

    enter_update_mode_via_swd()

    try:
        port = find_bootloader_port(timeout=10.0)
    except TimeoutError:
        pytest.fail("Bootloader serial port not found after reset")

    time.sleep(0.5)

    transport = Transport(port, timeout=5.0)
    yield transport
    transport.close()
