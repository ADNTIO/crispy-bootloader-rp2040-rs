// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Firmware update state machine over USB CDC.
//!
//! This module implements the update protocol:

//! - `GetStatus`: Query current bootloader state
//! - `StartUpdate`: Begin firmware upload to a bank
//! - `DataBlock`: Send firmware data chunks (accumulated in RAM)
//! - `FinishUpdate`: Persist to flash, verify CRC and commit the update
//! - `Reboot`: Restart the device
mod commands;
mod state;
mod storage;

pub use commands::dispatch_command;
pub use state::UpdateState;
