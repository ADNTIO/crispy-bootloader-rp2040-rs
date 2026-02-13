# Crispy Documentation

This documentation follows the Diataxis model:

- `tutorials/`: learning-oriented, step-by-step onboarding
- `how-to/`: goal-oriented operational guides
- `reference/`: factual technical details (API, protocol, memory map)
- `explanation/`: design rationale and architecture decisions

## Tutorials

- [Flash the bootloader for the first time](tutorials/first-bootloader-flash.md)

## How-to Guides

- [Upload firmware](how-to/upload-firmware.md)
- [Run integration tests](how-to/run-integration-tests.md)
- [Recover a device](how-to/recover-device.md)

## Reference

- [CLI `crispy-upload`](reference/cli-crispy-upload.md)
- [USB protocol](reference/protocol.md)
- [Memory map](reference/memory-map.md)
- [Boot data format](reference/boot-data.md)

## Explanation

- [Architecture](explanation/architecture.md)
- [AI-assisted development concept](explanation/ai-assisted-development.md)
- [Boot bank selection and rollback](explanation/boot-bank-selection.md)
- [Development methodology](explanation/development-methodology.md)

## Architecture Decisions

- [Architecture decisions index](explanation/architecture-decisions.md)
- [ADR-0001: Dual-bank firmware update model](explanation/adr/ADR-0001-dual-bank-update-model.md)
- [ADR-0002: RAM-buffered upload before flash write](explanation/adr/ADR-0002-ram-buffered-upload.md)
- [ADR-0003: Cooperative services + event bus](explanation/adr/ADR-0003-cooperative-services-and-events.md)

## Troubleshooting

- [Common issues](troubleshooting.md)
