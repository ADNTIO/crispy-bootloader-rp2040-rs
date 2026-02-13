// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

use crate::flash;
use crc::{Crc, CRC_32_ISO_HDLC};
use crispy_common::protocol::{FLASH_PAGE_SIZE, FLASH_SECTOR_SIZE};

const CRC32: Crc<u32> = Crc::<u32>::new(&CRC_32_ISO_HDLC);
const FLASH_PROGRAM_BATCH_SIZE: u32 = FLASH_SECTOR_SIZE;

unsafe extern "C" {
    static __fw_ram_base: u8;
    static __fw_copy_size: u32;
}

/// Base pointer for firmware RAM region exported by linker script (`__fw_ram_base`).
#[inline]
fn fw_ram_buffer_ptr() -> *mut u8 {
    core::ptr::addr_of!(__fw_ram_base).cast_mut()
}

/// Buffer size exported by linker script (`__fw_copy_size`).
///
/// `__fw_copy_size` is an absolute symbol, so its address is the value.
#[inline]
pub(super) fn fw_ram_buffer_size() -> u32 {
    core::ptr::addr_of!(__fw_copy_size) as usize as u32
}

pub(super) fn compute_ram_crc32(size: u32) -> u32 {
    let mut digest = CRC32.digest();
    let ram_base = fw_ram_buffer_ptr();
    let ram_slice = unsafe { core::slice::from_raw_parts(ram_base.cast_const(), size as usize) };
    digest.update(ram_slice);
    digest.finalize()
}

pub(super) fn copy_to_ram_buffer(offset: usize, data: &[u8]) {
    let ram_base = fw_ram_buffer_ptr();
    unsafe {
        core::ptr::copy_nonoverlapping(data.as_ptr(), ram_base.add(offset), data.len());
    }
}

/// Persist RAM firmware buffer into flash.
///
/// # Safety
/// `bank_addr` must point to a valid writable firmware bank and `size` must be validated.
pub(super) unsafe fn persist_ram_to_flash(bank_addr: u32, size: u32) {
    let flash_offset = flash::addr_to_offset(bank_addr);
    let ram_base = fw_ram_buffer_ptr();
    let erase_size = size.div_ceil(FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE;
    flash::flash_erase(flash_offset, erase_size);

    // Program full pages in larger batches to reduce XIP enter/exit overhead.
    let full_page_bytes = (size / FLASH_PAGE_SIZE) * FLASH_PAGE_SIZE;
    let mut offset = 0u32;
    while offset < full_page_bytes {
        let chunk = (full_page_bytes - offset).min(FLASH_PROGRAM_BATCH_SIZE);
        flash::flash_program(
            flash_offset + offset,
            ram_base.add(offset as usize).cast_const(),
            chunk as usize,
        );
        offset += chunk;
    }

    // Program trailing partial page padded with 0xFF to avoid writing stale RAM bytes.
    let trailing_bytes = size - full_page_bytes;
    if trailing_bytes > 0 {
        let mut last_page = [0xFFu8; FLASH_PAGE_SIZE as usize];
        core::ptr::copy_nonoverlapping(
            ram_base.add(full_page_bytes as usize),
            last_page.as_mut_ptr(),
            trailing_bytes as usize,
        );
        flash::flash_program(
            flash_offset + full_page_bytes,
            last_page.as_ptr(),
            last_page.len(),
        );
    }
}
