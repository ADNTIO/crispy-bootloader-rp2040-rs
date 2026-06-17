// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Ed25519 firmware signing and verification.
//!
//! - The **device** (bootloader) only ever *verifies*: it embeds a 32-byte
//!   public key and checks a 64-byte signature over the firmware image. This
//!   path is `no_std` and pulls in `ed25519-dalek` with `default-features = false`.
//! - The **host** tools additionally *sign* (and derive a public key from a
//!   32-byte secret seed). These helpers are gated behind the `std` feature so
//!   the device binary never links the signing code.
//!
//! The message that is signed/verified is the raw firmware image (exactly the
//! `size` bytes that get copied to RAM and written to a bank).

use crate::protocol::{ED25519_PUBLIC_KEY_LEN, ED25519_SIGNATURE_LEN};

use ed25519_dalek::{Signature, VerifyingKey};

/// Verify an Ed25519 signature over `message` using `public_key`.
///
/// Returns `true` only if the signature is valid. Uses `verify_strict` to
/// reject malleable / non-canonical signatures and small-order public keys.
pub fn verify(
    public_key: &[u8; ED25519_PUBLIC_KEY_LEN],
    message: &[u8],
    signature: &[u8; ED25519_SIGNATURE_LEN],
) -> bool {
    let Ok(verifying_key) = VerifyingKey::from_bytes(public_key) else {
        return false;
    };
    let signature = Signature::from_bytes(signature);
    verifying_key.verify_strict(message, &signature).is_ok()
}

/// Convenience wrapper accepting byte slices of arbitrary length.
///
/// Returns `false` if the key or signature do not have the expected length.
pub fn verify_slices(public_key: &[u8], message: &[u8], signature: &[u8]) -> bool {
    let Ok(pk) = <&[u8; ED25519_PUBLIC_KEY_LEN]>::try_from(public_key) else {
        return false;
    };
    let Ok(sig) = <&[u8; ED25519_SIGNATURE_LEN]>::try_from(signature) else {
        return false;
    };
    verify(pk, message, sig)
}

/// Length of the secret seed used to derive an Ed25519 key pair.
///
/// Signing/key-derivation are only used by the host tools. The device only ever
/// links [`verify`]; dead-code elimination drops the signing path from the
/// bootloader binary, so these helpers do not need to be feature-gated.
pub const ED25519_SEED_LEN: usize = 32;

/// Derive the 32-byte public key from a 32-byte secret seed.
pub fn public_key_from_seed(seed: &[u8; ED25519_SEED_LEN]) -> [u8; ED25519_PUBLIC_KEY_LEN] {
    use ed25519_dalek::SigningKey;
    SigningKey::from_bytes(seed).verifying_key().to_bytes()
}

/// Sign `message` with the key pair derived from `seed`.
pub fn sign(seed: &[u8; ED25519_SEED_LEN], message: &[u8]) -> [u8; ED25519_SIGNATURE_LEN] {
    use ed25519_dalek::{Signer, SigningKey};
    SigningKey::from_bytes(seed).sign(message).to_bytes()
}
