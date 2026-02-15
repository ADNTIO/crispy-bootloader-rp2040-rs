# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import subprocess
from pathlib import Path

from crispy_board.constants import EMBEDDED_TARGET


def _run(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def project_root_from(reference_file: str) -> Path:
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
    return _run(cmd, cwd=root, timeout=timeout)


def run_make(root: Path, *targets: str, timeout: float = 600) -> subprocess.CompletedProcess:
    return _run(["make"] + list(targets), cwd=root, timeout=timeout)


def objcopy(elf_path: Path, bin_path: Path, timeout: float = 30) -> subprocess.CompletedProcess:
    return _run(["rust-objcopy", "-O", "binary", str(elf_path), str(bin_path)], timeout=timeout)


def run_crispy_upload(
    project_root: Path, port: str, *args: str,
) -> tuple[bool, str, str]:
    result = _run(
        ["cargo", "run", "--release", "-p", "crispy-upload-rs", "--", "--port", port, *args],
        cwd=project_root, timeout=60,
    )
    return result.returncode == 0, result.stdout, result.stderr
