#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>
#
# Collect build artifacts into a flat release directory.
# Searches from the current directory so it works both locally
# (after `make all`) and in CI (after download-artifact).
#
# Usage: ./scripts/ci/prepare-release-assets.sh <release|debug> <output-dir>

set -euo pipefail

PROFILE="${1:?Usage: $0 <release|debug> <output-dir>}"
OUTDIR="${2:?Usage: $0 <release|debug> <output-dir>}"

if [[ "$PROFILE" != "release" && "$PROFILE" != "debug" ]]; then
    echo "ERROR: profile must be 'release' or 'debug', got '$PROFILE'" >&2
    exit 1
fi

mkdir -p "$OUTDIR"

# find_artifact <filename> [extra-find-args...]
#   Locate a build artifact by name.
#   Prefers paths containing /<profile>/ to disambiguate release vs debug.
#   Returns empty string if not found.
find_artifact() {
    local name="$1"; shift
    local result

    # Try profile-filtered first
    result="$(find . -name "$name" "$@" -path "*/$PROFILE/*" \
              ! -path './.git/*' ! -path '*/.venv/*' 2>/dev/null | head -1)"

    # Fallback: any match
    if [[ -z "$result" ]]; then
        result="$(find . -name "$name" "$@" \
                  ! -path './.git/*' ! -path '*/.venv/*' 2>/dev/null | head -1)"
    fi

    echo "$result"
}

# copy_required <filename> <dest> [extra-find-args...]
#   Find and copy an artifact. Exit 1 if not found.
copy_required() {
    local name="$1" dest="$2"; shift 2
    local src
    src="$(find_artifact "$name" "$@")"
    if [[ -z "$src" ]]; then
        echo "ERROR: '$name' not found" >&2
        exit 1
    fi
    cp "$src" "$dest"
}

# Bootloader (required)
copy_required crispy-bootloader    "$OUTDIR/crispy-bootloader.elf" -type f
copy_required crispy-bootloader.bin "$OUTDIR/"
copy_required crispy-bootloader.uf2 "$OUTDIR/"

# Firmware sample Rust (required)
copy_required crispy-fw-sample-rs     "$OUTDIR/crispy-fw-sample-rs.elf" -type f
copy_required crispy-fw-sample-rs.bin "$OUTDIR/"

# Firmware sample C++ (required)
copy_required crispy-fw-sample-cpp.elf "$OUTDIR/"
copy_required crispy-fw-sample-cpp.bin "$OUTDIR/"

# Upload tools
copy_required crispy-upload     "$OUTDIR/crispy-upload-linux-x64" -type f
copy_required crispy-upload.exe "$OUTDIR/crispy-upload-windows-x64.exe"
chmod +x "$OUTDIR/crispy-upload-linux-x64"

echo "Release assets ready in $OUTDIR/"
ls -1 "$OUTDIR/"
