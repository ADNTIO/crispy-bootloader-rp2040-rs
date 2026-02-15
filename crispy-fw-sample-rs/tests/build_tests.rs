// Copyright (c) 2026 ADNT Sàrl <info@adnt.io>
// SPDX-License-Identifier: MIT

//! Build sanity tests for crispy-fw-sample-rs.

#[test]
fn test_firmware_builds() {
    // If this test compiles and runs, the firmware crate and its
    // dependencies are correctly configured.
    assert!(true);
}

#[test]
fn test_workspace_structure() {
    assert!(
        std::path::Path::new("../crispy-common-rs").exists(),
        "crispy-common-rs crate should exist"
    );
    assert!(
        std::path::Path::new("Cargo.toml").exists(),
        "Cargo.toml should exist"
    );
    assert!(
        std::path::Path::new("src/main.rs").exists(),
        "src/main.rs should exist"
    );
}
