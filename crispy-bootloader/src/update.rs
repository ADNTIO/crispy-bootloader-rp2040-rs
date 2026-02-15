// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Firmware update state machine over USB CDC.
//!
//! This module implements the update protocol:
//! - GetStatus: Query current bootloader state
//! - StartUpdate: Begin firmware upload to a bank
//! - DataBlock: Send firmware data chunks (accumulated in RAM)
//! - FinishUpdate: Persist to flash, verify CRC and commit the update
//! - Reboot: Restart the device
//!
//! Version handling:
//! - `StartUpdate.version` is metadata provided by the host.
//! - This version is written to `BootData.version_a/version_b` only after a successful
//!   `FinishUpdate` (RAM CRC + flash CRC checks).
//! - `SetActiveBank` changes active selection only; it does not rewrite bank versions.

use crate::flash;
use crate::usb_transport::UsbTransport;
use crispy_common::protocol::*;

const BOOTLOADER_VERSION: &str = env!("CRISPY_VERSION");

/// Maximum firmware size that can be buffered in RAM
/// We use the firmware RAM region (0x20000000 - 0x20030000, 192KB) which is
/// unused during bootloader operation.
const FW_RAM_BUFFER_SIZE: usize = 128 * 1024;

/// RAM buffer address in firmware region (unused during bootloader operation)
const FW_RAM_BUFFER_ADDR: *mut u8 = 0x20000000 as *mut u8;

/// Update state machine states.
#[derive(Clone, Copy, defmt::Format)]
pub enum UpdateState {
    /// Inactive - not in update mode
    Inactive,
    /// Initializing USB
    Initializing,
    /// Waiting for a new update to start.
    Idle,
    /// Actively receiving firmware data (accumulating in RAM).
    Receiving {
        bank: u8,
        bank_addr: u32,
        expected_size: u32,
        expected_crc: u32,
        version: u32,
        bytes_received: u32,
    },
    /// Persisting firmware from RAM to flash (no USB commands processed).
    #[allow(dead_code)]
    Persisting {
        bank: u8,
        bank_addr: u32,
        size: u32,
        crc: u32,
        version: u32,
    },
}

/// Dispatch a command to its handler.
///
/// Note: version metadata is only committed on successful `FinishUpdate`.
pub fn dispatch_command(
    transport: &mut UsbTransport,
    state: UpdateState,
    cmd: Command,
) -> UpdateState {
    match cmd {
        Command::GetStatus => handle_get_status(transport, state),
        Command::StartUpdate {
            bank,
            size,
            crc32,
            version,
        } => handle_start_update(transport, state, bank, size, crc32, version),
        Command::DataBlock { offset, data } => handle_data_block(transport, state, offset, data),
        Command::FinishUpdate => handle_finish_update(transport, state),
        Command::Reboot => handle_reboot(transport),
        Command::SetActiveBank { bank } => handle_set_active_bank(transport, state, bank),
        Command::WipeAll => handle_wipe_all(transport, state),
    }
}

/// Handle GetStatus command: return current bootloader status.
fn handle_get_status(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    defmt::println!("handle_get_status called");
    let bd = flash::read_boot_data();
    let boot_state = match &state {
        UpdateState::Inactive => BootState::UpdateMode,
        UpdateState::Initializing => BootState::UpdateMode,
        UpdateState::Idle => BootState::UpdateMode,
        UpdateState::Receiving { .. } => BootState::Receiving,
        UpdateState::Persisting { .. } => BootState::Receiving,
    };
    let success = transport.send(&Response::Status {
        active_bank: bd.active_bank,
        version_a: bd.version_a,
        version_b: bd.version_b,
        state: boot_state,
        bootloader_version: parse_semver(BOOTLOADER_VERSION),
    });
    defmt::println!("handle_get_status: send returned {}", success);
    state
}

