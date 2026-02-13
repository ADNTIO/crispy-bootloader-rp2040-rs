// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! USB transport service for polling and receiving commands.

use crate::{peripherals::Peripherals, usb_transport::UsbTransport};
use core::cell::UnsafeCell;
use crispy_common::{
    protocol::Command,
    service::{Service, ServiceContext},
};
use heapless::spsc::Queue;

/// Wrapper to hold a Queue in a static without `static mut`.
///
/// SAFETY: This is only safe in a single-threaded (bare-metal, no OS) environment.
/// Only UsbTransportService (producer) calls enqueue, only UpdateService (consumer) calls dequeue.
struct SyncQueue(UnsafeCell<Queue<Command, 8>>);
unsafe impl Sync for SyncQueue {}

static COMMAND_QUEUE: SyncQueue = SyncQueue(UnsafeCell::new(Queue::new()));

/// Initialize the command queue (call once at startup)
pub fn init_command_queue() {
    // spsc::Queue is already initialized statically
}

/// Push a command to the queue (called by USB service)
#[allow(clippy::result_large_err)]
pub fn push_command(cmd: Command) -> Result<(), Command> {
    // SAFETY: Single-threaded bare-metal environment, no concurrent access
    unsafe { (*COMMAND_QUEUE.0.get()).enqueue(cmd) }
}

/// Pop a command from the queue (called by Update service)
pub fn pop_command() -> Option<Command> {
    // SAFETY: Single-threaded bare-metal environment, no concurrent access
    unsafe { (*COMMAND_QUEUE.0.get()).dequeue() }
}

/// Wrapper to hold an Option<UsbTransport> in a static without `static mut`.
///
/// SAFETY: Same single-threaded guarantee as above.
struct SyncTransport(UnsafeCell<Option<UsbTransport>>);
unsafe impl Sync for SyncTransport {}

static USB_TRANSPORT: SyncTransport = SyncTransport(UnsafeCell::new(None));

/// Store the USB transport (call once after initialization)
pub fn store_transport(transport: UsbTransport) {
    // SAFETY: Called only once during initialization, single-threaded
    unsafe {
        *USB_TRANSPORT.0.get() = Some(transport);
    }
}

/// Get a reference to the USB transport for sending responses
pub fn with_transport<F, R>(f: F) -> Option<R>
where
    F: FnOnce(&mut UsbTransport) -> R,
{
    // SAFETY: Single-threaded environment, no concurrent access
    unsafe { (*USB_TRANSPORT.0.get()).as_mut().map(f) }
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
