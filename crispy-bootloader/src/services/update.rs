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

/// External event observed by the service-level FSM.
#[derive(Clone, Copy)]
enum FsmEvent {
    Tick,
    UpdateRequested,
}

/// Side effect to execute after a state transition.
#[derive(Clone, Copy)]
enum FsmAction {
    None,
    InitializeUsb,
    PumpCommandQueue,
    IgnoreCommands,
}

/// Result of one pure FSM transition step.
#[derive(Clone, Copy)]
struct FsmStep {
    next_state: UpdateState,
    action: FsmAction,
}

impl UpdateService {
    pub fn new() -> Self {
        Self {
            state: Cell::new(UpdateState::Standby),
        }
    }

    fn consume_update_request(ctx: &mut ServiceContext<Peripherals>) -> bool {
        let mut requested = false;
        ctx.events.consume(|event| {
            let is_update_request = matches!(event, Event::RequestUpdate);
            requested |= is_update_request;
            is_update_request
        });
        requested
    }

    fn initialize_usb(ctx: &mut ServiceContext<Peripherals>) -> UpdateState {
        let Some(mut usb) = ctx.peripherals.usb.take() else {
            defmt::warn!("Update: USB peripheral unavailable during initialization");
            return UpdateState::Standby;
        };

        let usb_bus = usb_device::class_prelude::UsbBusAllocator::new(
            rp2040_hal::usb::UsbBus::new(usb.regs, usb.dpram, usb.clock, true, &mut usb.resets),
        );

        peripherals::store_usb_bus(usb_bus);

        match crate::usb_transport::UsbTransport::new(peripherals::usb_bus_ref()) {
            Ok(transport) => {
                defmt::println!("USB CDC initialized");
                ctx.peripherals.led_pin.set_high().ok();
                usb::store_transport(transport);
                UpdateState::Ready
            }
            Err(e) => {
                defmt::error!("Failed to initialize USB transport: {:?}", e);
                UpdateState::Standby
            }
        }
    }

    fn process_pending_command(
        ctx: &mut ServiceContext<Peripherals>,
        state: UpdateState,
    ) -> UpdateState {
        let Some(cmd) = usb::pop_command() else {
            return state;
        };

        defmt::println!("Update: Dequeued command from queue");
        let t_start = ctx.peripherals.timer.get_counter().ticks();

        let Some(new_state) = usb::with_transport(|transport| {
            defmt::println!("Update: Dispatching command");
            update::dispatch_command(transport, state, cmd)
        }) else {
            defmt::error!("Update: with_transport returned None!");
            return state;
        };

        let t_end = ctx.peripherals.timer.get_counter().ticks();
        defmt::println!(
            "Update: Command took {} us, new state: {:?}",
            t_end - t_start,
            new_state
        );
        new_state
    }

    fn transition(state: UpdateState, event: FsmEvent) -> FsmStep {
        match (state, event) {
            (UpdateState::Standby, FsmEvent::UpdateRequested) => FsmStep {
                next_state: UpdateState::InitializingUsb,
                action: FsmAction::None,
            },
            (UpdateState::Standby, FsmEvent::Tick) => FsmStep {
                next_state: UpdateState::Standby,
                action: FsmAction::None,
            },
            (UpdateState::InitializingUsb, _) => FsmStep {
                next_state: UpdateState::InitializingUsb,
                action: FsmAction::InitializeUsb,
            },
            (UpdateState::Ready | UpdateState::ReceivingData { .. }, _) => FsmStep {
                next_state: state,
                action: FsmAction::PumpCommandQueue,
            },
            (UpdateState::WritingFlash { .. }, _) => FsmStep {
                next_state: state,
                action: FsmAction::IgnoreCommands,
            },
        }
    }

    fn detect_event(ctx: &mut ServiceContext<Peripherals>, state: UpdateState) -> FsmEvent {
        match state {
            UpdateState::Standby if Self::consume_update_request(ctx) => FsmEvent::UpdateRequested,
            _ => FsmEvent::Tick,
        }
    }

    fn run_action(
        ctx: &mut ServiceContext<Peripherals>,
        state: UpdateState,
        action: FsmAction,
    ) -> UpdateState {
        match action {
            FsmAction::None => state,
            FsmAction::InitializeUsb => Self::initialize_usb(ctx),
            FsmAction::PumpCommandQueue => Self::process_pending_command(ctx, state),
            FsmAction::IgnoreCommands => {
                defmt::trace!("Update: WritingFlash, ignoring commands");
                state
            }
        }
    }

    fn step(ctx: &mut ServiceContext<Peripherals>, state: UpdateState) -> UpdateState {
        let event = Self::detect_event(ctx, state);
        let fsm_step = Self::transition(state, event);
        if matches!(event, FsmEvent::UpdateRequested) {
            defmt::println!("Update mode requested");
        }
        Self::run_action(ctx, fsm_step.next_state, fsm_step.action)
    }
}

impl Default for UpdateService {
    fn default() -> Self {
        Self::new()
    }
}

impl Service<Peripherals> for UpdateService {
    fn process(&self, ctx: &mut ServiceContext<Peripherals>) {
        let state = self.state.get();
        let new_state = Self::step(ctx, state);

        defmt::trace!("Update: State: {:?} -> {:?}", state, new_state);
        self.state.set(new_state);
    }
}
