// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Firmware signature verification for the bootloader.
//!
//! The 32-byte Ed25519 public key is embedded at build time (see `build.rs`).
//! Verification is performed at upload time over the firmware image buffered in
//! RAM, before it is committed to flash.

use crispy_common::protocol::{ED25519_PUBLIC_KEY_LEN, ED25519_SIGNATURE_LEN};

/// Whether unsigned firmware uploads are accepted.
///
/// Enabled by the default `allow-unsigned` feature for development. Build the
/// bootloader with `--no-default-features` for a signature-only (secure) build.
pub const ALLOW_UNSIGNED: bool = cfg!(feature = "allow-unsigned");

/// Ed25519 public key embedded by `build.rs` (`OUT_DIR/public_key.bin`).
pub static PUBLIC_KEY: [u8; ED25519_PUBLIC_KEY_LEN] =
    *include_bytes!(concat!(env!("OUT_DIR"), "/public_key.bin"));

/// Verify an Ed25519 `signature` over `message` using the embedded public key.
pub fn verify_firmware(message: &[u8], signature: &[u8; ED25519_SIGNATURE_LEN]) -> bool {
    crispy_common::crypto::verify(&PUBLIC_KEY, message, signature)
}
