// Copyright (c) 2026 ADNT Sarl <info@adnt.io>
// SPDX-License-Identifier: MIT

use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let linker_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .parent()
        .unwrap()
        .join("linker_scripts");

    let linker_script =
        fs::read_to_string(linker_dir.join("fw_rp2040.x")).expect("Failed to read fw_rp2040.x");
    fs::write(out_dir.join("memory.x"), linker_script).expect("Failed to write memory.x");

    println!("cargo:rustc-link-search={}", out_dir.display());
    println!("cargo:rustc-link-arg=-Tlink.x");
    println!("cargo:rustc-link-arg=-Tdefmt.x");
    println!(
        "cargo:rerun-if-changed={}",
        linker_dir.join("fw_rp2040.x").display()
    );
    println!("cargo:rerun-if-changed=build.rs");

    // Read version from project-root VERSION file
    let version_file = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .parent()
        .unwrap()
        .join("VERSION");
    let version = fs::read_to_string(&version_file)
        .expect("Failed to read VERSION file")
        .trim()
        .to_string();
    println!("cargo:rustc-env=CRISPY_VERSION={}", version);
    println!("cargo:rerun-if-changed={}", version_file.display());
}
