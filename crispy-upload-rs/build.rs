use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
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
