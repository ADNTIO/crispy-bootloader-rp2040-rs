# Crispy RP2040 Bootloader - Build shortcuts

EMBEDDED_TARGET := thumbv6m-none-eabi
WINDOWS_TARGET  := x86_64-pc-windows-gnu
CHIP := RP2040
RELEASE_DIR := target/$(EMBEDDED_TARGET)/release

# Override project version: make all VERSION=0.3.2
ifdef VERSION
$(shell printf '$(VERSION)' > VERSION)
endif

.PHONY: help all embedded host keygen bootloader firmware firmware-cpp upload upload-windows clean lint clippy lint-python lint-md test-unit test-integration test-ci-scripts sbom sbom-rust sbom-python scan scan-grype scan-trivy
.PHONY: bootloader-bin firmware-bin firmware-cpp-bin bootloader-uf2
.PHONY: flash-bootloader run-bootloader
.PHONY: install-probe-rs install-tools update-mode reset

# Display available targets
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Build targets:"
	@echo "  all              Build everything (ELF + BIN + UF2 + C++)"
	@echo "                   Override version: make all VERSION=0.3.2"
	@echo "  embedded         Build bootloader + firmware (RP2040)"
	@echo "  host             Build upload tool (host)"
	@echo "  bootloader       Build bootloader only"
	@echo "  firmware         Build firmware only"
	@echo "  upload           Build upload tool (Linux)"
	@echo "  upload-windows   Build upload tool (Windows, cross-compile)"
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
	@echo "  lint             Run all linters (Rust clippy + Python ruff + Markdown)"
	@echo "  clippy           Run Rust clippy lints"
	@echo "  lint-md          Run Markdown linter (markdownlint-cli2)"
	@echo "  test-unit        Run all unit tests (Rust + Python)"
	@echo "  test-integration Run all integration tests (needs SWD + board)"
	@echo "  test-ci-scripts  Run CI script tests (no hardware)"
	@echo "  sbom             Generate CycloneDX SBOMs for Rust + Python (SBOM_OUT=dir)"
	@echo "  sbom-rust        Generate CycloneDX SBOMs for Rust binaries"
	@echo "  sbom-python      Generate CycloneDX SBOMs for Python projects"
	@echo "  scan             Run security scan on SBOMs (grype + trivy, fail on HIGH+)"
	@echo "  scan-grype       Scan SBOMs with grype"
	@echo "  scan-trivy       Scan SBOMs with trivy"
	@echo ""
	@echo "Setup:"
	@echo "  keygen           Generate Ed25519 firmware-signing key pair (keys/)"
	@echo "  install-tools    Install cargo-binutils (rust-objcopy)"
	@echo "  install-probe-rs Install custom probe-rs with software breakpoint support"
	@echo ""
	@echo "Utilities:"
	@echo "  update-mode      Force bootloader into update mode via SWD"
	@echo "  reset            Reset the device via SWD"
	@echo "  clean            Clean build artifacts"

# Build everything (ELF + BIN + UF2 + C++ + upload tools Linux/Windows)
all: bootloader-uf2 firmware-bin firmware-cpp upload upload-windows

# Build embedded packages (bootloader + firmware)
embedded:
	cargo build --release -p crispy-bootloader -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET)

# Build host upload tool
host:
	cargo build --release -p crispy-upload-rs

# Generate the Ed25519 firmware-signing key pair (keys/private_key.bin + public_key.bin).
# The bootloader's build.rs embeds keys/public_key.bin on the next build.
keygen:
	cargo run --release -p crispy-upload-rs -- keygen --out-dir keys

# Individual targets
bootloader:
	cargo build --release -p crispy-bootloader --target $(EMBEDDED_TARGET)

firmware:
	cargo build --release -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET)

upload:
	cargo build --release -p crispy-upload-rs

upload-windows:
	cargo build --release -p crispy-upload-rs --target $(WINDOWS_TARGET)

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
	cargo run --release -p crispy-upload-rs -- bin2uf2 $(RELEASE_DIR)/crispy-bootloader.bin $(RELEASE_DIR)/crispy-bootloader.uf2 --base-address 0x10000000

# Flash/run bootloader via SWD
flash-bootloader:
	cargo flash --release -p crispy-bootloader --target $(EMBEDDED_TARGET) --chip $(CHIP)

