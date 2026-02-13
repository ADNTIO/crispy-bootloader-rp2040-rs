// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

use super::{state::UpdateState, storage};
use crate::flash;
use crate::usb_transport::UsbTransport;
use crispy_common::protocol::{
    parse_semver, AckStatus, BootData, Command, Response, FW_A_ADDR, FW_BANK_SIZE, FW_B_ADDR,
};

const BOOTLOADER_VERSION: &str = env!("CARGO_PKG_VERSION");

fn bank_addr(bank: u8) -> Option<u32> {
    match bank {
        0 => Some(FW_A_ADDR),
        1 => Some(FW_B_ADDR),
        _ => None,
    }
}

fn bank_firmware_info(bd: &BootData, bank: u8) -> Option<(u32, u32)> {
    match bank {
        0 => Some((bd.size_a, bd.crc_a)),
        1 => Some((bd.size_b, bd.crc_b)),
        _ => None,
    }
}

fn send_ack(transport: &mut UsbTransport, status: AckStatus) {
    let _ = transport.send(&Response::Ack(status));
}

fn reject_with(transport: &mut UsbTransport, status: AckStatus, state: UpdateState) -> UpdateState {
    send_ack(transport, status);
    state
}

/// Dispatch a command to its handler.
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
        Command::DataBlock { offset, data } => {
            handle_data_block(transport, state, offset, data.as_slice())
        }
        Command::FinishUpdate => handle_finish_update(transport, state),
        Command::Reboot => handle_reboot(transport),
        Command::SetActiveBank { bank } => handle_set_active_bank(transport, state, bank),
        Command::WipeAll => handle_wipe_all(transport, state),
    }
}

/// Handle `GetStatus` command: return current bootloader status.
fn handle_get_status(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    let bd = flash::read_boot_data();
    let _ = transport.send(&Response::Status {
        active_bank: bd.active_bank,
        version_a: bd.version_a,
        version_b: bd.version_b,
        state: state.as_boot_state(),
        bootloader_version: parse_semver(BOOTLOADER_VERSION),
    });
    state
}

/// Handle `StartUpdate` command: validate parameters, erase bank, begin receiving.
fn handle_start_update(
    transport: &mut UsbTransport,
    state: UpdateState,
    bank: u8,
    size: u32,
    crc32: u32,
    version: u32,
) -> UpdateState {
    if !matches!(state, UpdateState::Ready) {
        return reject_with(transport, AckStatus::BadState, state);
    }

    let max_buffer_size = storage::fw_ram_buffer_size();
    let Some(bank_addr) = bank_addr(bank) else {
        return reject_with(transport, AckStatus::BankInvalid, state);
    };

    if size == 0 || size > max_buffer_size {
        defmt::warn!(
            "Firmware size {} exceeds RAM buffer {}",
            size,
            max_buffer_size
        );
        return reject_with(transport, AckStatus::BankInvalid, state);
    }

    if size > FW_BANK_SIZE {
        return reject_with(transport, AckStatus::BankInvalid, state);
    }

    defmt::println!(
        "StartUpdate: bank={}, size={}, will buffer in RAM",
        bank,
        size
    );
    send_ack(transport, AckStatus::Ok);

    UpdateState::ReceivingData {
        bank,
        bank_addr,
        expected_size: size,
        expected_crc: crc32,
        version,
        bytes_received: 0,
    }
}

/// Handle `DataBlock` command: validate offset and append data to the RAM buffer.
fn handle_data_block(
    transport: &mut UsbTransport,
    mut state: UpdateState,
    offset: u32,
    data: &[u8],
) -> UpdateState {
    defmt::trace!("DataBlock: offset={}, data_len={}", offset, data.len());

    let UpdateState::ReceivingData {
        ref mut bytes_received,
        expected_size,
        ..
    } = state
    else {
        defmt::warn!("handle_data_block: BadState");
        return reject_with(transport, AckStatus::BadState, state);
    };

    if offset != *bytes_received {
        defmt::warn!(
            "handle_data_block: BadOffset {} != {}",
            offset,
            *bytes_received
        );
        return reject_with(transport, AckStatus::BadCommand, state);
    }

    let data_len = u32::try_from(data.len())
        .unwrap_or_else(|_| unreachable!("data block length always fits in u32"));
    if *bytes_received + data_len > expected_size {
        defmt::warn!("handle_data_block: Size overflow");
        return reject_with(transport, AckStatus::BadCommand, state);
    }

    storage::copy_to_ram_buffer(*bytes_received as usize, data);
    *bytes_received += data_len;

    send_ack(transport, AckStatus::Ok);
    state
}

