// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Trigger checking service for boot mode selection.

use crate::{boot, peripherals::Peripherals};
use core::cell::Cell;
use crispy_common::service::{Event, Service, ServiceContext};
use embedded_hal::digital::InputPin;

/// Service for checking mode triggers at startup
pub struct TriggerCheckService {
    checked: Cell<bool>,
}

impl TriggerCheckService {
    pub fn new() -> Self {
        Self {
            checked: Cell::new(false),
        }
    }
}

impl Service<Peripherals> for TriggerCheckService {
    fn process(&self, ctx: &mut ServiceContext<Peripherals>) {
        if self.checked.get() {
            return;
        }

        self.checked.set(true);
        let gp2_low = ctx.peripherals.gp2.is_low().unwrap_or(false);

        if boot::check_update_trigger(gp2_low) {
            defmt::println!("Update mode triggered");
            ctx.events.publish(Event::RequestUpdate);
        } else {
            defmt::println!("Boot mode selected");
            ctx.events.publish(Event::RequestBoot);
        }
    }
}
