# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Pytest configuration for integration tests.

Environment variables (used as defaults when CLI options are not provided):
    CRISPY_DEVICE       Serial port (e.g. /dev/ttyACM0)
    CRISPY_SKIP_BUILD   Set to "1" to skip building
    CRISPY_SKIP_FLASH   Set to "1" to skip flashing
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

# Constants matching crispy-common/src/protocol.rs
RAM_UPDATE_FLAG_ADDR = 0x2003_BFF0
RAM_UPDATE_MAGIC = 0x0FDA_7E00
CHIP = "rp2040"


def _env_bool(name: str) -> bool:
    """Read an environment variable as a boolean (truthy: '1', 'true', 'yes')."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--device",
        action="store",
        default=os.environ.get("CRISPY_DEVICE"),
        help="Serial port for the device (env: CRISPY_DEVICE)",
    )
    parser.addoption(
        "--skip-build",
        action="store_true",
        default=_env_bool("CRISPY_SKIP_BUILD"),
        help="Skip building firmware (env: CRISPY_SKIP_BUILD=1)",
    )
    parser.addoption(
        "--skip-flash",
        action="store_true",
        default=_env_bool("CRISPY_SKIP_FLASH"),
        help="Skip flashing device (env: CRISPY_SKIP_FLASH=1)",
    )


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
    """Execute ``cargo run -p crispy-upload -- <args>`` and return results.

    Returns:
        (success, stdout, stderr)
    """
    cmd = [
        "cargo", "run", "--release", "-p", "crispy-upload", "--",
        "--port", port,
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=project_root, capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0, result.stdout, result.stderr


@pytest.fixture(scope="session")
def device_port(request):
    """Get the device port from command line (optional override)."""
    return request.config.getoption("--device")


@pytest.fixture(scope="session")
def skip_build(request):
    """Check if build should be skipped."""
    return request.config.getoption("--skip-build")


@pytest.fixture(scope="session")
def skip_flash(request):
    """Check if flash should be skipped."""
    return request.config.getoption("--skip-flash")


@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


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
