# Crispy RP2040 Bootloader - Build shortcuts

EMBEDDED_TARGET := thumbv6m-none-eabi
CHIP := RP2040
RELEASE_DIR := target/$(EMBEDDED_TARGET)/release

.PHONY: help all embedded host bootloader firmware firmware-cpp upload clean clippy test test-integration test-deployment
.PHONY: bootloader-bin firmware-bin firmware-cpp-bin bootloader-uf2
.PHONY: flash-bootloader run-bootloader
.PHONY: install-probe-rs install-tools update-mode reset

# Display available targets
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Build targets:"
	@echo "  all              Build everything (ELF + BIN + UF2)"
	@echo "  embedded         Build bootloader + firmware (RP2040)"
	@echo "  host             Build upload tool (host)"
	@echo "  bootloader       Build bootloader only"
	@echo "  firmware         Build firmware only"
	@echo "  upload           Build upload tool only"
	@echo "  bootloader-bin   Build crispy-bootloader.bin"
	@echo "  firmware-bin     Build crispy-fw-sample-rs.bin"
	@echo "  firmware-cpp     Build C++ firmware sample (CMake + Pico SDK)"
	@echo "  bootloader-uf2   Build crispy-bootloader.uf2"
	@echo ""
	@echo "Flash/run targets:"
	@echo "  flash-bootloader Flash bootloader via SWD"
	@echo "  run-bootloader   Flash + run bootloader with defmt/RTT"
	@echo ""
	@echo "Quality targets:"
	@echo "  clippy           Run clippy lints"
	@echo "  test             Run unit tests"
	@echo "  test-integration Run hardware integration tests (needs SWD + board)"
	@echo "  test-deployment  Run end-to-end deployment test (needs SWD + board)"
	@echo ""
	@echo "Setup:"
	@echo "  install-tools    Install cargo-binutils (rust-objcopy)"
	@echo "  install-probe-rs Install custom probe-rs with software breakpoint support"
	@echo ""
	@echo "Utilities:"
	@echo "  update-mode      Force bootloader into update mode via SWD"
	@echo "  reset            Reset the device via SWD"
	@echo "  clean            Clean build artifacts"

# Build everything (ELF + BIN + UF2)
all: bootloader-uf2 firmware-bin

# Build embedded packages (bootloader + firmware)
embedded:
	cargo build --release -p crispy-bootloader -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET)

# Build host upload tool
host:
	cargo build --release -p crispy-upload

# Individual targets
bootloader:
	cargo build --release -p crispy-bootloader --target $(EMBEDDED_TARGET)

firmware:
	cargo build --release -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET)

upload:
	cargo build --release -p crispy-upload

# Binary conversion targets
bootloader-bin: bootloader
	rust-objcopy -O binary $(RELEASE_DIR)/crispy-bootloader $(RELEASE_DIR)/crispy-bootloader.bin

firmware-bin: firmware
	rust-objcopy -O binary $(RELEASE_DIR)/crispy-fw-sample-rs $(RELEASE_DIR)/crispy-fw-sample-rs.bin

# C++ firmware (CMake + Pico SDK)
CPP_FW_DIR := crispy-fw-sample-cpp
CPP_FW_BUILD := $(CPP_FW_DIR)/build

firmware-cpp:
	cmake -S $(CPP_FW_DIR) -B $(CPP_FW_BUILD) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(CPP_FW_BUILD)

# UF2 targets
bootloader-uf2: bootloader-bin host
	cargo run --release -p crispy-upload -- bin2uf2 $(RELEASE_DIR)/crispy-bootloader.bin $(RELEASE_DIR)/crispy-bootloader.uf2 --base-address 0x10000000

# Flash/run bootloader via SWD
flash-bootloader:
	cargo flash --release -p crispy-bootloader --target $(EMBEDDED_TARGET) --chip $(CHIP)

run-bootloader:
	cargo run --release -p crispy-bootloader --target $(EMBEDDED_TARGET)

# Linting
clippy:
	cargo clippy -p crispy-upload -- -D warnings
	cargo clippy -p crispy-bootloader -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET) -- -D warnings

# Tests
test:
	cargo test -p crispy-common

# Integration tests (requires SWD probe + RP2040 board)
# Override CRISPY_DEVICE if auto-detection doesn't work
test-integration: all
	cd scripts/python && . .venv/bin/activate && python -m pytest tests/test_integration.py -v

# End-to-end deployment test (erase -> flash -> upload -> boot -> bank switch -> wipe)
test-deployment: all firmware-cpp
	cd scripts/python && . .venv/bin/activate && \
		python -m pytest tests/test_deployment.py -v --tb=short

# Clean
clean:
	cargo clean
	rm -rf $(CPP_FW_BUILD)

# Install cargo-binutils (provides rust-objcopy)
install-tools:
	rustup component add llvm-tools-preview
	cargo install cargo-binutils

# Install custom probe-rs with software breakpoint support (required for RAM debugging)
install-probe-rs:
	cargo install probe-rs-tools \
		--git https://github.com/fmahon/probe-rs.git \
		--branch feat/software-breakpoints \
		--locked --force

# Probe-rs utilities
update-mode:
	probe-rs write b32 0x2003BFF0 0x0FDA7E00 --chip $(CHIP) && probe-rs reset --chip $(CHIP)

reset:
	probe-rs reset --chip $(CHIP)
