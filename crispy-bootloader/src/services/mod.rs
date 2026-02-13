// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Service implementations for the bootloader.

pub mod led;
pub mod trigger;
pub mod update;
pub mod usb;

pub use led::LedBlinkService;
pub use trigger::TriggerCheckService;
pub use update::UpdateService;
pub use usb::UsbTransportService;
