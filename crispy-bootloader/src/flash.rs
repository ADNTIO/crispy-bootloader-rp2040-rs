// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Flash read/write/erase wrappers using RP2040 ROM routines.
//!
//! On RP2040, flash operations (erase/program) require disabling XIP first.
//! The full sequence is:
//!   1. connect_internal_flash()
//!   2. flash_exit_xip()
//!   3. flash_range_erase() or flash_range_program()
//!   4. flash_flush_cache()
//!   5. flash_enter_cmd_xip()
//!
//! All code executing during steps 1-5 must run from RAM, not flash.
//! We use `#[link_section = ".data"]` to place critical functions in RAM,
//! and pre-resolve all ROM function pointers at init time.

use core::sync::atomic::{AtomicUsize, Ordering};
use crc::{Crc, CRC_32_ISO_HDLC};
use crispy_common::protocol::{
    BootData, BOOT_DATA_ADDR, FLASH_BASE, FLASH_PAGE_SIZE, FLASH_SECTOR_SIZE,
};

const CRC32: Crc<u32> = Crc::<u32>::new(&CRC_32_ISO_HDLC);

// RP2040 ROM table addresses (defined in RP2040 datasheet section 2.8.3)
/// Pointer to the ROM function table (16-bit pointer stored at 0x14)
const ROM_FUNC_TABLE_PTR: *const u16 = 0x0000_0014 as *const u16;
/// Pointer to the ROM table lookup function (16-bit pointer stored at 0x18)
const ROM_TABLE_LOOKUP_PTR: *const u16 = 0x0000_0018 as *const u16;

// ROM function pointer types
type RomFnVoid = unsafe extern "C" fn();
type RomFnErase = unsafe extern "C" fn(u32, usize, u32, u8);
type RomFnProgram = unsafe extern "C" fn(u32, *const u8, usize);

/// ROM function pointers, resolved once at init from the ROM table.
/// Using AtomicUsize for thread-safe initialization without static mut.
static ROM_CONNECT_INTERNAL_FLASH: AtomicUsize = AtomicUsize::new(0);
static ROM_FLASH_EXIT_XIP: AtomicUsize = AtomicUsize::new(0);
static ROM_FLASH_RANGE_ERASE: AtomicUsize = AtomicUsize::new(0);
static ROM_FLASH_RANGE_PROGRAM: AtomicUsize = AtomicUsize::new(0);
static ROM_FLASH_FLUSH_CACHE: AtomicUsize = AtomicUsize::new(0);
static ROM_FLASH_ENTER_CMD_XIP: AtomicUsize = AtomicUsize::new(0);

/// Look up a ROM function by its two-character tag.
/// Uses RP2040 ROM table as documented in datasheet section 2.8.3.
unsafe fn rom_func_lookup(tag: &[u8; 2]) -> usize {
    // Read function table pointer (stored as 16-bit value)
    let fn_table = *ROM_FUNC_TABLE_PTR as *const u16;

    // Read and call the ROM table lookup function
    let lookup: unsafe extern "C" fn(*const u16, u32) -> usize =
        core::mem::transmute::<usize, unsafe extern "C" fn(*const u16, u32) -> usize>(
            *ROM_TABLE_LOOKUP_PTR as usize,
        );

    let code = u16::from_le_bytes(*tag) as u32;
    lookup(fn_table, code)
}

/// Initialize ROM flash function pointers. Must be called once before any flash operations.
/// This performs ROM table lookups which require XIP to be active.
pub fn init() {
    unsafe {
        ROM_CONNECT_INTERNAL_FLASH.store(rom_func_lookup(b"IF"), Ordering::Release);
        ROM_FLASH_EXIT_XIP.store(rom_func_lookup(b"EX"), Ordering::Release);
        ROM_FLASH_RANGE_ERASE.store(rom_func_lookup(b"RE"), Ordering::Release);
        ROM_FLASH_RANGE_PROGRAM.store(rom_func_lookup(b"RP"), Ordering::Release);
        ROM_FLASH_FLUSH_CACHE.store(rom_func_lookup(b"FC"), Ordering::Release);
        ROM_FLASH_ENTER_CMD_XIP.store(rom_func_lookup(b"CX"), Ordering::Release);
    }
}

/// Convert an absolute XIP flash address to a flash-relative offset.
pub fn addr_to_offset(abs_addr: u32) -> u32 {
    abs_addr - FLASH_BASE
}

