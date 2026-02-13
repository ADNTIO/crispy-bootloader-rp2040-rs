# Crispy RP2040 - Bootloader + Firmware

> **AI-Assisted Development:** This project is developed with AI assistance under human supervision.
> The working model is human-in-the-loop AI-assisted development (AI as pair programmer, human as decision-maker).
> See [Development methodology](docs/explanation/development-methodology.md) and
> [AI-assisted development concept](docs/explanation/ai-assisted-development.md).

A/B bootloader for RP2040 (Raspberry Pi Pico) written in Rust.
The bootloader copies firmware from flash to RAM before executing it and supports two banks for safer updates over USB CDC.

For full documentation, start here: [`docs/index.md`](docs/index.md)

## Documentation

- Documentation hub: [`docs/index.md`](docs/index.md)
- First-time setup: [`docs/tutorials/first-bootloader-flash.md`](docs/tutorials/first-bootloader-flash.md)
- Firmware operations: [`docs/how-to/upload-firmware.md`](docs/how-to/upload-firmware.md)
- Architecture decisions (ADR): [`docs/explanation/architecture-decisions.md`](docs/explanation/architecture-decisions.md)

## Quick Start

```bash
# Install rust-objcopy (cargo-binutils) + llvm tools
make install-tools

# Show all available targets
make help

# Build bootloader UF2 + Rust firmware BIN
make all

# Show crispy-upload usage
cargo run --release -p crispy-upload -- --help
```

## Project Structure

```text
crispy-bootloader/     # RP2040 bootloader
crispy-fw-sample-rs/   # Sample Rust firmware (RAM execution)
crispy-fw-sample-cpp/  # Sample C++ firmware (Pico SDK)
crispy-sdk-cpp/        # C++ SDK for Crispy bootloader
crispy-common/         # Shared Rust crate (protocol + flash utilities)
crispy-upload/         # Host CLI for upload / status / bank selection
scripts/               # Utility scripts (integration tests, Python tools)
linker_scripts/        # Memory layouts for bootloader and firmware
docs/                  # Project documentation (Diataxis structure)
```

## Testing

- Unit tests: `make test`
- Hardware integration tests: [`docs/how-to/run-integration-tests.md`](docs/how-to/run-integration-tests.md)
- Deployment tests: `make test-deployment`

## License

MIT - Copyright (c) 2026 ADNT Sarl
