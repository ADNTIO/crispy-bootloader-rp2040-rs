// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! USB transport service for polling and receiving commands.

use crate::{peripherals::Peripherals, usb_transport::UsbTransport};
use crispy_common::{protocol::Command, service::{Service, ServiceContext}};
use heapless::spsc::Queue;

/// Static command queue for USB -> Update communication
///
/// SAFETY: This is safe because we run in a single-threaded environment.
/// Only UsbTransportService (producer) calls enqueue, only UpdateService (consumer) calls dequeue.
static mut COMMAND_QUEUE: Queue<Command, 8> = Queue::new();

/// Initialize the command queue (call once at startup)
pub fn init_command_queue() {
    // spsc::Queue is already initialized statically
}

/// Push a command to the queue (called by USB service)
pub fn push_command(cmd: Command) -> Result<(), Command> {
    unsafe {
        // SAFETY: Single-threaded, only UsbTransportService calls this
        COMMAND_QUEUE.enqueue(cmd)
    }
}

/// Pop a command from the queue (called by Update service)
pub fn pop_command() -> Option<Command> {
    unsafe {
        // SAFETY: Single-threaded, only UpdateService calls this
        COMMAND_QUEUE.dequeue()
    }
}

/// Static USB transport shared between services
///
/// SAFETY: This is safe because we run in a single-threaded environment
/// (bare metal, no OS). Access is protected by RefCell borrow checking.
static mut USB_TRANSPORT: Option<UsbTransport> = None;

/// Store the USB transport (call once after initialization)
pub fn store_transport(transport: UsbTransport) {
    unsafe {
        // SAFETY: Called only once during initialization
        USB_TRANSPORT = Some(transport);
    }
}

/// Get a reference to the USB transport for sending responses
pub fn with_transport<F, R>(f: F) -> Option<R>
where
    F: FnOnce(&mut UsbTransport) -> R,
{
    unsafe {
        // SAFETY: Single-threaded environment, no concurrent access
        USB_TRANSPORT.as_mut().map(f)
    }
}

/// Service that polls USB and queues received commands
pub struct UsbTransportService;

impl UsbTransportService {
    pub fn new() -> Self {
        Self
    }
}

impl Service<Peripherals> for UsbTransportService {
    fn process(&self, _ctx: &mut ServiceContext<Peripherals>) {
        with_transport(|transport| {
            // Poll USB device
            transport.poll();

            // Try to receive a command and queue it
            if let Some(cmd) = transport.try_receive() {
                defmt::println!("USB: Received command");
                match push_command(cmd) {
                    Ok(()) => {
                        defmt::println!("USB: Command queued successfully");
                    }
                    Err(_) => {
                        defmt::warn!("Command queue full, dropping command");
                    }
                }
            }
        });
    }
}