/// Erase flash at the given flash-relative offset.
/// Runs entirely from RAM with proper XIP teardown/setup.
///
/// # Safety
/// The `init()` function must have been called first.
#[link_section = ".data"]
#[inline(never)]
pub unsafe fn flash_erase(offset: u32, size: u32) {
    let connect: RomFnVoid = core::mem::transmute(ROM_CONNECT_INTERNAL_FLASH.load(Ordering::Acquire));
    let exit_xip: RomFnVoid = core::mem::transmute(ROM_FLASH_EXIT_XIP.load(Ordering::Acquire));
    let erase: RomFnErase = core::mem::transmute(ROM_FLASH_RANGE_ERASE.load(Ordering::Acquire));
    let flush: RomFnVoid = core::mem::transmute(ROM_FLASH_FLUSH_CACHE.load(Ordering::Acquire));
    let enter_xip: RomFnVoid = core::mem::transmute(ROM_FLASH_ENTER_CMD_XIP.load(Ordering::Acquire));

    cortex_m::interrupt::disable();
    connect();
    exit_xip();
    erase(offset, size as usize, FLASH_SECTOR_SIZE, 0x20);
    flush();
    enter_xip();
    cortex_m::interrupt::enable();
}

/// Program flash at the given flash-relative offset.
/// Runs entirely from RAM with proper XIP teardown/setup.
///
/// # Safety
/// The `init()` function must have been called first.
#[link_section = ".data"]
#[inline(never)]
pub unsafe fn flash_program(offset: u32, data: *const u8, len: usize) {
    let connect: RomFnVoid = core::mem::transmute(ROM_CONNECT_INTERNAL_FLASH.load(Ordering::Acquire));
    let exit_xip: RomFnVoid = core::mem::transmute(ROM_FLASH_EXIT_XIP.load(Ordering::Acquire));
    let program: RomFnProgram = core::mem::transmute(ROM_FLASH_RANGE_PROGRAM.load(Ordering::Acquire));
    let flush: RomFnVoid = core::mem::transmute(ROM_FLASH_FLUSH_CACHE.load(Ordering::Acquire));
    let enter_xip: RomFnVoid = core::mem::transmute(ROM_FLASH_ENTER_CMD_XIP.load(Ordering::Acquire));

    cortex_m::interrupt::disable();
    connect();
    exit_xip();
    program(offset, data, len);
    flush();
    enter_xip();
    cortex_m::interrupt::enable();
}

/// Read bytes from an absolute XIP flash address via volatile reads.
pub fn flash_read(abs_addr: u32, buf: &mut [u8]) {
    for (i, byte) in buf.iter_mut().enumerate() {
        *byte = unsafe { ((abs_addr + i as u32) as *const u8).read_volatile() };
    }
}

/// Compute CRC-32 (ISO HDLC) over flash data at the given absolute address.
pub fn compute_crc32(abs_addr: u32, size: u32) -> u32 {
    let mut digest = CRC32.digest();
    let mut remaining = size as usize;
    let mut addr = abs_addr;
    let mut chunk = [0u8; 256];

    while remaining > 0 {
        let n = remaining.min(chunk.len());
        flash_read(addr, &mut chunk[..n]);
        digest.update(&chunk[..n]);
        addr += n as u32;
        remaining -= n;
    }

    digest.finalize()
}

/// Read BootData from flash. Returns default if magic is invalid.
pub fn read_boot_data() -> BootData {
    let bd = unsafe { BootData::read_from(BOOT_DATA_ADDR) };
    if bd.is_valid() {
        bd
    } else {
        BootData::default_new()
    }
}

/// Write BootData to flash (erase sector, then program padded to 256B page).
///
/// # Safety
/// The `init()` function must have been called first.
pub unsafe fn write_boot_data(bd: &BootData) {
    let offset = addr_to_offset(BOOT_DATA_ADDR);

    // Erase the 4KB sector containing boot data
    flash_erase(offset, FLASH_SECTOR_SIZE);

    // Pad to a full 256-byte page
    let mut page = [0xFFu8; FLASH_PAGE_SIZE as usize];
    let src = bd.as_bytes();
    page[..src.len()].copy_from_slice(src);

    flash_program(offset, page.as_ptr(), page.len());
}
