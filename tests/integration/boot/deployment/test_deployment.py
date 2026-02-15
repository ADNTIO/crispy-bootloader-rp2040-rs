# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
End-to-end deployment test for the Crispy Bootloader.

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
BOOTLOADER_UF2 = TARGET_DIR / "crispy-bootloader.uf2"
FW_RS_BIN = TARGET_DIR / "crispy-fw-sample-rs.bin"
FW_CPP_BIN = Path("crispy-fw-sample-cpp/build/crispy-fw-sample-cpp.bin")

pytestmark = pytest.mark.deployment


def _root():
    return project_root_from(__file__)


def _upload(port, *args):
    ok, stdout, stderr = run_crispy_upload(_root(), port, *args)
    assert ok, f"{args[0]} failed:\n{stdout}\n{stderr}"
    return stdout + stderr


def _assert_update_mode(output):
    assert "updatemode" in output.lower().replace(" ", "").replace("_", ""), (
        f"Expected UpdateMode in:\n{output}"
    )


def _serial_command(port, command, read_delay=1.0):
    with serial.Serial(port, baudrate=115200, timeout=3) as ser:
        ser.reset_input_buffer()
        ser.write(b"\r\n")
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.write(command.encode() + b"\r\n")
        time.sleep(read_delay)
        return ser.read(ser.in_waiting or 256).decode(errors="replace")


def _reboot_to_bootloader(fw_port):
    with serial.Serial(fw_port, baudrate=115200, timeout=3) as ser:
        ser.write(b"bootload\r\n")
        time.sleep(0.5)
    time.sleep(3.0)
    return find_firmware_port(pid=PID_BOOTLOADER, timeout=15.0)


class TestDeployment:

    bootloader_port: str = ""
    fw_rs_port: str = ""
    fw_cpp_port: str = ""

    @classmethod
    def _find_bootloader_port(cls, timeout: float = 15.0) -> str:
        cls.bootloader_port = find_firmware_port(pid=PID_BOOTLOADER, timeout=timeout)
        return cls.bootloader_port

    def test_01_erase_flash(self, skip_flash):
        if skip_flash:
            pytest.skip("Flash skipped")
        assert erase_boot_data(), "Failed to erase boot data via SWD"

    def test_02_build_artifacts(self, skip_build):
        if skip_build:
            pytest.skip("Build skipped")

        root = _root()
        result = run_make(root, "bootloader-uf2", "firmware-bin", "firmware-cpp", "upload")
        assert result.returncode == 0, f"make failed:\n{result.stderr}"

        for path in (TARGET_DIR / "crispy-bootloader", FW_RS_BIN, FW_CPP_BIN):
            assert (root / path).exists(), f"Artifact not found: {root / path}"

    def test_03_flash_bootloader_uf2(self, skip_flash):
        if skip_flash:
            pytest.skip("Flash skipped")

        uf2 = _root() / BOOTLOADER_UF2
        assert uf2.exists(), f"UF2 not found: {uf2}"
        assert flash_uf2(uf2), "Failed to flash bootloader via UF2"
        assert enter_update_mode_via_swd(), "Failed to enter update mode"
        print(f"Bootloader detected on {self._find_bootloader_port()}")

    def test_04_upload_fw_rs_bank_a(self):
        assert enter_update_mode_via_swd(), "Failed to enter update mode"
        port = self._find_bootloader_port()
        _upload(port, "upload", str(_root() / FW_RS_BIN), "--bank", "0", "--version", "1")

    def test_05_upload_fw_cpp_bank_b(self):
        port = self._find_bootloader_port()
        _upload(port, "upload", str(_root() / FW_CPP_BIN), "--bank", "1", "--version", "1")

    def test_06_verify_status_after_upload(self):
        port = self._find_bootloader_port()
        output = _upload(port, "status")
        low = output.lower()

        expected_version = (_root() / "VERSION").read_text().strip()
        assert f"bootloader:  {expected_version}" in low, f"Expected version in:\n{output}"
        assert "version a:   1" in low, f"Expected Version A = 1 in:\n{output}"
        assert "version b:   1" in low, f"Expected Version B = 1 in:\n{output}"

    def test_07_set_bank_a_and_reboot(self):
        port = self._find_bootloader_port()
        _upload(port, "set-bank", "0")
        _upload(port, "reboot")

        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_FW_RUST, timeout=15.0)
        TestDeployment.fw_rs_port = fw_port

        time.sleep(1.0)
        response = _serial_command(fw_port, "status")
        assert "Bank: 0" in response, f"Expected 'Bank: 0', got:\n{response}"

    def test_08_fw_rs_reboot_to_bootloader(self):
        assert TestDeployment.fw_rs_port, "Rust firmware port not set"
        port = _reboot_to_bootloader(TestDeployment.fw_rs_port)
        _assert_update_mode(_upload(port, "status"))

    def test_09_switch_to_bank_b(self):
        port = self._find_bootloader_port()
        _upload(port, "set-bank", "1")
        output = _upload(port, "status")
        assert "active bank: 1" in output.lower(), f"Expected bank B active in:\n{output}"

    def test_10_reboot_to_fw_cpp(self):
        port = self._find_bootloader_port()
        _upload(port, "reboot")

        time.sleep(3.0)
        fw_port = find_firmware_port(pid=PID_BOOTLOADER, timeout=15.0)
        TestDeployment.fw_cpp_port = fw_port

        time.sleep(1.0)
        expected_version = (_root() / "VERSION").read_text().strip()
        version_response = _serial_command(fw_port, "version")
        assert f"Version: {expected_version}" in version_response, (
            f"Expected 'Version: {expected_version}' in:\n{version_response}"
        )

        status_response = _serial_command(fw_port, "status")
        assert "Bank: 1" in status_response, f"Expected 'Bank: 1', got:\n{status_response}"

    def test_11_fw_cpp_reboot_to_bootloader(self):
        assert TestDeployment.fw_cpp_port, "C++ firmware port not set"
        port = _reboot_to_bootloader(TestDeployment.fw_cpp_port)
        _assert_update_mode(_upload(port, "status"))

    def test_12_wipe_and_verify_update_mode(self):
        port = self._find_bootloader_port()
        _upload(port, "wipe")
        _upload(port, "reboot")

        time.sleep(3.0)
        port = self._find_bootloader_port(timeout=15.0)
        time.sleep(1.0)
        _assert_update_mode(_upload(port, "status"))
