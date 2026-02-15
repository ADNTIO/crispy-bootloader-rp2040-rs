# Boot Data Reference

Boot metadata is stored in flash at `BOOT_DATA_ADDR` (`0x10190000`).

## Structure

Defined in `crispy-common-rs/src/protocol.rs` as `repr(C)` 32-byte struct:

```rust
pub struct BootData {
    pub magic: u32,
    pub active_bank: u8,
    pub confirmed: u8,
    pub boot_attempts: u8,
    pub _reserved0: u8,
    pub version_a: u32,
    pub version_b: u32,
    pub crc_a: u32,
    pub crc_b: u32,
    pub size_a: u32,
    pub size_b: u32,
}
```

## Field meaning

- `magic`: must equal `BOOT_DATA_MAGIC` (`0xB007DA7A`)
- `active_bank`: `0` for A, `1` for B
- `confirmed`: firmware marked as stable
- `boot_attempts`: increments on boot; rollback threshold is enforced in boot logic
- `version_*`: firmware versions per bank
- `crc_*`: CRC32 per bank
- `size_*`: firmware byte size per bank
