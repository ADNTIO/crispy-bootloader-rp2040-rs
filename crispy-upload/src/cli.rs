// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! Command-line interface definitions.

use std::path::PathBuf;

use anyhow::{bail, Result};
use clap::{Parser, Subcommand};

use crate::commands;
use crate::transport::Transport;

/// Command-line arguments.
#[derive(Parser)]
#[command(name = "crispy-upload")]
#[command(about = "Firmware upload tool for crispy-bootloader")]
pub struct Cli {
    /// Serial port (e.g., /dev/ttyACM0)
    #[arg(short, long)]
    pub port: Option<String>,

    #[command(subcommand)]
    pub command: Commands,
}

/// Available subcommands.
#[derive(Subcommand)]
pub enum Commands {
    /// Get bootloader status
    Status,

    /// Upload firmware to a bank
    Upload {
        /// Firmware binary file
        #[arg(value_name = "FILE")]
        file: PathBuf,

        /// Target bank (0 = A, 1 = B)
        #[arg(short, long, default_value = "0")]
        bank: u8,

        /// Firmware version number
        #[arg(short, long, default_value = "1")]
        version: u32,
    },

    /// Set the active bank for the next boot (without uploading new firmware)
    SetBank {
        /// Target bank (0 = A, 1 = B)
        #[arg(value_name = "BANK")]
        bank: u8,
    },

    /// Wipe all firmware banks and reset boot data
    Wipe,

    /// Reboot the device
    Reboot,

    /// Convert a raw binary file to UF2 format
    #[command(name = "bin2uf2")]
    Bin2Uf2 {
        /// Input binary file
        #[arg(value_name = "INPUT")]
        input: PathBuf,

        /// Output UF2 file
        #[arg(value_name = "OUTPUT")]
        output: PathBuf,

        /// Base address in hex (default: 0x10000000)
        #[arg(short = 'a', long, default_value = "0x10000000", value_parser = parse_hex_u32)]
        base_address: u32,

        /// Family ID in hex (default: 0xE48BFF56 for RP2040)
        #[arg(short, long, default_value = "0xE48BFF56", value_parser = parse_hex_u32)]
        family_id: u32,
    },
}

/// Parse a hex string (with or without 0x prefix) into a u32.
fn parse_hex_u32(s: &str) -> Result<u32, String> {
    let s = s
        .strip_prefix("0x")
        .or_else(|| s.strip_prefix("0X"))
        .unwrap_or(s);
    u32::from_str_radix(s, 16).map_err(|e| format!("invalid hex value: {e}"))
}

/// Execute the parsed CLI command.
pub fn run(cli: Cli) -> Result<()> {
    match cli.command {
        Commands::Bin2Uf2 {
            input,
            output,
            base_address,
            family_id,
        } => commands::bin2uf2(&input, &output, base_address, family_id),

        cmd => {
            let port = cli
                .port
                .as_deref()
                .ok_or_else(|| anyhow::anyhow!("--port is required for this command"))?;
            let mut transport = Transport::new(port)?;

            match cmd {
                Commands::Status => commands::status(&mut transport),
                Commands::Upload {
                    file,
                    bank,
                    version,
                } => commands::upload(&mut transport, &file, bank, version),
                Commands::SetBank { bank } => commands::set_bank(&mut transport, bank),
                Commands::Wipe => commands::wipe(&mut transport),
                Commands::Reboot => commands::reboot(&mut transport),
                Commands::Bin2Uf2 { .. } => bail!("unreachable"),
            }
        }
    }
}
