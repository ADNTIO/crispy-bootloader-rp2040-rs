# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""
Version injection tests.

Verifies that the VERSION file is correctly injected into all build artifacts.

Usage:
    cd tests/integration && uv run pytest boot/version/ -v
"""

from pathlib import Path

import pytest

from crispy_board import EMBEDDED_TARGET, build_packages, project_root_from
from crispy_board.cargo import _run

RELEASE_DIR = Path(f"target/{EMBEDDED_TARGET}/release")

pytestmark = pytest.mark.version


class TestVersionInjection:

    @pytest.fixture(autouse=True)
    def _restore_version(self):
        root = project_root_from(__file__)
        original = (root / "VERSION").read_text().strip()
        yield
        (root / "VERSION").write_text(original)

    @pytest.mark.parametrize("version", ["0.3.2", "0.3.4"], ids=["test_01_version_032", "test_02_version_034"])
    def test_version_injection(self, version):
        root = project_root_from(__file__)
        (root / "VERSION").write_text(version)

        result = build_packages(root, ["crispy-upload-rs"], target=None)
        assert result.returncode == 0, f"cargo build crispy-upload-rs failed:\n{result.stderr}"

        result = build_packages(root, ["crispy-bootloader", "crispy-fw-sample-rs"])
        assert result.returncode == 0, f"cargo build embedded failed:\n{result.stderr}"

        cli = _run([str(root / "target/release/crispy-upload"), "--version"], timeout=10)
        assert cli.returncode == 0, f"crispy-upload --version failed:\n{cli.stderr}"
        assert version in cli.stdout, f"Expected '{version}' in CLI output, got: {cli.stdout.strip()}"

        for binary in ("crispy-bootloader", "crispy-fw-sample-rs"):
            path = root / RELEASE_DIR / binary
            assert path.exists(), f"Binary not found: {path}"
            assert version.encode() in path.read_bytes(), f"{binary} does not contain version {version}"
