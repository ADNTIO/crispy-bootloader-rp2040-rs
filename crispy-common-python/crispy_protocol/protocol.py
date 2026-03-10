# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union

from .cobs import cobs_encode, cobs_decode
from .varint import encode_varint, decode_varint


class CommandType(IntEnum):
    GET_STATUS = 0
    START_UPDATE = 1
    DATA_BLOCK = 2
    FINISH_UPDATE = 3
    REBOOT = 4
    SET_ACTIVE_BANK = 5
    WIPE_ALL = 6


class Command:
    @staticmethod
    def get_status() -> bytes:
        return encode_get_status()

    @staticmethod
    def start_update(bank: int, size: int, crc32: int, version: int) -> bytes:
        return encode_start_update(bank, size, crc32, version)

    @staticmethod
    def data_block(offset: int, data: bytes) -> bytes:
        return encode_data_block(offset, data)

    @staticmethod
    def finish_update() -> bytes:
        return encode_finish_update()

    @staticmethod
    def reboot() -> bytes:
        return encode_reboot()

    @staticmethod
    def set_active_bank(bank: int) -> bytes:
        return encode_set_active_bank(bank)

    @staticmethod
    def wipe_all() -> bytes:
        return encode_wipe_all()


class AckStatus(IntEnum):
    OK = 0
    CRC_ERROR = 1
    FLASH_ERROR = 2
    BAD_COMMAND = 3
    BAD_STATE = 4
    BANK_INVALID = 5

    def __str__(self) -> str:
        return self.name


class BootState(IntEnum):
    IDLE = 0
    UPDATE_MODE = 1
    RECEIVING = 2

    def __str__(self) -> str:
        return self.name


class Response:
    TYPE_ACK = 0
    TYPE_STATUS = 1


@dataclass
class AckResponse:
    status: AckStatus
    type: int = Response.TYPE_ACK

    @property
    def is_ok(self) -> bool:
        return self.status == AckStatus.OK


@dataclass
class StatusResponse:
    active_bank: int
    version_a: int
    version_b: int
    state: BootState
    bootloader_version: Optional[int] = None
    type: int = Response.TYPE_STATUS

    @property
    def active_bank_name(self) -> str:
        return "A" if self.active_bank == 0 else "B"


ResponseType = Union[AckResponse, StatusResponse]


def _frame(data: bytes) -> bytes:
    return cobs_encode(data) + b'\x00'


def _simple_command(cmd: CommandType) -> bytes:
    return _frame(bytes([cmd]))


def encode_get_status() -> bytes:
    return _simple_command(CommandType.GET_STATUS)


def encode_start_update(bank: int, size: int, crc32: int, version: int) -> bytes:
    payload = (
        bytes([CommandType.START_UPDATE, bank])
        + encode_varint(size)
        + encode_varint(crc32)
        + encode_varint(version)
    )
    return _frame(payload)


def encode_data_block(offset: int, data: bytes) -> bytes:
    payload = (
        bytes([CommandType.DATA_BLOCK])
        + encode_varint(offset)
        + encode_varint(len(data))
        + data
    )
    return _frame(payload)


def encode_finish_update() -> bytes:
    return _simple_command(CommandType.FINISH_UPDATE)


def encode_reboot() -> bytes:
    return _simple_command(CommandType.REBOOT)


def encode_set_active_bank(bank: int) -> bytes:
    return _frame(bytes([CommandType.SET_ACTIVE_BANK, bank]))


def encode_wipe_all() -> bytes:
    return _simple_command(CommandType.WIPE_ALL)


def decode_response(data: bytes) -> ResponseType:
    if data and data[-1] == 0:
        data = data[:-1]

    decoded = cobs_decode(data)

    if len(decoded) < 1:
        raise ValueError("Empty response")

    resp_type = decoded[0]

    if resp_type == Response.TYPE_ACK:
        if len(decoded) < 2:
            raise ValueError("Truncated Ack response")
        return AckResponse(status=AckStatus(decoded[1]))

    elif resp_type == Response.TYPE_STATUS:
        if len(decoded) < 2:
            raise ValueError("Truncated Status response")

        active_bank = decoded[1]
        offset = 2
        version_a, offset = decode_varint(decoded, offset)
        version_b, offset = decode_varint(decoded, offset)

        if offset >= len(decoded):
            raise ValueError("Truncated Status response")
        state = BootState(decoded[offset])
        offset += 1

        bootloader_version = None
        if offset < len(decoded):
            bootloader_version, offset = decode_varint(decoded, offset)

        return StatusResponse(
            active_bank=active_bank,
            version_a=version_a,
            version_b=version_b,
            state=state,
            bootloader_version=bootloader_version,
        )

    else:
        raise ValueError(f"Unknown response type: {resp_type}")
