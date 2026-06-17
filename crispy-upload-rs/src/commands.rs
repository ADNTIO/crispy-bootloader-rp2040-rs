// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Command implementations for bootloader operations.

use std::fs;
use std::io::Write;
use std::path::Path;

use anyhow::{bail, Context, Result};
use crc::{Crc, CRC_32_ISO_HDLC};
use indicatif::{ProgressBar, ProgressStyle};

use crispy_common::crypto::{public_key_from_seed, sign, ED25519_SEED_LEN};
use crispy_common::protocol::{unpack_semver, AckStatus, Command, Response, SignatureBytes};
use crispy_common::MAX_DATA_BLOCK_SIZE;

use crate::transport::Transport;

const CRC32: Crc<u32> = Crc::<u32>::new(&CRC_32_ISO_HDLC);
const CHUNK_SIZE: usize = MAX_DATA_BLOCK_SIZE;

/// Get and display bootloader status.
pub fn status(transport: &mut Transport) -> Result<()> {
    let response = transport.send_recv(&Command::GetStatus)?;

    match response {
        Response::Status {
            active_bank,
            version_a,
            version_b,
            state,
            bootloader_version,
        } => {
            println!("Bootloader Status:");
            if let Some(version) = bootloader_version {
                let (major, minor, patch) = unpack_semver(version);
                println!("  Bootloader:  {}.{}.{}", major, minor, patch);
            } else {
                println!("  Bootloader:  unknown");
            }
            println!(
                "  Active bank: {} ({})",
                active_bank,
                if active_bank == 0 { "A" } else { "B" }
            );
            println!("  Version A:   {}", version_a);
            println!("  Version B:   {}", version_b);
            println!("  State:       {:?}", state);
        }
        Response::Ack(status) => {
            println!("Unexpected ACK response: {:?}", status);
        }
    }

    Ok(())
}

/// Upload firmware to the specified bank.
///
/// If `key_path` is provided, the firmware is signed with the Ed25519 private
/// key (32-byte seed) and sent via `StartUpdateSigned`. Otherwise it is sent
/// unsigned via `StartUpdate` (only accepted by `allow-unsigned` builds).
pub fn upload(
    transport: &mut Transport,
    file: &Path,
    bank: u8,
    version: u32,
    key_path: Option<&Path>,
) -> Result<()> {
    // Read firmware file
    let firmware = fs::read(file).with_context(|| format!("Failed to read {}", file.display()))?;
    let size = firmware.len() as u32;
    let crc32 = CRC32.checksum(&firmware);

    println!(
        "Firmware: {} ({} bytes, CRC32: 0x{:08x})",
        file.display(),
        size,
        crc32
    );
    println!(
        "Target:   Bank {} ({})",
        bank,
        if bank == 0 { "A" } else { "B" }
    );
    println!("Version:  {}", version);

    // Build the start command, signing the firmware if a key was provided.
    let start_command = match key_path {
        Some(path) => {
            let seed = read_seed(path)?;
            let signature = sign(&seed, &firmware);
            println!("Signing:  Ed25519 (signed)");
            Command::StartUpdateSigned {
                bank,
                size,
                crc32,
                version,
                signature: SignatureBytes::from_slice(&signature)
                    .map_err(|_| anyhow::anyhow!("signature length mismatch"))?,
            }
        }
        None => {
            println!("Signing:  none (unsigned upload)");
            Command::StartUpdate {
                bank,
                size,
                crc32,
                version,
            }
        }
    };
    println!();

    // Start update (includes erasing the target bank - can take 30+ seconds)
    print!("Starting update (erasing bank)... ");
    std::io::stdout().flush()?;

    let response = transport.send_recv_timeout(
        &start_command,
        60_000, // 60 second timeout for bank erase
    )?;

    match response {
        Response::Ack(AckStatus::Ok) => println!("OK"),
        Response::Ack(AckStatus::SignatureRequired) => bail!(
            "Bootloader requires a signed firmware. Re-run with --key <PRIVATE_KEY>."
        ),
        Response::Ack(status) => bail!("StartUpdate failed: {:?}", status),
        _ => bail!("Unexpected response: {:?}", response),
    }

    // Send data blocks
    let pb = ProgressBar::new(size as u64);
    pb.set_style(
        ProgressStyle::default_bar()
            .template(
                "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})",
            )?
            .progress_chars("#>-"),
    );

    for (i, chunk) in firmware.chunks(CHUNK_SIZE).enumerate() {
        let offset = (i * CHUNK_SIZE) as u32;
        let response = transport.send_recv(&Command::DataBlock {
            offset,
            data: chunk.to_vec(),
        })?;

        match response {
            Response::Ack(AckStatus::Ok) => {}
            Response::Ack(status) => {
                pb.abandon();
                bail!("DataBlock failed at offset {}: {:?}", offset, status);
            }
            _ => {
                pb.abandon();
                bail!("Unexpected response at offset {}: {:?}", offset, response);
            }
        }

        pb.set_position(offset as u64 + chunk.len() as u64);
    }

    pb.finish_with_message("Upload complete");
    println!();

    // Finish update
    print!("Finalizing... ");
    std::io::stdout().flush()?;

    let response = transport.send_recv(&Command::FinishUpdate)?;

    match response {
        Response::Ack(AckStatus::Ok) => println!("OK"),
        Response::Ack(AckStatus::CrcError) => bail!("CRC verification failed!"),
        Response::Ack(AckStatus::SignatureInvalid) => {
            bail!("Signature verification failed (wrong key or tampered firmware)!")
        }
        Response::Ack(status) => bail!("FinishUpdate failed: {:?}", status),
        _ => bail!("Unexpected response: {:?}", response),
    }

    println!();
    println!("Firmware uploaded successfully!");
    println!(
        "Use 'crispy-upload --port {} reboot' to restart the device.",
        transport.port_name()
    );

    Ok(())
}

