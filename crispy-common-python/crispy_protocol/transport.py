# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import time
from pathlib import Path
from typing import Callable, Optional

import serial

from .crc32 import crc32
from .protocol import (
    ResponseType,
    AckResponse,
    StatusResponse,
    AckStatus,
    decode_response,
    encode_get_status,
    encode_start_update,
    encode_data_block,
    encode_finish_update,
    encode_reboot,
)


class TransportError(Exception):
    pass


class TimeoutError(TransportError):
    pass


class ProtocolError(TransportError):
    pass


class UploadError(TransportError):
    pass


class Transport:
    """USB CDC transport for crispy bootloader.

    Can be used as a context manager:
        with Transport("/dev/ttyACM0") as t:
            status = t.get_status()
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 5.0):
        self._ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()

    @property
    def port(self) -> str:
        return self._ser.port

    def _send(self, data: bytes):
        self._ser.write(data)
        self._ser.flush()

    def _receive(self) -> bytes:
        result = bytearray()
        while True:
            byte = self._ser.read(1)
            if not byte:
                raise TimeoutError("Timeout waiting for response")
            result.append(byte[0])
            if byte[0] == 0:
                break
        return bytes(result)

    def _send_recv(self, data: bytes) -> ResponseType:
        self._send(data)
        return decode_response(self._receive())

    def _expect(self, data: bytes, expected_type: type):
        resp = self._send_recv(data)
        if not isinstance(resp, expected_type):
            raise ProtocolError(
                f"Expected {expected_type.__name__}, got {type(resp).__name__}"
            )
        return resp

    def send(self, data: bytes) -> None:
        self._send(data)

    def receive(self) -> ResponseType:
        return decode_response(self._receive())

    def get_status(self) -> StatusResponse:
        return self._expect(encode_get_status(), StatusResponse)

    def start_update(self, bank: int, size: int, crc: int, version: int) -> AckResponse:
        return self._expect(encode_start_update(bank, size, crc, version), AckResponse)

    def send_data_block(self, offset: int, data: bytes) -> AckResponse:
        return self._expect(encode_data_block(offset, data), AckResponse)

    def finish_update(self) -> AckResponse:
        return self._expect(encode_finish_update(), AckResponse)

    def reboot(self) -> AckResponse:
        return self._expect(encode_reboot(), AckResponse)

    def upload_firmware(
        self,
        firmware: bytes,
        bank: int,
        version: int,
        chunk_size: int = 1024,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        size = len(firmware)
        checksum = crc32(firmware)

        resp = self.start_update(bank, size, checksum, version)
        if not resp.is_ok:
            raise UploadError(f"StartUpdate failed: {resp.status}")

        offset = 0
        while offset < size:
            chunk = firmware[offset:offset + chunk_size]
            resp = self.send_data_block(offset, chunk)

            if not resp.is_ok:
                raise UploadError(f"DataBlock failed at offset {offset}: {resp.status}")

            offset += len(chunk)

            if progress_callback:
                progress_callback(offset, size)

        resp = self.finish_update()
        if not resp.is_ok:
            if resp.status == AckStatus.CRC_ERROR:
                raise UploadError("CRC verification failed")
            raise UploadError(f"FinishUpdate failed: {resp.status}")

    def upload_firmware_file(
        self,
        path: Path,
        bank: int,
        version: int,
        chunk_size: int = 1024,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        """Upload firmware from file. Returns CRC-32 of uploaded data."""
        firmware = Path(path).read_bytes()
        self.upload_firmware(firmware, bank, version, chunk_size, progress_callback)
        return crc32(firmware)
