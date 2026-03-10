# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Low-level probe-rs subprocess wrapper."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from crispy_board.constants import CHIP


@dataclass
class ProbeResult:
    """Result of a probe-rs command."""

    success: bool
    output: str


def run(*args: str, timeout: float = 30.0) -> ProbeResult:
    """Run a probe-rs command and return the result."""
    cmd = ["probe-rs"] + list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    return ProbeResult(
        success=result.returncode == 0,
        output=result.stdout + result.stderr,
    )


def download_binary(
    data: bytes, base_address: int, timeout: float = 30.0,
) -> ProbeResult:
    """Write binary data to flash via probe-rs download.

    Creates a temporary file, downloads it to the given address, and cleans up.
    This factorizes the tempfile pattern used by erase_boot_data,
    force_bootsel_mode, and test_deployment.
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(data)
        tmp_path = f.name
    try:
        return run(
            "download", "--chip", CHIP,
            "--binary-format", "bin",
            "--base-address", hex(base_address),
            tmp_path,
            timeout=timeout,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
