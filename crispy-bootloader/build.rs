use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let linker_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .parent()
        .unwrap()
        .join("linker_scripts");

    let linker_script = fs::read_to_string(linker_dir.join("bootloader_rp2040.x"))
        .expect("Failed to read bootloader_rp2040.x");
    fs::write(out_dir.join("memory.x"), linker_script).expect("Failed to write memory.x");
    println!("cargo:rustc-link-search={}", out_dir.display());
    println!("cargo:rustc-link-arg=-Tlink.x");
    println!("cargo:rustc-link-arg=-Tdefmt.x");
    println!(
        "cargo:rerun-if-changed={}",
        linker_dir.join("bootloader_rp2040.x").display()
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

    // Embed the Ed25519 public key used to verify firmware signatures.
    embed_public_key(&out_dir);
}

/// Resolve the firmware-signing public key and copy it to `OUT_DIR/public_key.bin`
/// so it can be `include_bytes!`-ed by the bootloader.
///
/// Resolution order:
///   1. `CRISPY_PUBLIC_KEY_FILE` environment variable (path to a 32-byte key)
///   2. `keys/public_key.bin` at the project root
///   3. `keys/public_key.bin.example` (all-zero placeholder; prints a warning)
fn embed_public_key(out_dir: &std::path::Path) {
    const KEY_LEN: usize = 32;

    let keys_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .parent()
        .unwrap()
        .join("keys");

    let (key_path, is_placeholder) = match env::var("CRISPY_PUBLIC_KEY_FILE") {
        Ok(path) => (PathBuf::from(path), false),
        Err(_) => {
            let real = keys_dir.join("public_key.bin");
            if real.exists() {
                (real, false)
            } else {
                (keys_dir.join("public_key.bin.example"), true)
            }
        }
    };

    let key = fs::read(&key_path)
        .unwrap_or_else(|e| panic!("Failed to read public key {}: {e}", key_path.display()));
    assert_eq!(
        key.len(),
        KEY_LEN,
        "Public key {} must be exactly {KEY_LEN} bytes, got {}",
        key_path.display(),
        key.len()
    );

    if is_placeholder {
        println!(
            "cargo:warning=Using placeholder firmware-signing public key ({}). \
             No signature can be valid until you run `make keygen`.",
            key_path.display()
        );
    }

    fs::write(out_dir.join("public_key.bin"), &key).expect("Failed to write public_key.bin");
    // Watch both the chosen key and the canonical real-key path so that creating
    // keys/public_key.bin (e.g. via `make keygen`) triggers a rebuild even when
    // the placeholder was used previously.
    println!("cargo:rerun-if-changed={}", key_path.display());
    println!(
        "cargo:rerun-if-changed={}",
        keys_dir.join("public_key.bin").display()
    );
    println!("cargo:rerun-if-env-changed=CRISPY_PUBLIC_KEY_FILE");
}
