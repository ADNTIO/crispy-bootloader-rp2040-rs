# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
Integration tests for crispy-bootloader protocol.

Run with: cd tests/integration && uv run pytest boot/bootsequence/ -v --device /dev/ttyACM0
"""

import time

import pytest

from crispy_board import (
    EMBEDDED_TARGET,
    build_packages,
    objcopy,
    upload_firmware,
)

pytestmark = pytest.mark.integration


class TestBuildArtifacts:

    def test_build_bootloader(self, project_root, skip_build):
        if skip_build:
            pytest.skip("Build skipped")

        result = build_packages(project_root, ["crispy-bootloader"])
        assert result.returncode == 0, f"Build failed: {result.stderr}"

    def test_build_firmware(self, project_root, skip_build):
        if skip_build:
            pytest.skip("Build skipped")

        result = build_packages(project_root, ["crispy-fw-sample-rs"])
        assert result.returncode == 0, f"Build failed: {result.stderr}"

    def test_create_firmware_binary(self, project_root, skip_build):
        if skip_build:
            pytest.skip("Build skipped")

        elf_path = (
            project_root
            / "target"
            / EMBEDDED_TARGET
            / "release"
            / "crispy-fw-sample-rs"
        )
        bin_path = project_root / "target" / "firmware.bin"

        result = objcopy(elf_path, bin_path)
        assert result.returncode == 0, f"rust-objcopy failed: {result.stderr}"
        assert bin_path.exists(), "Firmware binary not created"

    def test_firmware_size(self, project_root):
        bin_path = project_root / "target" / "firmware.bin"
        if not bin_path.exists():
            pytest.skip("Firmware binary not found")

        max_size = 768 * 1024
        actual_size = bin_path.stat().st_size

        assert actual_size < max_size, f"Firmware too large: {actual_size} > {max_size}"
        print(f"Firmware size: {actual_size} bytes ({actual_size / 1024:.1f} KB)")


class TestBootloaderStatus:

    def test_get_status(self, transport):
        from crispy_protocol.protocol import Command, Response

        transport.send(Command.get_status())

        response = transport.receive()
        assert response is not None, "No response received"
        assert response.type == Response.TYPE_STATUS, f"Expected Status, got {response}"

        print(f"Active bank: {response.active_bank}")
        print(f"Version A: {response.version_a}")
        print(f"Version B: {response.version_b}")
        print(f"State: {response.state}")

    def test_status_shows_update_mode(self, transport):
        from crispy_protocol.protocol import BootState, Command

        transport.send(Command.get_status())
        response = transport.receive()

        assert response.state in (
            BootState.UPDATE_MODE,
            BootState.RECEIVING,
        ), f"Expected UpdateMode or Receiving, got {response.state}"


class TestFirmwareUpload:

    @pytest.fixture
    def firmware_path(self, project_root):
        path = project_root / "target" / "firmware.bin"
        if not path.exists():
            pytest.skip("Firmware binary not found. Run build tests first.")
        return path

    @pytest.fixture
    def firmware_data(self, firmware_path):
        return firmware_path.read_bytes()

    def test_start_update_bank_a(self, transport, firmware_data):
        from crispy_protocol.crc32 import crc32
        from crispy_protocol.protocol import AckStatus, Command, Response

        size = len(firmware_data)
        checksum = crc32(firmware_data)

        transport.send(Command.start_update(bank=0, size=size, crc32=checksum, version=1))

        response = transport.receive()
        assert response is not None, "No response received"
        assert response.type == Response.TYPE_ACK, f"Expected Ack, got {response}"
        assert response.status == AckStatus.OK, f"Expected OK, got {response.status}"

    def test_upload_data_blocks(self, transport, firmware_data):
        upload_firmware(transport, firmware_data, bank=0, version=2)
        print(f"Uploaded {len(firmware_data)} bytes")

    def test_finish_update(self, transport, firmware_data):
        upload_firmware(transport, firmware_data, bank=0, version=3)

    def test_status_after_upload(self, transport, firmware_data):
        from crispy_protocol.protocol import Command

        version = 42
        upload_firmware(transport, firmware_data, bank=0, version=version)

        transport.send(Command.get_status())
        response = transport.receive()

        assert response.active_bank == 0, f"Expected bank 0, got {response.active_bank}"
        assert response.version_a == version, f"Expected version {version}, got {response.version_a}"


class TestBankSwitching:

    @pytest.fixture
    def firmware_data(self, project_root):
        path = project_root / "target" / "firmware.bin"
        if not path.exists():
            pytest.skip("Firmware binary not found")
        return path.read_bytes()

    def test_upload_to_bank_b(self, transport, firmware_data):
        from crispy_protocol.protocol import Command

        version = 100
        upload_firmware(transport, firmware_data, bank=1, version=version)

        transport.send(Command.get_status())
        response = transport.receive()

        assert response.active_bank == 1, f"Expected bank 1, got {response.active_bank}"
        assert response.version_b == version, f"Expected version {version}, got {response.version_b}"


class TestErrorHandling:

    def test_invalid_bank(self, transport):
        from crispy_protocol.protocol import AckStatus, Command

        transport.send(Command.start_update(bank=2, size=1024, crc32=0, version=1))
        response = transport.receive()

        assert response.status == AckStatus.BANK_INVALID

    def test_zero_size(self, transport):
        from crispy_protocol.protocol import AckStatus, Command

        transport.send(Command.start_update(bank=0, size=0, crc32=0, version=1))
        response = transport.receive()

        assert response.status == AckStatus.BANK_INVALID

    def test_data_block_without_start(self, transport):
        from crispy_protocol.protocol import AckStatus, Command

        # Ensure idle state
        transport.send(Command.get_status())
        transport.receive()

        transport.send(Command.data_block(offset=0, data=b"\x00" * 256))
        response = transport.receive()

        assert response.status == AckStatus.BAD_STATE

    def test_wrong_offset(self, transport):
        from crispy_protocol.crc32 import crc32
        from crispy_protocol.protocol import AckStatus, Command

        data = b"\x00" * 2048
        transport.send(Command.start_update(bank=0, size=len(data), crc32=crc32(data), version=1))
        assert transport.receive().status == AckStatus.OK

        transport.send(Command.data_block(offset=0, data=data[:1024]))
        assert transport.receive().status == AckStatus.OK

        # Wrong offset: should be 1024
        transport.send(Command.data_block(offset=512, data=data[1024:]))
        response = transport.receive()

        assert response.status == AckStatus.BAD_COMMAND

    def test_crc_mismatch(self, transport):
        from crispy_protocol.protocol import AckStatus, Command

        data = b"\x00" * 1024
        wrong_crc = 0xDEADBEEF

        transport.send(Command.start_update(bank=0, size=len(data), crc32=wrong_crc, version=1))
        assert transport.receive().status == AckStatus.OK

        transport.send(Command.data_block(offset=0, data=data))
        assert transport.receive().status == AckStatus.OK

        transport.send(Command.finish_update())
        response = transport.receive()

        assert response.status == AckStatus.CRC_ERROR


class TestReboot:

    def test_reboot_command(self, transport):
        from crispy_protocol.protocol import AckStatus, Command

        transport.send(Command.reboot())
        response = transport.receive()

        assert response.status == AckStatus.OK

        time.sleep(2)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--device", "/dev/ttyACM0"])
