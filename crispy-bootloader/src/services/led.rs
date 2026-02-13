// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! LED service for status indication.

use crate::peripherals::Peripherals;
use core::cell::Cell;
use crispy_common::service::{Service, ServiceContext};
use embedded_hal::digital::OutputPin;

/// LED state machine
#[derive(Clone, Copy)]
enum LedState {
    On { since_us: u64 },
    Off { since_us: u64 },
}

/// Service that blinks the LED periodically based on time
pub struct LedBlinkService {
    state: Cell<LedState>,
}

const LED_PERIOD_US: u64 = 500_000; // 500ms

impl LedBlinkService {
    pub fn new() -> Self {
        Self {
            state: Cell::new(LedState::Off { since_us: 0 }),
        }
    }
}

impl Service<Peripherals> for LedBlinkService {
    fn process(&self, ctx: &mut ServiceContext<Peripherals>) {
        let now = ctx.peripherals.timer.get_counter().ticks();
        let state = self.state.get();

        match state {
            LedState::On { since_us } => {
                if now - since_us >= LED_PERIOD_US {
                    ctx.peripherals.led_pin.set_low().ok();
                    self.state.set(LedState::Off { since_us: now });
                }
            }
            LedState::Off { since_us } => {
                if now - since_us >= LED_PERIOD_US {
                    ctx.peripherals.led_pin.set_high().ok();
                    self.state.set(LedState::On { since_us: now });
                }
            }
        }
    }
}