/// Set the active bank for the next boot.
pub fn set_bank(transport: &mut Transport, bank: u8) -> Result<()> {
    println!(
        "Setting active bank to {} ({})...",
        bank,
        if bank == 0 { "A" } else { "B" }
    );

    let response = transport.send_recv(&Command::SetActiveBank { bank })?;

    match response {
        Response::Ack(AckStatus::Ok) => {
            println!("Active bank set successfully.");
            println!(
                "Use 'crispy-upload --port {} reboot' to restart the device.",
                transport.port_name()
            );
        }
        Response::Ack(AckStatus::BankInvalid) => bail!("Invalid bank: must be 0 (A) or 1 (B)"),
        Response::Ack(AckStatus::CrcError) => {
            bail!("Bank {} has no valid firmware (CRC check failed)", bank)
        }
        Response::Ack(status) => bail!("SetActiveBank failed: {:?}", status),
        _ => bail!("Unexpected response: {:?}", response),
    }

    Ok(())
}

/// Wipe all firmware banks and reset boot data.
pub fn wipe(transport: &mut Transport) -> Result<()> {
    println!("Resetting boot data (invalidates all firmware)...");

    let response = transport.send_recv(&Command::WipeAll)?;

    match response {
        Response::Ack(AckStatus::Ok) => {
            println!("Boot data reset. Firmware banks marked as invalid.");
            println!("Device is now in update mode, ready for firmware upload.");
        }
        Response::Ack(AckStatus::BadState) => {
            bail!("Cannot wipe: device is not in idle state (upload in progress?)")
        }
        Response::Ack(status) => bail!("Wipe failed: {:?}", status),
        _ => bail!("Unexpected response: {:?}", response),
    }

    Ok(())
}

/// Reboot the device.
pub fn reboot(transport: &mut Transport) -> Result<()> {
    print!("Rebooting device... ");
    std::io::stdout().flush()?;

    let response = transport.send_recv(&Command::Reboot)?;

    match response {
        Response::Ack(AckStatus::Ok) => println!("OK"),
        Response::Ack(status) => bail!("Reboot failed: {:?}", status),
        _ => bail!("Unexpected response: {:?}", response),
    }

    Ok(())
}

/// Read a 32-byte Ed25519 secret seed from `path`.
fn read_seed(path: &Path) -> Result<[u8; ED25519_SEED_LEN]> {
    let bytes = fs::read(path)
        .with_context(|| format!("Failed to read private key {}", path.display()))?;
    <[u8; ED25519_SEED_LEN]>::try_from(bytes.as_slice()).map_err(|_| {
        anyhow::anyhow!(
            "Private key {} must be exactly {} bytes, got {}",
            path.display(),
            ED25519_SEED_LEN,
            bytes.len()
        )
    })
}

