# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Cargo build and crispy-upload helpers."""

import subprocess
from pathlib import Path

from crispy_board.constants import EMBEDDED_TARGET


def project_root_from(reference_file: str) -> Path:
    """Find the project root by walking up from *reference_file* until Cargo.toml is found."""
    path = Path(reference_file).resolve().parent
    while path != path.parent:
        if (path / "Cargo.toml").exists() and (path / "VERSION").exists():
            return path
        path = path.parent
    raise FileNotFoundError(
        f"Could not find project root (Cargo.toml + VERSION) from {reference_file}"
    )


def build_packages(
    root: Path,
    packages: list[str],
    target: str | None = EMBEDDED_TARGET,
    timeout: float = 120,
) -> subprocess.CompletedProcess:
    """Build one or more cargo packages.

    Args:
        root: Project root directory.
        packages: List of package names (e.g. ["crispy-bootloader", "crispy-fw-sample-rs"]).
        target: Cross-compilation target (None for host target).
        timeout: Build timeout in seconds.
    """
    cmd = ["cargo", "build", "--release"]
    for pkg in packages:
        cmd += ["-p", pkg]
    if target:
        cmd += ["--target", target]

    return subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=timeout,
    )


def run_crispy_upload(
    project_root: Path, port: str, *args: str,
) -> tuple[bool, str, str]:
    """Execute ``cargo run -p crispy-upload-rs -- <args>`` and return results.

    Returns:
        (success, stdout, stderr)
    """
    cmd = [
        "cargo", "run", "--release", "-p", "crispy-upload-rs", "--",
        "--port", port,
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=project_root, capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0, result.stdout, result.stderr
