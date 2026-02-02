// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

#![no_std]
#![no_main]

mod boot;

use defmt_rtt as _;
use embedded_hal::digital::OutputPin;
use panic_probe as _;

defmt::timestamp!("{=u64:us}", { 0 });

use cortex_m_rt::entry;

#[unsafe(link_section = ".boot2")]
#[used]
pub static BOOT2: [u8; 256] = rp2040_boot2::BOOT_LOADER_GENERIC_03H;

#[entry]
fn main() -> ! {
    defmt::println!("Bootloader init");

    let (mut timer, mut led_pin) = crispy_common::init_board();
    crispy_common::blink(&mut led_pin, &mut timer, 3, 200);

    let layout = boot::MemoryLayout::from_linker();

    let preferred_bank = boot::read_boot_data(layout.boot_data).unwrap_or_else(|| {
        defmt::println!("BOOT_DATA: no valid data, defaulting to bank A");
        0
    });
    if preferred_bank != 0 {
        defmt::println!("BOOT_DATA: active bank = {}", preferred_bank);
    }

    let banks = if preferred_bank == 0 {
        [(layout.fw_a, "A"), (layout.fw_b, "B")]
    } else {
        [(layout.fw_b, "B"), (layout.fw_a, "A")]
    };

    let selected = banks.iter().find_map(|&(addr, label)| {
        defmt::println!("Checking bank {} at 0x{:08x}", label, addr);
        boot::validate_bank(addr).map(|(sp, reset)| {
            defmt::println!("  SP:    0x{:08x}", sp);
            defmt::println!("  Reset: 0x{:08x}", reset);
            (addr, label)
        })
    });

    let Some((flash_addr, label)) = selected else {
        defmt::println!("No valid firmware in any bank");
        led_pin.set_high().ok();
        loop {
            cortex_m::asm::nop();
        }
    };

    defmt::println!(
        "Loading bank {} from 0x{:08x} to 0x{:08x} ({}KB)",
        label,
        flash_addr,
        layout.ram_base,
        layout.copy_size / 1024
    );
    defmt::println!("Jumping to firmware...");

    unsafe { boot::load_and_jump(flash_addr, &layout) }
}
