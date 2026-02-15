# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
Version injection tests.

Verifies that the VERSION file at the project root is correctly
injected into all build artifacts (Rust CLI, bootloader, firmware).

The test builds twice with different version numbers (0.3.2 and 0.3.4)
and checks that each artifact contains the expected version string.

Usage:
    cd tests/integration && uv run pytest boot/version/ -v
"""

import subprocess
from pathlib import Path

import pytest

EMBEDDED_TARGET = "thumbv6m-none-eabi"
RELEASE_DIR = Path(f"target/{EMBEDDED_TARGET}/release")

pytestmark = pytest.mark.version


class TestVersionInjection:
    """Build with two different versions and verify artifacts."""

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).parent.parent.parent.parent.parent

    @staticmethod
    def _read_version(root: Path) -> str:
        return (root / "VERSION").read_text().strip()

    @staticmethod
    def _write_version(root: Path, version: str):
        (root / "VERSION").write_text(version)

    @staticmethod
    def _build_all(root: Path):
        """Build CLI + embedded targets."""
        result = subprocess.run(
            ["cargo", "build", "--release", "-p", "crispy-upload-rs"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert (
            result.returncode == 0
        ), f"cargo build crispy-upload-rs failed:\n{result.stderr}"

        result = subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "-p",
                "crispy-bootloader",
                "-p",
                "crispy-fw-sample-rs",
                "--target",
                EMBEDDED_TARGET,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"cargo build embedded failed:\n{result.stderr}"

    @staticmethod
    def _cli_version(root: Path) -> str:
        """Run crispy-upload --version and return the output."""
        result = subprocess.run(
            [str(root / "target/release/crispy-upload"), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert (
            result.returncode == 0
        ), f"crispy-upload --version failed:\n{result.stderr}"
        return result.stdout.strip()

    @staticmethod
    def _binary_contains_version(root: Path, binary_path: Path, version: str) -> bool:
        """Check if an ELF binary contains the version string."""
        full_path = root / binary_path
        assert full_path.exists(), f"Binary not found: {full_path}"
        data = full_path.read_bytes()
        return version.encode() in data

    @pytest.fixture(autouse=True)
    def _restore_version(self):
        """Save and restore the original VERSION file."""
        root = self._project_root()
        original = self._read_version(root)
        yield
        self._write_version(root, original)

    def test_01_version_032(self):
        """Build with VERSION=0.3.2 and verify all artifacts."""
        root = self._project_root()
        self._write_version(root, "0.3.2")

        self._build_all(root)

        # CLI
        cli_output = self._cli_version(root)
        assert (
            "0.3.2" in cli_output
        ), f"Expected '0.3.2' in CLI output, got: {cli_output}"

        # Bootloader ELF
        assert self._binary_contains_version(
            root, RELEASE_DIR / "crispy-bootloader", "0.3.2"
        ), "Bootloader ELF does not contain version 0.3.2"

        # Firmware ELF
        assert self._binary_contains_version(
            root, RELEASE_DIR / "crispy-fw-sample-rs", "0.3.2"
        ), "Firmware ELF does not contain version 0.3.2"

        print("All artifacts contain version 0.3.2")

    def test_02_version_034(self):
        """Build with VERSION=0.3.4 and verify all artifacts."""
        root = self._project_root()
        self._write_version(root, "0.3.4")

        self._build_all(root)

        # CLI
        cli_output = self._cli_version(root)
        assert (
            "0.3.4" in cli_output
        ), f"Expected '0.3.4' in CLI output, got: {cli_output}"

        # Bootloader ELF
        assert self._binary_contains_version(
            root, RELEASE_DIR / "crispy-bootloader", "0.3.4"
        ), "Bootloader ELF does not contain version 0.3.4"

        # Firmware ELF
        assert self._binary_contains_version(
            root, RELEASE_DIR / "crispy-fw-sample-rs", "0.3.4"
        ), "Firmware ELF does not contain version 0.3.4"

        print("All artifacts contain version 0.3.4")
