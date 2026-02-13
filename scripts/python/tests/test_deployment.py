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

from tests.conftest import (
    CHIP,
    enter_update_mode_via_swd,
    find_firmware_port,
    flash_uf2,
    run_crispy_upload,
    wait_for_serial_banner,
)

# USB identifiers
PID_BOOTLOADER = "000a"  # VID=2E8A, also used by C++ firmware (Pico SDK default)
PID_FW_RUST = "000b"     # VID=2E8A, Rust firmware uses a distinct PID

# Artifact paths (relative to project root)
TARGET_DIR = Path("target/thumbv6m-none-eabi/release")
BOOTLOADER_ELF = TARGET_DIR / "crispy-bootloader"
BOOTLOADER_UF2 = TARGET_DIR / "crispy-bootloader.uf2"
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
        """Erase boot data via SWD to start from a clean state.

        Instead of erasing the full 2MB flash (which can hang on some
        RP2040 setups), we only wipe the BootData sector at 0x10190000.
        The bootloader area is overwritten in test_03 anyway.
        """
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        import tempfile

        # Write a 4KB sector of 0xFF (erased flash) to invalidate BootData
        boot_data_addr = 0x1019_0000
        sector = b"\xFF" * 4096
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(sector)
            blank_path = f.name

        try:
            result = subprocess.run(
                [
                    "probe-rs", "download", "--chip", CHIP,
                    "--binary-format", "bin",
                    "--base-address", hex(boot_data_addr),
                    blank_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            assert result.returncode == 0, (
                f"probe-rs erase boot data failed:\n{result.stdout}\n{result.stderr}"
            )
        finally:
            Path(blank_path).unlink(missing_ok=True)

    def test_02_build_artifacts(self, skip_build):
        """Build bootloader, Rust firmware, and C++ firmware."""
        if skip_build:
            pytest.skip("Build skipped (--skip-build / CRISPY_SKIP_BUILD)")

        root = self._project_root()

        # Build Rust artifacts (bootloader ELF + BIN + UF2, firmware RS BIN)
        result = subprocess.run(
            ["make", "all"], cwd=root, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"make all failed:\n{result.stderr}"

        # Build C++ firmware
        result = subprocess.run(
            ["make", "firmware-cpp"], cwd=root, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"make firmware-cpp failed:\n{result.stderr}"

        # Verify artifacts exist
        for path in (BOOTLOADER_ELF, FW_RS_BIN, FW_CPP_BIN):
            full = root / path
            assert full.exists(), f"Expected artifact not found: {full}"

    def test_03_flash_bootloader_uf2(self, skip_flash):
        """Flash the bootloader UF2 via BOOTSEL mode and wait for USB enumeration.

        Validates the user-facing UF2 flashing workflow:
        invalidate boot2 → BOOTSEL → copy UF2 → reboot → bootloader running.
        """
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        root = self._project_root()
        uf2 = root / BOOTLOADER_UF2

        assert uf2.exists(), (
            f"UF2 not found: {uf2}\n"
            "Run 'make bootloader-uf2' first."
        )

        # Flash via UF2 (force BOOTSEL → copy UF2 → device reboots)
        assert flash_uf2(uf2), "Failed to flash bootloader via UF2"

        # After reboot the bootloader finds no valid boot data (erased in
        # test_01) and enters update mode automatically.  Belt-and-suspenders:
        # re-erase boot data + write RAM magic to guarantee update mode.
        assert enter_update_mode_via_swd(), "Failed to enter update mode via SWD"

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
        low = output.lower()
        # Both banks should have version 1
        assert "version a:   1" in low, (
            f"Expected Version A = 1 in status output:\n{output}"
        )
        assert "version b:   1" in low, (
            f"Expected Version B = 1 in status output:\n{output}"
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
            # Flush any pending data (welcome banner)
            ser.reset_input_buffer()
            # Send empty line to sync prompt, then the real command
            ser.write(b"\r\n")
            time.sleep(0.5)
            ser.reset_input_buffer()
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
        assert "active bank: 1" in output.lower(), (
            f"Expected bank B (1) active in status output:\n{output}"
        )
        print(f"Status after bank switch:\n{output}")

    def test_10_reboot_to_fw_cpp(self):
        """Reboot into C++ firmware on bank B and verify via serial."""
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        # C++ firmware uses PID 000A (same as bootloader / Pico SDK default)
        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_BOOTLOADER, timeout=15.0)
        TestDeployment.fw_cpp_port = fw_port

        # The banner may have already been sent before we opened the port.
        # Send a newline + status command to identify the C++ firmware.
        time.sleep(1.0)
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            # Flush any pending data (may contain the banner)
            time.sleep(0.5)
            pending = ser.read(ser.in_waiting or 1)
            banner = pending.decode(errors="replace")

            # Send status command
            ser.write(b"status\r\n")
            time.sleep(1.0)
            response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            full_output = banner + response

            # Verify it's the C++ firmware on bank 1
            assert "Bank: 1" in response, (
                f"Expected 'Bank: 1' in firmware response, got:\n{full_output}"
            )
            print(f"C++ firmware output:\n{full_output}")

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
        ok, stdout, stderr = run_crispy_upload(root, port, "wipe")
        assert ok, f"wipe failed:\n{stdout}\n{stderr}"
        print(f"Wipe result:\n{stdout}")

        # Reboot — with no valid firmware the bootloader should stay in update mode
        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)

        # Wait for CDC to be ready after USB enumeration
        time.sleep(1.0)

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace("_", ""), (
            f"Expected UpdateMode after wipe, got:\n{output}"
        )
        print(f"Final status (post-wipe):\n{output}")
