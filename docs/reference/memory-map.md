# Memory Map Reference

## Flash Layout (2 MB)

- `0x10000000`: `BOOT2` (256 B)
- `0x10000100`: Bootloader (64 KB)
- `0x10010000`: Firmware Bank A (768 KB)
- `0x100D0000`: Firmware Bank B (768 KB)
- `0x10190000`: BootData sector (4 KB)

## RAM Layout

- `0x20000000 - 0x2003BFEF`: firmware runtime RAM
- `0x2003BFF0 - 0x2003BFF3`: update flag (`0x0FDA7E00`)
- `0x2003C000 - 0x2003FFFF`: reserved/bootloader high RAM usage

## Important constants

Defined in `crispy-common/src/protocol.rs`:

- `FLASH_BASE = 0x10000000`
- `FW_A_ADDR = 0x10010000`
- `FW_B_ADDR = 0x100D0000`
- `BOOT_DATA_ADDR = 0x10190000`
- `RAM_UPDATE_FLAG_ADDR = 0x2003BFF0`
- `RAM_UPDATE_MAGIC = 0x0FDA7E00`
- `FW_BANK_SIZE = 768 * 1024`
