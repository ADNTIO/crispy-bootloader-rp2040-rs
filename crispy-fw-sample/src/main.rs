// Copyright (c) 2026 ADNT Sarl <info@adnt.io>
// SPDX-License-Identifier: MIT

#![no_std]
#![no_main]

use defmt_rtt as _;
use panic_probe as _;

defmt::timestamp!("{=u64:us}", { 0 });

use cortex_m_rt::entry;

#[entry]
fn main() -> ! {
    defmt::println!("Firmware started!");

    let (mut timer, mut led_pin) = crispy_common::init_board();

    defmt::println!("Firmware: blinking LED");

    for count in (10u32..).step_by(10) {
        crispy_common::blink(&mut led_pin, &mut timer, 10, 100);
        defmt::println!("FW blink count: {}", count);
    }

    unreachable!()
}
