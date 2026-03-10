# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
End-to-end deployment test for the Crispy Bootloader.

Validates the full lifecycle:
    erase -> flash bootloader -> upload firmwares (Rust + C++)
    -> boot -> bank switching -> wipe.

Usage:
    cd tests/integration && uv run pytest boot/deployment/ -v --tb=short
"""

import time
from pathlib import Path

import pytest
import serial

from crispy_board import (
    EMBEDDED_TARGET,
    PID_BOOTLOADER,
    PID_FW_RUST,
    enter_update_mode_via_swd,
    erase_boot_data,
    find_firmware_port,
    flash_uf2,
    project_root_from,
    run_crispy_upload,
    run_make,
)

TARGET_DIR = Path(f"target/{EMBEDDED_TARGET}/release")
BOOTLOADER_ELF = TARGET_DIR / "crispy-bootloader"
BOOTLOADER_UF2 = TARGET_DIR / "crispy-bootloader.uf2"
FW_RS_BIN = TARGET_DIR / "crispy-fw-sample-rs.bin"
FW_CPP_BIN = Path("crispy-fw-sample-cpp/build/crispy-fw-sample-cpp.bin")

pytestmark = pytest.mark.deployment


class TestDeployment:
    """Sequential end-to-end deployment tests (ordered by numeric prefix)."""

    bootloader_port: str = ""
    fw_rs_port: str = ""
    fw_cpp_port: str = ""

    @staticmethod
    def _project_root() -> Path:
        return project_root_from(__file__)

    @classmethod
    def _find_bootloader_port(cls, timeout: float = 15.0) -> str:
        port = find_firmware_port(pid=PID_BOOTLOADER, timeout=timeout)
        cls.bootloader_port = port
        return port

    def test_01_erase_flash(self, skip_flash):
        """Erase boot data sector to start from a clean state."""
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        assert erase_boot_data(), "Failed to erase boot data via SWD"

    def test_02_build_artifacts(self, skip_build):
        if skip_build:
            pytest.skip("Build skipped (--skip-build / CRISPY_SKIP_BUILD)")

        root = self._project_root()

        result = run_make(
            root, "bootloader-uf2", "firmware-bin", "firmware-cpp", "upload",
        )
        assert result.returncode == 0, f"make failed:\n{result.stderr}"

        for path in (BOOTLOADER_ELF, FW_RS_BIN, FW_CPP_BIN):
            full = root / path
            assert full.exists(), f"Expected artifact not found: {full}"

    def test_03_flash_bootloader_uf2(self, skip_flash):
        """Flash bootloader UF2 via BOOTSEL and enter update mode."""
        if skip_flash:
            pytest.skip("Flash skipped (--skip-flash / CRISPY_SKIP_FLASH)")

        root = self._project_root()
        uf2 = root / BOOTLOADER_UF2

        assert uf2.exists(), f"UF2 not found: {uf2}\nRun 'make bootloader-uf2' first."
        assert flash_uf2(uf2), "Failed to flash bootloader via UF2"
        assert enter_update_mode_via_swd(), "Failed to enter update mode via SWD"

        port = self._find_bootloader_port()
        print(f"Bootloader detected on {port}")

    def test_04_upload_fw_rs_bank_a(self):
        root = self._project_root()

        assert enter_update_mode_via_swd(), "Failed to enter update mode via SWD"

        port = self._find_bootloader_port()

        fw_path = root / FW_RS_BIN
        ok, stdout, stderr = run_crispy_upload(
            root, port, "upload", str(fw_path), "--bank", "0", "--version", "1",
        )
        assert ok, f"Upload Rust FW to bank A failed:\n{stdout}\n{stderr}"

    def test_05_upload_fw_cpp_bank_b(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        fw_path = root / FW_CPP_BIN
        ok, stdout, stderr = run_crispy_upload(
            root, port, "upload", str(fw_path), "--bank", "1", "--version", "1",
        )
        assert ok, f"Upload C++ FW to bank B failed:\n{stdout}\n{stderr}"

    def test_06_verify_status_after_upload(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        low = output.lower()

        expected_version = (root / "VERSION").read_text().strip()
        expected_line = f"bootloader:  {expected_version}"
        assert expected_line in low, f"Expected '{expected_line}' in:\n{output}"

        assert "version a:   1" in low, f"Expected Version A = 1 in:\n{output}"
        assert "version b:   1" in low, f"Expected Version B = 1 in:\n{output}"

    def test_07_set_bank_a_and_reboot(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "set-bank", "0")
        assert ok, f"set-bank 0 failed:\n{stdout}\n{stderr}"

        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_FW_RUST, timeout=15.0)
        TestDeployment.fw_rs_port = fw_port

        time.sleep(1.0)
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.reset_input_buffer()
            # Sync prompt then send command
            ser.write(b"\r\n")
            time.sleep(0.5)
            ser.reset_input_buffer()
            ser.write(b"status\r\n")
            time.sleep(1.0)
            response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            assert "Bank: 0" in response, f"Expected 'Bank: 0', got:\n{response}"

    def test_08_fw_rs_reboot_to_bootloader(self):
        fw_port = TestDeployment.fw_rs_port
        assert fw_port, "Rust firmware port not set (test_07 must pass first)"

        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"bootload\r\n")
            time.sleep(0.5)

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)

        root = self._project_root()
        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace(
            "_", ""
        ), f"Expected UpdateMode in:\n{output}"

    def test_09_switch_to_bank_b(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "set-bank", "1")
        assert ok, f"set-bank 1 failed:\n{stdout}\n{stderr}"

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "active bank: 1" in output.lower(), f"Expected bank B active in:\n{output}"

    def test_10_reboot_to_fw_cpp(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        # C++ firmware uses PID 000A (same as bootloader / Pico SDK default)
        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_BOOTLOADER, timeout=15.0)
        TestDeployment.fw_cpp_port = fw_port

        time.sleep(1.0)
        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.reset_input_buffer()
            ser.write(b"\r\n")
            time.sleep(0.5)
            ser.reset_input_buffer()

            ser.write(b"version\r\n")
            time.sleep(1.0)
            version_response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            expected_version = (root / "VERSION").read_text().strip()
            assert f"Version: {expected_version}" in version_response, (
                f"Expected 'Version: {expected_version}' in:\n{version_response}"
            )

            ser.write(b"status\r\n")
            time.sleep(1.0)
            status_response = ser.read(ser.in_waiting or 256).decode(errors="replace")
            assert "Bank: 1" in status_response, f"Expected 'Bank: 1', got:\n{status_response}"

    def test_11_fw_cpp_reboot_to_bootloader(self):
        fw_port = TestDeployment.fw_cpp_port
        assert fw_port, "C++ firmware port not set (test_10 must pass first)"

        with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
            ser.write(b"bootload\r\n")
            time.sleep(0.5)

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)

        root = self._project_root()
        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace(
            "_", ""
        ), f"Expected UpdateMode in:\n{output}"

    def test_12_wipe_and_verify_update_mode(self):
        root = self._project_root()
        port = self._find_bootloader_port()

        ok, stdout, stderr = run_crispy_upload(root, port, "wipe")
        assert ok, f"wipe failed:\n{stdout}\n{stderr}"

        ok, stdout, stderr = run_crispy_upload(root, port, "reboot")
        assert ok, f"reboot failed:\n{stdout}\n{stderr}"

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)

        time.sleep(1.0)

        ok, stdout, stderr = run_crispy_upload(root, port, "status")
        assert ok, f"Status command failed:\n{stdout}\n{stderr}"

        output = stdout + stderr
        assert "updatemode" in output.lower().replace(" ", "").replace(
            "_", ""
        ), f"Expected UpdateMode after wipe, got:\n{output}"
