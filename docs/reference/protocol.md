# Protocol Reference

Transport protocol between host tools and bootloader.

## Encoding

- Framing: COBS with `0x00` packet delimiter
- Serialization: `postcard` (serde)
- Max data payload per `DataBlock`: `1024` bytes

## Commands

Defined in `crispy-common-rs/src/protocol.rs`.

- `GetStatus`
- `StartUpdate { bank, size, crc32, version }`
- `DataBlock { offset, data }`
- `FinishUpdate`
- `SetActiveBank { bank }`
- `WipeAll`
- `Reboot`

## Responses

- `Ack(AckStatus)`
- `Status { active_bank, version_a, version_b, state, bootloader_version? }`

`bootloader_version` is an optional packed semantic version (`major.minor.patch`)
encoded as a `u32`:

- `major = (value >> 20) & 0x03FF`
- `minor = (value >> 10) & 0x03FF`
- `patch = value & 0x03FF`

Older bootloader builds may omit this field; host tools should handle its absence.

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