/// Handle StartUpdate command: validate parameters, erase bank, begin receiving.
fn handle_start_update(
    transport: &mut UsbTransport,
    state: UpdateState,
    bank: u8,
    size: u32,
    crc32: u32,
    version: u32,
) -> UpdateState {
    // Must be in Idle state
    if !matches!(state, UpdateState::Idle) {
        transport.send(&Response::Ack(AckStatus::BadState));
        return state;
    }

    // Validate bank number
    if bank > 1 {
        transport.send(&Response::Ack(AckStatus::BankInvalid));
        return state;
    }

    // Validate size fits in RAM buffer
    if size == 0 || size > FW_RAM_BUFFER_SIZE as u32 {
        defmt::warn!(
            "Firmware size {} exceeds RAM buffer {}",
            size,
            FW_RAM_BUFFER_SIZE
        );
        transport.send(&Response::Ack(AckStatus::BankInvalid));
        return state;
    }

    // Also check against flash bank size
    if size > FW_BANK_SIZE {
        transport.send(&Response::Ack(AckStatus::BankInvalid));
        return state;
    }

    let bank_addr = if bank == 0 { FW_A_ADDR } else { FW_B_ADDR };

    // No need to initialize RAM buffer - we'll overwrite it with firmware data
    // The buffer resides in unused firmware RAM region

    defmt::println!(
        "StartUpdate: bank={}, size={}, will buffer in RAM",
        bank,
        size
    );
    transport.send(&Response::Ack(AckStatus::Ok));

    UpdateState::Receiving {
        bank,
        bank_addr,
        expected_size: size,
        expected_crc: crc32,
        version,
        bytes_received: 0,
    }
}

/// Handle DataBlock command: validate offset, program flash.
fn handle_data_block(
    transport: &mut UsbTransport,
    mut state: UpdateState,
    offset: u32,
    data: heapless::Vec<u8, MAX_DATA_BLOCK_SIZE>,
) -> UpdateState {
    defmt::println!(
        "handle_data_block: offset={}, data_len={}",
        offset,
        data.len()
    );

    let UpdateState::Receiving {
        bank_addr: _,
        ref mut bytes_received,
        expected_size,
        ..
    } = state
    else {
        defmt::warn!("handle_data_block: BadState");
        transport.send(&Response::Ack(AckStatus::BadState));
        return state;
    };

    defmt::println!(
        "handle_data_block: bytes_received={}, expected={}",
        *bytes_received,
        expected_size
    );

    // Validate sequential offset
    if offset != *bytes_received {
        defmt::warn!(
            "handle_data_block: BadOffset {} != {}",
            offset,
            *bytes_received
        );
        transport.send(&Response::Ack(AckStatus::BadCommand));
        return state;
    }

    // Validate data doesn't exceed expected size
    let data_len = data.len() as u32;
    if *bytes_received + data_len > expected_size {
        defmt::warn!("handle_data_block: Size overflow");
        transport.send(&Response::Ack(AckStatus::BadCommand));
        return state;
    }

    // Copy data to RAM buffer (NO flash writes, interrupts stay enabled!)
    let ram_offset = *bytes_received as usize;
    defmt::println!(
        "handle_data_block: Copying {} bytes to RAM at offset {}",
        data_len,
        ram_offset
    );

    unsafe {
        core::ptr::copy_nonoverlapping(
            data.as_ptr(),
            FW_RAM_BUFFER_ADDR.add(ram_offset),
            data_len as usize,
        );
    }

    *bytes_received += data_len;

    // Send ACK immediately (fast, no flash delays!)
    defmt::println!("handle_data_block: Sending ACK");
    let success = transport.send(&Response::Ack(AckStatus::Ok));
    defmt::println!("handle_data_block: ACK sent, success={}", success);
    state
}

