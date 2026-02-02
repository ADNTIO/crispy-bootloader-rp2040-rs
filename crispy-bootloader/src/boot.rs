// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

const BOOT_DATA_MAGIC: u32 = 0xB007_DA7A;
const RAM_START: u32 = 0x2000_0000;
const RAM_END: u32 = 0x2004_0000;

unsafe extern "C" {
    static __fw_a_entry: u32;
    static __fw_b_entry: u32;
    static __fw_ram_base: u32;
    static __fw_copy_size: u32;
    static __boot_data_addr: u32;
}

macro_rules! linker_addr {
    ($sym:ident) => {
        unsafe { &$sym as *const u32 as u32 }
    };
}

pub struct MemoryLayout {
    pub fw_a: u32,
    pub fw_b: u32,
    pub ram_base: u32,
    pub copy_size: u32,
    pub boot_data: u32,
}

impl MemoryLayout {
    pub fn from_linker() -> Self {
        Self {
            fw_a: linker_addr!(__fw_a_entry),
            fw_b: linker_addr!(__fw_b_entry),
            ram_base: linker_addr!(__fw_ram_base),
            copy_size: linker_addr!(__fw_copy_size),
            boot_data: linker_addr!(__boot_data_addr),
        }
    }
}

struct VectorTable {
    initial_sp: u32,
    reset_vector: u32,
}

impl VectorTable {
    unsafe fn read_from(addr: u32) -> Self {
        Self {
            initial_sp: (addr as *const u32).read_volatile(),
            reset_vector: (addr as *const u32).offset(1).read_volatile(),
        }
    }

    fn is_valid_for_ram_execution(&self) -> bool {
        is_in_ram(self.initial_sp) && is_in_ram(self.reset_vector)
    }
}

fn is_in_ram(addr: u32) -> bool {
    (RAM_START..RAM_END).contains(&addr)
}

fn read_volatile_u32(addr: u32) -> u32 {
    unsafe { (addr as *const u32).read_volatile() }
}

fn read_volatile_u8(addr: u32) -> u8 {
    unsafe { (addr as *const u8).read_volatile() }
}

pub fn read_boot_data(addr: u32) -> Option<u8> {
    if read_volatile_u32(addr) == BOOT_DATA_MAGIC {
        Some(read_volatile_u8(addr + 4))
    } else {
        None
    }
}

pub fn validate_bank(flash_addr: u32) -> Option<(u32, u32)> {
    let vt = unsafe { VectorTable::read_from(flash_addr) };
    if vt.is_valid_for_ram_execution() {
        Some((vt.initial_sp, vt.reset_vector))
    } else {
        None
    }
}

/// # Safety
/// Caller must ensure `flash_addr` and `layout` are valid.
pub unsafe fn load_and_jump(flash_addr: u32, layout: &MemoryLayout) -> ! {
    copy_firmware_to_ram(flash_addr, layout);
    relocate_vector_table(layout.ram_base);

    let vt = VectorTable::read_from(layout.ram_base);
    jump_to_firmware(vt.initial_sp, vt.reset_vector);
}

unsafe fn copy_firmware_to_ram(flash_addr: u32, layout: &MemoryLayout) {
    core::ptr::copy_nonoverlapping(
        flash_addr as *const u32,
        layout.ram_base as *mut u32,
        layout.copy_size as usize / 4,
    );
}

unsafe fn relocate_vector_table(ram_base: u32) {
    cortex_m::interrupt::disable();

    const SCB_VTOR: *mut u32 = 0xE000_ED08 as *mut u32;
    SCB_VTOR.write_volatile(ram_base);

    cortex_m::asm::dsb();
    cortex_m::asm::isb();
}

unsafe fn jump_to_firmware(initial_sp: u32, reset_vector: u32) -> ! {
    core::arch::asm!(
        "msr msp, {sp}",
        "bx {reset}",
        sp = in(reg) initial_sp,
        reset = in(reg) reset_vector,
        options(noreturn)
    );
}
