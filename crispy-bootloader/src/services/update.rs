// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Update service for firmware updates via USB.

use crate::{peripherals, peripherals::Peripherals, services::usb, update};
use core::cell::Cell;
use crispy_common::service::{Event, Service, ServiceContext};
use embedded_hal::digital::OutputPin;
use update::UpdateState;

/// Service for handling firmware updates via USB
pub struct UpdateService {
    state: Cell<UpdateState>,
}

impl UpdateService {
    pub fn new() -> Self {
        Self {
            state: Cell::new(UpdateState::Inactive),
        }
    }
}

impl Service<Peripherals> for UpdateService {
    fn process(&self, ctx: &mut ServiceContext<Peripherals>) {
        use UpdateState::*;
        let state = self.state.replace(Inactive);

        let new_state = match state {
            Inactive => {
                // Check if update was requested
                let mut activated = false;
                ctx.events.consume(|event| {
                    if matches!(event, Event::RequestUpdate) {
                        defmt::println!("Update mode requested");
                        activated = true;
                        true
                    } else {
                        false
                    }
                });
                if activated {
                    Initializing
                } else {
                    Inactive
                }
            }
            Initializing => {
                // Initialize USB once
                if let Some(mut usb) = ctx.peripherals.usb.take() {
                    let usb_bus = usb_device::class_prelude::UsbBusAllocator::new(
                        rp2040_hal::usb::UsbBus::new(
                            usb.regs,
                            usb.dpram,
                            usb.clock,
                            true,
                            &mut usb.resets,
                        ),
                    );

                    peripherals::store_usb_bus(usb_bus);

                    match crate::usb_transport::UsbTransport::new(peripherals::usb_bus_ref()) {
                        Ok(transport) => {
                            defmt::println!("USB CDC initialized");
                            ctx.peripherals.led_pin.set_high().ok();
                            // Store transport in USB service
                            usb::store_transport(transport);
                            Idle
                        }
                        Err(e) => {
                            defmt::error!("Failed to initialize USB transport: {:?}", e);
                            Inactive
                        }
                    }
                } else {
                    Inactive
                }
            }
            Idle | Receiving { .. } => {
                // Process commands from queue
                if let Some(cmd) = usb::pop_command() {
                    defmt::println!("Update: Dequeued command from queue");
                    let t_start = ctx.peripherals.timer.get_counter().ticks();

                    // Dispatch command with transport access
                    // Clone state for fallback since it will be moved into closure
                    let state_copy = state;
                    let new_state = usb::with_transport(move |transport| {
                        defmt::println!("Update: Dispatching command");
                        update::dispatch_command(transport, state_copy, cmd)
                    })
                    .unwrap_or_else(|| {
                        defmt::error!("Update: with_transport returned None!");
                        state
                    });

                    let t_end = ctx.peripherals.timer.get_counter().ticks();
                    defmt::println!(
                        "Update: Command took {} us, new state: {:?}",
                        t_end - t_start,
                        new_state
                    );
                    new_state
                } else {
                    state
                }
            }
            Persisting { .. } => {
                // Flash write in progress, ignore commands
                defmt::trace!("Update: Persisting, ignoring commands");
                state
            }
        };

        defmt::trace!("Update: State: {:?} -> {:?}", state, new_state);
        self.state.set(new_state);
    }
}
