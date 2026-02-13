// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Update service for firmware updates via USB.

use crate::{peripherals, peripherals::Peripherals, update, usb_transport::UsbTransport};
use core::cell::{Cell, RefCell};
use crispy_common::service::{Event, Service, ServiceContext};
use embedded_hal::digital::OutputPin;
use update::UpdateState;

/// Service for handling firmware updates via USB
pub struct UpdateService {
    state: Cell<UpdateState>,
    transport: RefCell<Option<UsbTransport>>,
}

impl UpdateService {
    pub fn new() -> Self {
        Self {
            state: Cell::new(UpdateState::Inactive),
            transport: RefCell::new(None),
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
                    crispy_common::blink(&mut ctx.peripherals.led_pin, &mut ctx.peripherals.timer, 10, 50);

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

                    match UsbTransport::new(peripherals::usb_bus_ref()) {
                        Ok(transport) => {
                            *self.transport.borrow_mut() = Some(transport);
                            defmt::println!("USB CDC initialized, entering update mode");
                            ctx.peripherals.led_pin.set_high().ok();
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
                // Poll USB and process one command at a time
                if let Some(ref mut transport) = *self.transport.borrow_mut() {
                    transport.poll();

                    if let Some(cmd) = transport.try_receive() {
                        update::dispatch_command(transport, state, cmd)
                    } else {
                        state
                    }
                } else {
                    state
                }
            }
        };

        self.state.set(new_state);
    }
}
