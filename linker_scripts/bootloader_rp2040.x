/*
* SPDX-License-Identifier: MIT OR Apache-2.0
* Bootloader linker script for RP2040
*
* Flash layout (2MB):
*   0x10000000 - 0x10000100: BOOT2 (256B)
*   0x10000100 - 0x10004100: Bootloader (16KB)
*   0x10004100 - 0x100C4100: FW_A bank (768KB)
*   0x100C4100 - 0x10184100: FW_B bank (768KB)
*   0x10184100 - 0x10185100: BOOT_DATA (4KB)
*
* RAM layout (256KB):
*   0x20000000 - 0x20030000: Firmware code (192KB, copied by bootloader)
*   0x20030000 - 0x2003C000: Firmware data/BSS/stack (48KB)
*   0x2003C000 - 0x20040000: Bootloader data/BSS/stack (16KB)
*/

MEMORY {
    BOOT2 : ORIGIN = 0x10000000, LENGTH = 0x100
    FLASH : ORIGIN = 0x10000100, LENGTH = 16K
    RAM   : ORIGIN = 0x2003C000, LENGTH = 16K
}

EXTERN(BOOT2_FIRMWARE)

SECTIONS {
    /* ### Boot loader */
    .boot2 ORIGIN(BOOT2) :
    {
        KEEP(*(.boot2));
    } > BOOT2
} INSERT BEFORE .text;

SECTIONS {
    /* ### Boot ROM info */
    .boot_info : ALIGN(4)
    {
        KEEP(*(.boot_info));
    } > FLASH

} INSERT AFTER .vector_table;

/* move .text to start /after/ the boot info */
_stext = ADDR(.boot_info) + SIZEOF(.boot_info);

SECTIONS {
    /* ### Picotool 'Binary Info' Entries */
    .bi_entries : ALIGN(4)
    {
        __bi_entries_start = .;
        KEEP(*(.bi_entries));
        . = ALIGN(4);
        __bi_entries_end = .;
    } > FLASH
} INSERT AFTER .text;

/* Firmware bank addresses in flash */
PROVIDE(__fw_a_entry = 0x10004100);
PROVIDE(__fw_b_entry = 0x100C4100);
PROVIDE(__boot_data_addr = 0x10184100);

/* Firmware copy parameters */
PROVIDE(__fw_ram_base = 0x20000000);
PROVIDE(__fw_copy_size = 0x30000);  /* 192KB */
