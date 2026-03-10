# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import subprocess
from pathlib import Path

from crispy_board.constants import EMBEDDED_TARGET


def project_root_from(reference_file: str) -> Path:
    """Walk up from *reference_file* until a directory with Cargo.toml + VERSION is found."""
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
    cmd = ["cargo", "build", "--release"]
    for pkg in packages:
        cmd += ["-p", pkg]
    if target:
        cmd += ["--target", target]

    return subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=timeout,
    )


def run_make(
    root: Path,
    *targets: str,
    timeout: float = 600,
) -> subprocess.CompletedProcess:
    cmd = ["make"] + list(targets)
    return subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, timeout=timeout,
    )


def objcopy(
    elf_path: Path,
    bin_path: Path,
    timeout: float = 30,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["rust-objcopy", "-O", "binary", str(elf_path), str(bin_path)],
        capture_output=True, text=True, timeout=timeout,
    )


def run_crispy_upload(
    project_root: Path, port: str, *args: str,
) -> tuple[bool, str, str]:
    """Returns (success, stdout, stderr)."""
    cmd = [
        "cargo", "run", "--release", "-p", "crispy-upload-rs", "--",
        "--port", port,
        *args,
    ]
    result = subprocess.run(
        cmd, cwd=project_root, capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0, result.stdout, result.stderr
