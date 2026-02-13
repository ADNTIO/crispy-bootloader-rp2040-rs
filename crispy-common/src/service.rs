// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Generic service system for event-driven architecture.

use core::cell::RefCell;
use heapless::Vec;

/// Events that can be sent between services
#[derive(Debug, Clone, Copy)]
#[cfg_attr(feature = "defmt", derive(defmt::Format))]
pub enum Event {
    /// Request to enter update mode
    RequestUpdate,
    /// Request to enter boot mode
    RequestBoot,
}

/// Event bus for inter-service communication
pub struct EventBus {
    events: RefCell<Vec<Event, 32>>,
}

impl EventBus {
    pub const fn new() -> Self {
        Self {
            events: RefCell::new(Vec::new()),
        }
    }

    /// Publish an event to the bus
    pub fn publish(&self, event: Event) {
        if let Err(_) = self.events.borrow_mut().push(event) {
            #[cfg(feature = "defmt")]
            defmt::warn!("Event bus full, dropping event: {:?}", event);
        }
    }

    /// Consume events matching a filter
    pub fn consume<F>(&self, mut filter: F)
    where
        F: FnMut(&Event) -> bool,
    {
        self.events.borrow_mut().retain(|e| !filter(e));
    }

    /// Check if an event exists without consuming it
    pub fn has_event<F>(&self, filter: F) -> bool
    where
        F: FnMut(&Event) -> bool,
    {
        self.events.borrow().iter().any(filter)
    }
}

/// Shared context passed to all services
pub struct ServiceContext<'a, P> {
    pub peripherals: &'a mut P,
    pub events: &'a EventBus,
}

/// Trait for services that run in the main loop
pub trait Service<P> {
    /// Process this service's logic
    /// Uses interior mutability (Cell/RefCell) for state changes
    fn process(&self, ctx: &mut ServiceContext<P>);
}
