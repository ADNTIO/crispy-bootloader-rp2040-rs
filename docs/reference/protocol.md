# Protocol Reference

Transport protocol between host tools and bootloader.

## Encoding

- Framing: COBS with `0x00` packet delimiter
- Serialization: `postcard` (serde)
- Max data payload per `DataBlock`: `1024` bytes

## Commands

Defined in `crispy-common-rs/src/protocol.rs`.

- `GetStatus`
- `StartUpdate { bank, size, crc32, version }` — legacy, unsigned upload
- `DataBlock { offset, data }`
- `FinishUpdate`
- `SetActiveBank { bank }`
- `WipeAll`
- `Reboot`
- `StartUpdateSigned { bank, size, crc32, version, signature }` — signed upload
  (`signature` is a 64-byte Ed25519 signature over the firmware image)

`StartUpdateSigned` is appended after the legacy variants, so the `postcard`
wire encoding of all existing commands is unchanged.

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
- `SignatureInvalid` — signature did not verify against the embedded public key
- `SignatureRequired` — a signature is required (secure build) but the upload was unsigned

## BootState

- `Idle`
- `UpdateMode`
- `Receiving`

## Version Management

- `StartUpdate.version` is provided by the host for the target bank.
- The version is persisted to `BootData.version_a` or `BootData.version_b` only after a successful `FinishUpdate` (RAM CRC check + flash CRC check).
- `SetActiveBank` switches the active bank but does not rewrite bank version metadata.
- `WipeAll` resets boot metadata (`BootData::default_new()`), including bank versions.
- `Status.bootloader_version` is optional and encoded as packed semver (`u32`) for backward compatibility with older bootloader builds.

## Firmware signing

- The bootloader verifies an **Ed25519** signature over the firmware image at
  `FinishUpdate`, using a public key embedded at build time.
- Signed uploads use `StartUpdateSigned`; the host signs with the matching
  private key (see [`../how-to/sign-firmware.md`](../how-to/sign-firmware.md)).
- Unsigned uploads (`StartUpdate`) are only accepted by bootloaders built with
  the default `allow-unsigned` feature. A bootloader built with
  `--no-default-features` rejects them with `SignatureRequired`.
- Verification happens at upload time only; signatures are not persisted in
  `BootData`, and boot-time integrity continues to rely on the CRC-32 check.
