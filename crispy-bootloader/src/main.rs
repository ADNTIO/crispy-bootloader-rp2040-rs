// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Crispy Bootloader for RP2040 with A/B multiboot and USB CDC update mode.

#![no_std]
#![no_main]

mod boot;
mod flash;
mod peripherals;
mod services;
mod update;
mod usb_transport;

use defmt_rtt as _;
use panic_probe as _;

use crispy_common::service::{Event, EventBus, Service, ServiceContext};
use peripherals::Peripherals;
use services::{LedBlinkService, TriggerCheckService, UpdateService, UsbTransportService};

defmt::timestamp!("{=u64:us}", { 0 });

use cortex_m_rt::entry;

#[unsafe(link_section = ".boot2")]
#[used]
pub static BOOT2: [u8; 256] = rp2040_boot2::BOOT_LOADER_GENERIC_03H;

/// Enum containing all possible services
enum ServiceType {
    UsbTransport(UsbTransportService),
    Trigger(TriggerCheckService),
    Update(UpdateService),
    Led(LedBlinkService),
}

impl ServiceType {
    /// Process this service
    fn process(&self, ctx: &mut ServiceContext<Peripherals>) {
        match self {
            ServiceType::UsbTransport(s) => s.process(ctx),
            ServiceType::Trigger(s) => s.process(ctx),
            ServiceType::Update(s) => s.process(ctx),
            ServiceType::Led(s) => s.process(ctx),
        }
    }
}

#[entry]
fn main() -> ! {
    defmt::println!("Bootloader starting");

    let mut p = init_hardware();

    // Initialize command queue for USB<->Update communication
    services::usb::init_command_queue();

    let event_bus = EventBus::new();

    let services = [
        ServiceType::UsbTransport(UsbTransportService::new()),  
        ServiceType::Trigger(TriggerCheckService::new()),
        ServiceType::Update(UpdateService::new()),
        ServiceType::Led(LedBlinkService::new()),
    ];

    defmt::println!("Starting main loop with {} services", services.len());

    loop {
        let mut ctx = ServiceContext {
            peripherals: &mut p,
            events: &event_bus,
        };

        // Process all services
        for service in &services {
            service.process(&mut ctx);
        }

        // Check for boot request
        if event_bus.has_event(|e| matches!(e, Event::RequestBoot)) {
            event_bus.consume(|e| matches!(e, Event::RequestBoot));
            boot::run_normal_boot(&mut p);
            // run_normal_boot only returns when no valid firmware is found
            // → fall back to update mode so the device enumerates on USB
            defmt::println!("No bootable firmware, entering update mode");
            event_bus.publish(Event::RequestUpdate);
        }
    }
}

/// Initialize hardware and flash subsystem
fn init_hardware() -> peripherals::Peripherals {
    let mut p = match peripherals::init() {
        Ok(p) => p,
        Err(e) => {
            defmt::error!("Failed to initialize peripherals: {:?}", e);
            loop {
                cortex_m::asm::wfi();
            }
        }
    };

    crispy_common::blink(&mut p.led_pin, &mut p.timer, 3, 200);
    flash::init();

    p
}
