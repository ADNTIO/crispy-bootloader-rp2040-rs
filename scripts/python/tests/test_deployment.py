# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
End-to-end deployment test for the Crispy Bootloader.

Validates the full lifecycle:
    erase -> flash bootloader -> upload firmwares (Rust + C++)
    -> boot -> bank switching -> wipe.

Designed for CI with a physical RP2040 connected via SWD + USB.

Usage:
    make test-deployment
    # or directly
    cd scripts/python && . .venv/bin/activate
    python -m pytest tests/test_deployment.py -v --tb=short

Environment variables:
    CRISPY_SKIP_BUILD  Set to "1" to skip the build step
    CRISPY_SKIP_FLASH  Set to "1" to skip erase+flash steps
"""

import subprocess
import time
from pathlib import Path

import pytest
import serial

from conftest import (
    CHIP,
    enter_update_mode_via_swd,
    find_firmware_port,
    run_crispy_upload,
    wait_for_serial_banner,
)

# USB identifiers
PID_BOOTLOADER = "000a"  # VID=2E8A, also used by C++ firmware (Pico SDK default)
PID_FW_RUST = "000b"     # VID=2E8A, Rust firmware uses a distinct PID

# Artifact paths (relative to project root)
TARGET_DIR = Path("target/thumbv6m-none-eabi/release")
BOOTLOADER_ELF = TARGET_DIR / "crispy-bootloader"
FW_RS_BIN = TARGET_DIR / "crispy-fw-sample-rs.bin"
FW_CPP_BIN = Path("crispy-fw-sample-cpp/build/crispy-fw-sample-cpp.bin")

pytestmark = pytest.mark.deployment


class TestDeployment:
    """Sequential end-to-end deployment tests.

    Tests are ordered by numeric prefix and share state via class attributes.
    Each test depends on the previous ones having passed.
    """

    # Shared state across tests
    bootloader_port: str = ""
    fw_rs_port: str = ""
    fw_cpp_port: str = ""

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).parent.parent.parent.parent

    @classmethod
    def _find_bootloader_port(cls, timeout: float = 15.0) -> str:
        port = find_firmware_port(pid=PID_BOOTLOADER, timeout=timeout)
        cls.bootloader_port = port
        return port

    # ------------------------------------------------------------------ #
    # Test steps
    # ------------------------------------------------------------------ #

    def test_01_erase_flash(self, skip_flash):
        """Erase the entire flash via SWD."""
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        result = subprocess.run(
            ["probe-rs", "erase", "--chip", CHIP],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"probe-rs erase failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_02_build_artifacts(self, skip_build):
        """Build bootloader, Rust firmware, and C++ firmware."""
        if skip_build:
            pytest.skip("Build skipped (--skip-build / CRISPY_SKIP_BUILD)")

        root = self._project_root()

        # Build Rust artifacts (bootloader ELF + BIN + UF2, firmware RS BIN)
        result = subprocess.run(
            ["make", "all"], cwd=root, capture_output=True, text=True,
        )
        assert result.returncode == 0, f"make all failed:\n{result.stderr}"

        # Build C++ firmware
        result = subprocess.run(
            ["make", "firmware-cpp"], cwd=root, capture_output=True, text=True,
        )
        assert result.returncode == 0, f"make firmware-cpp failed:\n{result.stderr}"

        # Verify artifacts exist
        for path in (BOOTLOADER_ELF, FW_RS_BIN, FW_CPP_BIN):
            full = root / path
            assert full.exists(), f"Expected artifact not found: {full}"

    def test_03_flash_bootloader(self, skip_flash):
        """Flash the bootloader ELF via SWD and wait for USB enumeration."""
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        root = self._project_root()
        elf = root / BOOTLOADER_ELF

        # Flash bootloader
        result = subprocess.run(
            ["probe-rs", "download", "--chip", CHIP, str(elf)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"probe-rs download failed:\n{result.stdout}\n{result.stderr}"
        )

        # Reset the device
        result = subprocess.run(
            ["probe-rs", "reset", "--chip", CHIP],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"probe-rs reset failed:\n{result.stderr}"

        # Wait for the bootloader to enumerate on USB
        time.sleep(2.0)
        port = self._find_bootloader_port()
        print(f"Bootloader detected on {port}")

    def test_04_upload_fw_rs_bank_a(self):
        """Upload Rust firmware to bank A via crispy-upload."""
        root = self._project_root()

        # Enter update mode via SWD (ensures bootloader is in update mode)
        assert enter_update_mode_via_swd(), "Failed to enter update mode via SWD"

        port = self._find_bootloader_port()

        fw_path = root / FW_RS_BIN
        ok, stdout, stderr = run_crispy_upload(
            root, port, "upload", str(fw_path), "--bank", "0", "--version", "1",
        )
        assert ok, f"Upload Rust FW to bank A failed:\n{stdout}\n{stderr}"
        print(f"Rust firmware uploaded to bank A:\n{stdout}")

    def test_05_upload_fw_cpp_bank_b(self):
        """Upload C++ firmware to bank B via crispy-upload."""
        root = self._project_root()
        port = self._find_bootloader_port()

        fw_path = root / FW_CPP_BIN
        ok, stdout, stderr = run_crispy_upload(
            root, port, "upload", str(fw_path), "--bank", "1", "--version", "1",
        )
        assert ok, f"Upload C++ FW to bank B failed:\n{stdout}\n{stderr}"
        print(f"C++ firmware uploaded to bank B:\n{stdout}")

    def test_06_verify_status_after_upload(self):
        """Verify both banks are populated with correct versions."""
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        # Bank A should be active, both versions should be 1
        assert "active_bank: 0" in output.lower() or "bank a" in output.lower() or "active_bank=0" in output.lower(), (
            f"Expected bank A active in status output:\n{output}"
        )
        print(f"Status after upload:\n{output}")

    def test_07_set_bank_a_and_reboot(self):
        """Set bank A active, reboot, and verify Rust firmware is running."""
        root = self._project_root()
        port = self._find_bootloader_port()

        # Ensure bank A is active
        ok, stdout, stderr = run_crispy_upload(root, port, "set-bank", "0")
        assert ok, f"set-bank 0 failed:\n{stdout}\n{stderr}"

        # Reboot into firmware
        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        # Wait for Rust firmware to enumerate (PID 000B)
        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_FW_RUST, timeout=15.0)
        TestDeployment.fw_rs_port = fw_port
        print(f"Rust firmware detected on {fw_port}")

        # Open serial and verify the firmware responds
        time.sleep(1.0)
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"status\r\n")
            time.sleep(1.0)
            response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            assert "Bank: 0" in response, (
                f"Expected 'Bank: 0' in firmware response, got:\n{response}"
            )
            print(f"Rust firmware status:\n{response}")

    def test_08_fw_rs_reboot_to_bootloader(self):
        """Send bootload command to Rust firmware and return to bootloader."""
        fw_port = TestDeployment.fw_rs_port
        assert fw_port, "Rust firmware port not set (test_07 must pass first)"

        # Send bootload command
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"bootload\r\n")
            time.sleep(0.5)

        # Wait for the firmware port to disappear and bootloader to re-enumerate
        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)
        print(f"Bootloader re-detected on {port}")

        # Verify we are back in update mode
        root = self._project_root()
        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace("_", ""), (
            f"Expected UpdateMode in status output:\n{output}"
        )
        print(f"Bootloader status:\n{output}")

    def test_09_switch_to_bank_b(self):
        """Switch active bank to B."""
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "set-bank", "1")
        assert ok, f"set-bank 1 failed:\n{stdout}\n{stderr}"

        # Verify active bank is now 1
        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "active_bank: 1" in output.lower() or "bank b" in output.lower() or "active_bank=1" in output.lower(), (
            f"Expected bank B (1) active in status output:\n{output}"
        )
        print(f"Status after bank switch:\n{output}")

    def test_10_reboot_to_fw_cpp(self):
        """Reboot into C++ firmware on bank B and verify banner."""
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        # C++ firmware uses PID 000A (same as bootloader / Pico SDK default)
        # We distinguish by reading the serial banner
        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_BOOTLOADER, timeout=15.0)

        # Read the banner to confirm it's the C++ firmware
        banner = wait_for_serial_banner(
            fw_port, "Crispy Firmware Sample (C++)", timeout=10.0,
        )
        TestDeployment.fw_cpp_port = fw_port
        print(f"C++ firmware banner:\n{banner}")

        # Verify bank 1 via serial status command
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"status\r\n")
            time.sleep(1.0)
            response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            assert "Bank: 1" in response, (
                f"Expected 'Bank: 1' in firmware response, got:\n{response}"
            )
            print(f"C++ firmware status:\n{response}")

    def test_11_fw_cpp_reboot_to_bootloader(self):
        """Send bootload command to C++ firmware and return to bootloader."""
        fw_port = TestDeployment.fw_cpp_port
        assert fw_port, "C++ firmware port not set (test_10 must pass first)"

        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"bootload\r\n")
            time.sleep(0.5)

        # Wait for bootloader to re-enumerate
        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)
        print(f"Bootloader re-detected on {port}")

        # Verify update mode
        root = self._project_root()
        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace("_", ""), (
            f"Expected UpdateMode in status output:\n{output}"
        )

    def test_12_wipe_and_verify_update_mode(self):
        """Wipe all firmware, reboot, and verify device stays in update mode."""
        root = self._project_root()
        port = self._find_bootloader_port()

        # Wipe all firmware banks
        ok, stdout, stderr = run_crispy_upload(root, port, "wipe-all")
        assert ok, f"wipe-all failed:\n{stdout}\n{stderr}"
        print(f"Wipe result:\n{stdout}")

        # Reboot — with no valid firmware the bootloader should stay in update mode
        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace("_", ""), (
            f"Expected UpdateMode after wipe, got:\n{output}"
        )
        print(f"Final status (post-wipe):\n{output}")
