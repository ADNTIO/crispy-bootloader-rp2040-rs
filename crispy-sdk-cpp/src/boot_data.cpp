// SPDX-License-Identifier: MIT
// Crispy Bootloader - BootData operations

#include "crispy/boot_data.h"
#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include <cstring>
#include <cstdio>

namespace crispy {

BootData read_boot_data() {
    const auto* bd = reinterpret_cast<const BootData*>(BOOT_DATA_ADDR);
    return *bd;
}

void confirm_boot() {
    BootData bd = read_boot_data();

    if (!bd.is_valid()) {
        printf("BootData invalid, skipping confirmation\r\n");
        return;
    }
    if (bd.confirmed == 1) {
        printf("Boot already confirmed\r\n");
        return;
    }

    printf("Confirming boot (bank=%d)...\r\n", bd.active_bank);

    bd.confirmed = 1;
    bd.boot_attempts = 0;

    uint32_t offset = BOOT_DATA_ADDR - FLASH_BASE_ADDR;

    // Pad to FLASH_PAGE_SIZE (256 bytes)
    uint8_t page[FLASH_PAGE_SIZE];
    memset(page, 0xFF, sizeof(page));
    memcpy(page, &bd, sizeof(bd));

    // Disable interrupts during flash operations
    uint32_t ints = save_and_disable_interrupts();

    // Erase sector (4KB) and program page
    flash_range_erase(offset, FLASH_SECTOR_SIZE);
    flash_range_program(offset, page, sizeof(page));

    restore_interrupts(ints);

    printf("Boot confirmed successfully\r\n");
}

// Trigger ARM system reset via AIRCR register (same as Rust's SCB::sys_reset)
static void sys_reset() {
    constexpr uint32_t AIRCR = 0xE000ED0C;
    constexpr uint32_t VECTKEY = 0x05FA0000;
    constexpr uint32_t SYSRESETREQ = 1u << 2;

    // Memory barrier before reset
    __asm volatile ("dsb 0xF" ::: "memory");

    *reinterpret_cast<volatile uint32_t*>(AIRCR) = VECTKEY | SYSRESETREQ;

    // Wait for reset
    __asm volatile ("dsb 0xF" ::: "memory");
    while (true) tight_loop_contents();
}

void reboot_to_bootloader() {
    printf("Rebooting to bootloader update mode...\r\n");
    sleep_ms(100);

    // Write magic to RAM flag
    *reinterpret_cast<volatile uint32_t*>(RAM_UPDATE_FLAG_ADDR) = RAM_UPDATE_MAGIC;

    // Small delay to ensure write completes
    busy_wait_us(100000);

    sys_reset();
}

void reboot() {
    printf("Rebooting...\r\n");
    sleep_ms(100);
    sys_reset();
}

} // namespace crispy
