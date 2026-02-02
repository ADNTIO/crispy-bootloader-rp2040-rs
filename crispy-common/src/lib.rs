// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

#![no_std]

use embedded_hal::delay::DelayNs;
use embedded_hal::digital::OutputPin;
use rp2040_hal as hal;

pub type LedPin =
    hal::gpio::Pin<hal::gpio::bank0::Gpio25, hal::gpio::FunctionSioOutput, hal::gpio::PullDown>;

/// # Safety
/// Uses `Peripherals::steal()` — caller must ensure exclusive peripheral access.
pub fn init_board() -> (hal::Timer, LedPin) {
    let mut pac = unsafe { hal::pac::Peripherals::steal() };

    let mut watchdog = hal::Watchdog::new(pac.WATCHDOG);
    let clocks = hal::clocks::init_clocks_and_plls(
        12_000_000u32,
        pac.XOSC,
        pac.CLOCKS,
        pac.PLL_SYS,
        pac.PLL_USB,
        &mut pac.RESETS,
        &mut watchdog,
    )
    .unwrap();

    let timer = hal::Timer::new(pac.TIMER, &mut pac.RESETS, &clocks);
    let sio = hal::Sio::new(pac.SIO);
    let pins = hal::gpio::Pins::new(
        pac.IO_BANK0,
        pac.PADS_BANK0,
        sio.gpio_bank0,
        &mut pac.RESETS,
    );

    (timer, pins.gpio25.into_push_pull_output())
}

pub fn blink(led: &mut impl OutputPin, timer: &mut impl DelayNs, count: u32, period_ms: u32) {
    for _ in 0..count {
        led.set_high().ok();
        timer.delay_ms(period_ms);
        led.set_low().ok();
        timer.delay_ms(period_ms);
    }
}
