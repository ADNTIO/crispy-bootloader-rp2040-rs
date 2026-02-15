// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Unit tests for BootData structure and methods.

use crispy_common::protocol::{BootData, BOOT_DATA_MAGIC, FW_A_ADDR, FW_B_ADDR};

#[test]
fn test_boot_data_default_new() {
    let bd = BootData::default_new();

    assert_eq!(bd.magic, BOOT_DATA_MAGIC);
    assert_eq!(bd.active_bank, 0);
    assert_eq!(bd.confirmed, 0);
    assert_eq!(bd.boot_attempts, 0);
    assert_eq!(bd.version_a, 0);
    assert_eq!(bd.version_b, 0);
    assert_eq!(bd.crc_a, 0);
    assert_eq!(bd.crc_b, 0);
    assert_eq!(bd.size_a, 0);
    assert_eq!(bd.size_b, 0);
}

#[test]
fn test_boot_data_is_valid() {
    let mut bd = BootData::default_new();
    assert!(bd.is_valid());

    bd.magic = 0;
    assert!(!bd.is_valid());

    bd.magic = 0xDEADBEEF;
    assert!(!bd.is_valid());
}

#[test]
fn test_boot_data_bank_addr_bank_a() {
    let mut bd = BootData::default_new();
    bd.active_bank = 0;

    assert_eq!(bd.bank_addr(), FW_A_ADDR);
}

#[test]
fn test_boot_data_bank_addr_bank_b() {
    let mut bd = BootData::default_new();
    bd.active_bank = 1;

    assert_eq!(bd.bank_addr(), FW_B_ADDR);
}

#[test]
fn test_boot_data_as_bytes_length() {
    let bd = BootData::default_new();
    let bytes = bd.as_bytes();

    assert_eq!(bytes.len(), 32);
}

#[test]
fn test_boot_data_as_bytes_magic() {
    let bd = BootData::default_new();
    let bytes = bd.as_bytes();

    // Magic is at the start, little-endian
    let magic = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
    assert_eq!(magic, BOOT_DATA_MAGIC);
}

#[test]
fn test_boot_data_size_is_32_bytes() {
    assert_eq!(std::mem::size_of::<BootData>(), 32);
}