/// Generate an Ed25519 key pair and write it to `out_dir`.
pub fn keygen(out_dir: &Path, force: bool) -> Result<()> {
    let private_path = out_dir.join("private_key.bin");
    let public_path = out_dir.join("public_key.bin");

    if !force && (private_path.exists() || public_path.exists()) {
        bail!(
            "Key files already exist in {} (use --force to overwrite)",
            out_dir.display()
        );
    }

    fs::create_dir_all(out_dir)
        .with_context(|| format!("Failed to create {}", out_dir.display()))?;

    // Generate a 32-byte secret seed from the OS CSPRNG.
    let mut seed = [0u8; ED25519_SEED_LEN];
    getrandom::getrandom(&mut seed).map_err(|e| anyhow::anyhow!("RNG failure: {e}"))?;
    let public_key = public_key_from_seed(&seed);

    write_key_file(&private_path, &seed)?;
    write_key_file(&public_path, &public_key)?;

    println!("Generated Ed25519 key pair:");
    println!("  Private key: {}", private_path.display());
    println!("  Public key:  {}", public_path.display());
    println!();
    println!("Keep the private key secret. The bootloader's build.rs embeds");
    println!("keys/public_key.bin automatically; rebuild the bootloader to apply.");

    Ok(())
}

/// Write key bytes to `path` with owner-only permissions where supported.
fn write_key_file(path: &Path, bytes: &[u8]) -> Result<()> {
    fs::write(path, bytes).with_context(|| format!("Failed to write {}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(path)?.permissions();
        perms.set_mode(0o600);
        let _ = fs::set_permissions(path, perms);
    }
    Ok(())
}

// UF2 constants
const UF2_MAGIC_START0: u32 = 0x0A324655;
const UF2_MAGIC_START1: u32 = 0x9E5D5157;
const UF2_MAGIC_END: u32 = 0x0AB16F30;
const UF2_FLAG_FAMILY_ID: u32 = 0x00002000;
const UF2_PAYLOAD_SIZE: usize = 256;

/// Convert a raw binary file to UF2 format.
pub fn bin2uf2(input: &Path, output: &Path, base_address: u32, family_id: u32) -> Result<()> {
    let data = fs::read(input).with_context(|| format!("Failed to read {}", input.display()))?;

    let num_blocks = data.len().div_ceil(UF2_PAYLOAD_SIZE);
    let mut out = Vec::with_capacity(num_blocks * 512);

    for i in 0..num_blocks {
        let offset = i * UF2_PAYLOAD_SIZE;
        let end = (offset + UF2_PAYLOAD_SIZE).min(data.len());
        let chunk = &data[offset..end];

        // 32-byte header
        out.extend_from_slice(&UF2_MAGIC_START0.to_le_bytes());
        out.extend_from_slice(&UF2_MAGIC_START1.to_le_bytes());
        out.extend_from_slice(&UF2_FLAG_FAMILY_ID.to_le_bytes());
        out.extend_from_slice(&(base_address + offset as u32).to_le_bytes());
        out.extend_from_slice(&(UF2_PAYLOAD_SIZE as u32).to_le_bytes());
        out.extend_from_slice(&(i as u32).to_le_bytes());
        out.extend_from_slice(&(num_blocks as u32).to_le_bytes());
        out.extend_from_slice(&family_id.to_le_bytes());

        // 256-byte payload (zero-padded)
        out.extend_from_slice(chunk);
        out.resize(out.len() + UF2_PAYLOAD_SIZE - chunk.len(), 0);

        // 220-byte padding
        out.resize(out.len() + 512 - 32 - UF2_PAYLOAD_SIZE - 4, 0);

        // 4-byte footer
        out.extend_from_slice(&UF2_MAGIC_END.to_le_bytes());
    }

    fs::write(output, &out).with_context(|| format!("Failed to write {}", output.display()))?;

    println!(
        "UF2: {} ({} blocks, {} bytes)",
        output.display(),
        num_blocks,
        data.len()
    );

    Ok(())
}
