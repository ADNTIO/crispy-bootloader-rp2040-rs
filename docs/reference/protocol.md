# Protocol Reference

Transport protocol between host tools and bootloader.

## Encoding

- Framing: COBS with `0x00` packet delimiter
- Serialization: `postcard` (serde)
- Max data payload per `DataBlock`: `1024` bytes

## Commands

Defined in `crispy-common/src/protocol.rs`.

- `GetStatus`
- `StartUpdate { bank, size, crc32, version }`
- `DataBlock { offset, data }`
- `FinishUpdate`
- `SetActiveBank { bank }`
- `WipeAll`
- `Reboot`

## Responses

- `Ack(AckStatus)`
- `Status { active_bank, version_a, version_b, state }`

## AckStatus

- `Ok`
- `CrcError`
- `FlashError`
- `BadCommand`
- `BadState`
- `BankInvalid`

## BootState

- `Idle`
- `UpdateMode`
- `Receiving`