/// Handle FinishUpdate command: persist RAM buffer to flash, verify CRC, update BootData.
fn handle_finish_update(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    let UpdateState::Receiving {
        bank,
        bank_addr,
        expected_size,
        expected_crc,
        version,
        bytes_received,
    } = state
    else {
        transport.send(&Response::Ack(AckStatus::BadState));
        return state;
    };

    // Verify all data was received in RAM
    if bytes_received != expected_size {
        defmt::warn!(
            "FinishUpdate: Incomplete data {} != {}",
            bytes_received,
            expected_size
        );
        transport.send(&Response::Ack(AckStatus::BadCommand));
        return UpdateState::Receiving {
            bank,
            bank_addr,
            expected_size,
            expected_crc,
            version,
            bytes_received,
        };
    }

    defmt::println!("FinishUpdate: Verifying CRC of RAM buffer");
    // Verify CRC of RAM buffer BEFORE writing to flash
    let ram_crc = unsafe {
        use crc::{Crc, CRC_32_ISO_HDLC};
        const CRC32: Crc<u32> = Crc::<u32>::new(&CRC_32_ISO_HDLC);
        let mut digest = CRC32.digest();
        let ram_slice = core::slice::from_raw_parts(FW_RAM_BUFFER_ADDR, expected_size as usize);
        digest.update(ram_slice);
        digest.finalize()
    };

    if ram_crc != expected_crc {
        defmt::warn!(
            "FinishUpdate: CRC mismatch in RAM: expected 0x{:08x}, got 0x{:08x}",
            expected_crc,
            ram_crc
        );
        transport.send(&Response::Ack(AckStatus::CrcError));
        return UpdateState::Idle;
    }

    defmt::println!("FinishUpdate: CRC OK, persisting to flash...");

    // Erase flash bank (this takes time but no USB commands are expected now)
    let erase_size = expected_size.div_ceil(FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE;
    let flash_offset = flash::addr_to_offset(bank_addr);
    unsafe {
        flash::flash_erase(flash_offset, erase_size);
    }

    // Write RAM buffer to flash (page by page to respect flash alignment)
    let mut offset = 0u32;
    while offset < expected_size {
        let chunk_size = (expected_size - offset).min(FLASH_PAGE_SIZE);
        let padded_size = chunk_size.div_ceil(FLASH_PAGE_SIZE) * FLASH_PAGE_SIZE;

        unsafe {
            let src_ptr = FW_RAM_BUFFER_ADDR.add(offset as usize) as *const u8;
            flash::flash_program(flash_offset + offset, src_ptr, padded_size as usize);
        }

        offset += chunk_size;
    }

    defmt::println!("FinishUpdate: Flash write complete, verifying...");

    // Verify CRC from flash
    let flash_crc = flash::compute_crc32(bank_addr, expected_size);
    if flash_crc != expected_crc {
        defmt::error!(
            "FinishUpdate: Flash CRC mismatch: expected 0x{:08x}, got 0x{:08x}",
            expected_crc,
            flash_crc
        );
        transport.send(&Response::Ack(AckStatus::CrcError));
        return UpdateState::Idle;
    }

    // Update BootData
    let mut bd = flash::read_boot_data();
    bd.active_bank = bank;
    bd.confirmed = 0; // unconfirmed until firmware confirms
    bd.boot_attempts = 0;

    if bank == 0 {
        bd.version_a = version;
        bd.crc_a = expected_crc;
        bd.size_a = expected_size;
    } else {
        bd.version_b = version;
        bd.crc_b = expected_crc;
        bd.size_b = expected_size;
    }

    unsafe {
        flash::write_boot_data(&bd);
    }

    transport.send(&Response::Ack(AckStatus::Ok));
    UpdateState::Idle
}

/// Handle Reboot command: send ACK and reset the system.
fn handle_reboot(transport: &mut UsbTransport) -> ! {
    transport.send(&Response::Ack(AckStatus::Ok));
    // Small delay to let the ACK be sent
    cortex_m::asm::delay(12_000_000); // ~1s at 12MHz
    cortex_m::peripheral::SCB::sys_reset();
}

/// Handle SetActiveBank command: change the active bank for next boot.
fn handle_set_active_bank(
    transport: &mut UsbTransport,
    state: UpdateState,
    bank: u8,
) -> UpdateState {
    // Must be in Idle state
    if !matches!(state, UpdateState::Idle) {
        transport.send(&Response::Ack(AckStatus::BadState));
        return state;
    }

    // Validate bank number
    if bank > 1 {
        transport.send(&Response::Ack(AckStatus::BankInvalid));
        return state;
    }

    // Read current BootData and update active bank
    let mut bd = flash::read_boot_data();

    // Check that the target bank has valid firmware
    let (size, crc) = if bank == 0 {
        (bd.size_a, bd.crc_a)
    } else {
        (bd.size_b, bd.crc_b)
    };

    if size == 0 {
        defmt::println!("SetActiveBank: bank {} has no firmware", bank);
        transport.send(&Response::Ack(AckStatus::BankInvalid));
        return state;
    }

    // Verify CRC of the target bank
    let bank_addr = if bank == 0 { FW_A_ADDR } else { FW_B_ADDR };
    let actual_crc = flash::compute_crc32(bank_addr, size);
    if actual_crc != crc {
        defmt::println!(
            "SetActiveBank: bank {} CRC mismatch (expected 0x{:08x}, got 0x{:08x})",
            bank,
            crc,
            actual_crc
        );
        transport.send(&Response::Ack(AckStatus::CrcError));
        return state;
    }

    // Update BootData
    bd.active_bank = bank;
    bd.confirmed = 0; // unconfirmed until firmware confirms
    bd.boot_attempts = 0;

    unsafe {
        flash::write_boot_data(&bd);
    }

    defmt::println!("SetActiveBank: switched to bank {}", bank);
    transport.send(&Response::Ack(AckStatus::Ok));
    state
}

fn handle_wipe_all(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    if !matches!(state, UpdateState::Idle) {
        transport.send(&Response::Ack(AckStatus::BadState));
        return state;
    }

    defmt::println!("Resetting boot data");
    unsafe {
        flash::write_boot_data(&BootData::default_new());
    }

    transport.send(&Response::Ack(AckStatus::Ok));
    state
}
