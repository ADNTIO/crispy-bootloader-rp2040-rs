# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

CHIP = "rp2040"

# Memory addresses (matching crispy-common-rs/src/protocol.rs)
RAM_UPDATE_FLAG_ADDR = 0x2003_BFF0
RAM_UPDATE_MAGIC = 0x0FDA_7E00
BOOT_DATA_ADDR = 0x101A_0000
BOOT2_ADDR = 0x1000_0000
BOOT_DATA_SECTOR_SIZE = 4096
BOOT2_SIZE = 256

# USB identifiers (VID = 2E8A / Raspberry Pi)
DEFAULT_VID = "2e8a"
PID_BOOTLOADER = "000a"
PID_FW_RUST = "000b"

EMBEDDED_TARGET = "thumbv6m-none-eabi"
