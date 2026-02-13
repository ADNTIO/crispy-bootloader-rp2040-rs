// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

use crispy_common::protocol::BootState;

/// Update state machine states.
#[derive(Clone, Copy, defmt::Format)]
pub enum UpdateState {
    /// Waiting for an explicit update-mode request.
    Standby,
    /// Initializing USB transport for update mode.
    InitializingUsb,
    /// Update mode is active and ready for commands.
    Ready,
    /// Actively receiving firmware data (accumulating in RAM).
    ReceivingData {
        bank: u8,
        bank_addr: u32,
        expected_size: u32,
        expected_crc: u32,
        version: u32,
        bytes_received: u32,
    },
}

impl UpdateState {
    pub(super) fn as_boot_state(self) -> BootState {
        match self {
            Self::Standby | Self::InitializingUsb | Self::Ready => BootState::UpdateMode,
            Self::ReceivingData { .. } => BootState::Receiving,
        }
    }
}
