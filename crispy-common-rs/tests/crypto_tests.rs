// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Round-trip and negative tests for Ed25519 firmware signing/verification.

#![cfg(feature = "crypto")]

use crispy_common::crypto::{public_key_from_seed, sign, verify, verify_slices};

const SEED: [u8; 32] = [
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10,
    0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20,
];

#[test]
fn sign_then_verify_roundtrip() {
    let message = b"crispy firmware image bytes";
    let public_key = public_key_from_seed(&SEED);
    let signature = sign(&SEED, message);

    assert!(verify(&public_key, message, &signature));
    assert!(verify_slices(&public_key, message, &signature));
}

#[test]
fn tampered_message_is_rejected() {
    let message = b"crispy firmware image bytes";
    let public_key = public_key_from_seed(&SEED);
    let signature = sign(&SEED, message);

    let mut tampered = message.to_vec();
    tampered[0] ^= 0xFF;
    assert!(!verify(&public_key, &tampered, &signature));
}

#[test]
fn wrong_public_key_is_rejected() {
    let message = b"crispy firmware image bytes";
    let signature = sign(&SEED, message);

    let mut other_seed = SEED;
    other_seed[0] ^= 0xFF;
    let wrong_key = public_key_from_seed(&other_seed);
    assert!(!verify(&wrong_key, message, &signature));
}

#[test]
fn empty_or_wrong_length_inputs_are_rejected() {
    let message = b"crispy firmware image bytes";
    let public_key = public_key_from_seed(&SEED);
    let signature = sign(&SEED, message);

    // Wrong-length public key / signature slices must not verify.
    assert!(!verify_slices(&public_key[..31], message, &signature));
    assert!(!verify_slices(&public_key, message, &signature[..63]));
    // All-zero signature must not verify against a real key.
    assert!(!verify(&public_key, message, &[0u8; 64]));
}
