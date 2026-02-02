/*
* SPDX-License-Identifier: MIT OR Apache-2.0
*
* Firmware linker script for RP2040 — RAM execution
*
* The firmware binary is stored in flash by the build system but
* executed from RAM. The bootloader copies the binary from flash
* to FLASH (which is actually RAM) before jumping to the reset vector.
*
* RAM layout:
*   0x20000000 - 0x20030000: FLASH region (192KB) — code, rodata, data LMA
*   0x20030000 - 0x2003C000: RAM region (48KB) — data VMA, BSS, stack
*/

MEMORY {
    FLASH : ORIGIN = 0x20000000, LENGTH = 192K
    RAM   : ORIGIN = 0x20030000, LENGTH = 48K
}