run-bootloader:
	cargo run --release -p crispy-bootloader --target $(EMBEDDED_TARGET)

# Linting
lint: clippy lint-python lint-md

clippy:
	cargo clippy -p crispy-upload-rs -- -D warnings
	cargo clippy -p crispy-bootloader -p crispy-fw-sample-rs --target $(EMBEDDED_TARGET) -- -D warnings

lint-python:
	cd crispy-common-python && uv run ruff check .

lint-md:
	npx --yes markdownlint-cli2

# Unit tests (Rust + Python, no hardware needed)
test-unit:
	cargo test -p crispy-common-rs --features crypto
	cd crispy-common-python && uv run pytest -v

# All integration tests (version + bootsequence + deployment)
test-integration:
	cd tests/integration && uv run pytest -v --tb=short


# CI script tests
test-ci-scripts:
	./scripts/ci/test-prepare-release-assets.sh

# Python projects (used by SBOM + scan targets)
PYTHON_PROJECTS := crispy-common-python crispy-upload-python tests/integration

# SBOM generation (CycloneDX format, published with release binaries)
SBOM_OUT ?= sbom
RUST_SBOM_PACKAGES := crispy-bootloader crispy-fw-sample-rs crispy-upload-rs

sbom: sbom-rust sbom-python

sbom-rust:
	@command -v cargo-cyclonedx >/dev/null 2>&1 || cargo install cargo-cyclonedx --locked
	@mkdir -p $(SBOM_OUT)
	@echo "==> cargo-cyclonedx (workspace, all targets)"
	cargo cyclonedx --format json --target all --quiet
	@for pkg in $(RUST_SBOM_PACKAGES); do \
		mv $$pkg/$$pkg.cdx.json $(SBOM_OUT)/$$pkg.cdx.json; \
	done
	@find . -maxdepth 2 -name "*.cdx.json" -not -path "./$(SBOM_OUT)/*" -delete

sbom-python:
	@command -v cyclonedx-py >/dev/null 2>&1 || pip install --user cyclonedx-bom
	@mkdir -p $(SBOM_OUT)
	@for project in $(PYTHON_PROJECTS); do \
		name=$$(basename $$project); \
		echo "==> cyclonedx-py: $$project -> $(SBOM_OUT)/$$name.cdx.json"; \
		(cd $$project && uv export --format requirements-txt --no-hashes --no-emit-project > .sbom-requirements.txt) && \
		cyclonedx-py requirements $$project/.sbom-requirements.txt -o $(SBOM_OUT)/$$name.cdx.json --output-format JSON; \
		rm -f $$project/.sbom-requirements.txt; \
	done

# Security scan: run grype + trivy on the generated SBOMs.
# Threshold matches CI (HIGH or higher fails).
SCAN_REPORTS ?= $(SBOM_OUT)/reports

scan: scan-grype scan-trivy

scan-grype: sbom
	@command -v grype >/dev/null 2>&1 || { \
		echo "Installing grype..."; \
		curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b $$HOME/.local/bin; \
	}
	@mkdir -p $(SCAN_REPORTS)
	@fail=0; for sbom in $(SBOM_OUT)/*.cdx.json; do \
		name=$$(basename $$sbom .cdx.json); \
		echo "==> grype: $$name"; \
		grype "sbom:$$sbom" --fail-on high -o table | tee $(SCAN_REPORTS)/grype-$$name.txt || fail=1; \
	done; exit $$fail

scan-trivy: sbom
	@command -v trivy >/dev/null 2>&1 || { \
		echo "Installing trivy..."; \
		curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sudo sh -s -- -b /usr/local/bin; \
	}
	@mkdir -p $(SCAN_REPORTS)
	@fail=0; for sbom in $(SBOM_OUT)/*.cdx.json; do \
		name=$$(basename $$sbom .cdx.json); \
		echo "==> trivy: $$name"; \
		trivy sbom $$sbom --severity HIGH,CRITICAL --exit-code 1 --format table \
			| tee $(SCAN_REPORTS)/trivy-$$name.txt || fail=1; \
	done; exit $$fail

# Clean
clean:
	cargo clean
	rm -rf $(CPP_FW_BUILD)

# Install cargo-binutils + Windows cross-compilation target
install-tools:
	rustup component add llvm-tools-preview
	rustup target add x86_64-pc-windows-gnu
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
