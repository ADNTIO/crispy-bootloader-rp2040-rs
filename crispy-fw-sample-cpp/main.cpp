// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>
//
// Minimal C++ firmware sample for Crispy Bootloader
// Bare-metal LED blink without SDK initialization.

#include <cstdint>

// RP2040 register addresses
constexpr uint32_t SIO_BASE = 0xD0000000;
constexpr uint32_t GPIO_OUT_SET = SIO_BASE + 0x014;
constexpr uint32_t GPIO_OUT_CLR = SIO_BASE + 0x018;
constexpr uint32_t GPIO_OE_SET = SIO_BASE + 0x024;

constexpr uint32_t IO_BANK0_BASE = 0x40014000;
constexpr uint32_t PADS_BANK0_BASE = 0x4001C000;
constexpr uint32_t RESETS_BASE = 0x4000C000;

constexpr uint32_t LED_PIN = 25;

volatile uint32_t& reg(uint32_t addr) {
    return *reinterpret_cast<volatile uint32_t*>(addr);
}

void delay(uint32_t cycles) {
    for (volatile uint32_t i = 0; i < cycles; i++) {
        asm volatile("nop");
    }
}

int main() {
    // Unreset IO_BANK0 and PADS_BANK0 if needed
    reg(RESETS_BASE + 0x0) &= ~((1 << 5) | (1 << 8)); // RESET register
    while ((reg(RESETS_BASE + 0x8) & ((1 << 5) | (1 << 8))) != ((1 << 5) | (1 << 8))) {}

    // Configure GPIO25 function to SIO (F5)
    reg(IO_BANK0_BASE + 0x0CC) = 5; // GPIO25_CTRL = SIO

    // Configure pad
    reg(PADS_BANK0_BASE + 0x68) = 0x56; // GPIO25 pad: output enable, no pull

    // Set as output
    reg(GPIO_OE_SET) = (1 << LED_PIN);

    // Blink loop
    while (true) {
        reg(GPIO_OUT_SET) = (1 << LED_PIN);
        delay(500000);
        reg(GPIO_OUT_CLR) = (1 << LED_PIN);
        delay(500000);
    }
}