/// Handle `FinishUpdate` command: persist RAM buffer to flash, verify CRC, update `BootData`.
fn handle_finish_update(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    let UpdateState::ReceivingData {
        bank,
        bank_addr,
        expected_size,
        expected_crc,
        version,
        bytes_received,
    } = state
    else {
        return reject_with(transport, AckStatus::BadState, state);
    };

    if bytes_received != expected_size {
        defmt::warn!(
            "FinishUpdate: Incomplete data {} != {}",
            bytes_received,
            expected_size
        );
        send_ack(transport, AckStatus::BadCommand);
        return UpdateState::ReceivingData {
            bank,
            bank_addr,
            expected_size,
            expected_crc,
            version,
            bytes_received,
        };
    }

    defmt::println!("FinishUpdate: Verifying CRC of RAM buffer");
    let ram_crc = storage::compute_ram_crc32(expected_size);

    if ram_crc != expected_crc {
        defmt::warn!(
            "FinishUpdate: CRC mismatch in RAM: expected 0x{:08x}, got 0x{:08x}",
            expected_crc,
            ram_crc
        );
        send_ack(transport, AckStatus::CrcError);
        return UpdateState::Ready;
    }

    defmt::println!("FinishUpdate: CRC OK, persisting to flash...");
    unsafe { storage::persist_ram_to_flash(bank_addr, expected_size) };

    defmt::println!("FinishUpdate: Flash write complete, verifying...");

    let flash_crc = flash::compute_crc32(bank_addr, expected_size);
    if flash_crc != expected_crc {
        defmt::error!(
            "FinishUpdate: Flash CRC mismatch: expected 0x{:08x}, got 0x{:08x}",
            expected_crc,
            flash_crc
        );
        send_ack(transport, AckStatus::CrcError);
        return UpdateState::Ready;
    }

    let mut bd = flash::read_boot_data();
    bd.active_bank = bank;
    bd.confirmed = 0;
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

    send_ack(transport, AckStatus::Ok);
    UpdateState::Ready
}

/// Handle `Reboot` command: send ACK and reset the system.
fn handle_reboot(transport: &mut UsbTransport) -> ! {
    send_ack(transport, AckStatus::Ok);
    cortex_m::asm::delay(12_000_000);
    cortex_m::peripheral::SCB::sys_reset();
}

/// Handle `SetActiveBank` command: change the active bank for next boot.
fn handle_set_active_bank(
    transport: &mut UsbTransport,
    state: UpdateState,
    bank: u8,
) -> UpdateState {
    if !matches!(state, UpdateState::Ready) {
        return reject_with(transport, AckStatus::BadState, state);
    }

    let Some(bank_addr) = bank_addr(bank) else {
        return reject_with(transport, AckStatus::BankInvalid, state);
    };

    let mut bd = flash::read_boot_data();
    let Some((size, crc)) = bank_firmware_info(&bd, bank) else {
        return reject_with(transport, AckStatus::BankInvalid, state);
    };

    if size == 0 {
        defmt::println!("SetActiveBank: bank {} has no firmware", bank);
        return reject_with(transport, AckStatus::BankInvalid, state);
    }

    let actual_crc = flash::compute_crc32(bank_addr, size);
    if actual_crc != crc {
        defmt::println!(
            "SetActiveBank: bank {} CRC mismatch (expected 0x{:08x}, got 0x{:08x})",
            bank,
            crc,
            actual_crc
        );
        return reject_with(transport, AckStatus::CrcError, state);
    }

    bd.active_bank = bank;
    bd.confirmed = 0;
    bd.boot_attempts = 0;

    unsafe {
        flash::write_boot_data(&bd);
    }

    defmt::println!("SetActiveBank: switched to bank {}", bank);
    send_ack(transport, AckStatus::Ok);
    state
}

fn handle_wipe_all(transport: &mut UsbTransport, state: UpdateState) -> UpdateState {
    if !matches!(state, UpdateState::Ready) {
        return reject_with(transport, AckStatus::BadState, state);
    }

    defmt::println!("Resetting boot data");
    unsafe {
        flash::write_boot_data(&BootData::default_new());
    }

    send_ack(transport, AckStatus::Ok);
    state
}
