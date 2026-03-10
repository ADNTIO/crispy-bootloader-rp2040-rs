# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

from crispy_protocol.crc32 import crc32
from crispy_protocol.protocol import AckStatus, Command


def upload_firmware(transport, firmware_data: bytes, bank: int, version: int,
                    chunk_size: int = 1024) -> None:
    """Send StartUpdate + all DataBlock chunks + FinishUpdate, asserting OK on each."""
    size = len(firmware_data)
    checksum = crc32(firmware_data)

    transport.send(Command.start_update(
        bank=bank, size=size, crc32=checksum, version=version,
    ))
    resp = transport.receive()
    assert resp.status == AckStatus.OK, f"StartUpdate failed: {resp.status}"

    offset = 0
    while offset < size:
        chunk = firmware_data[offset:offset + chunk_size]
        transport.send(Command.data_block(offset=offset, data=chunk))
        resp = transport.receive()
        assert resp.status == AckStatus.OK, (
            f"DataBlock failed at offset {offset}: {resp.status}"
        )
        offset += len(chunk)

    transport.send(Command.finish_update())
    resp = transport.receive()
    assert resp.status == AckStatus.OK, f"FinishUpdate failed: {resp.status}"
