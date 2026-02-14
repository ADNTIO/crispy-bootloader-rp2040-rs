#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>
#
# Test for prepare-release-assets.sh
# Runs scenarios: local layout, CI layout, missing artifact, and invalid profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/prepare-release-assets.sh"

# verify_files <release-dir> <label> <file1> [file2 ...]
verify_files() {
    local release_dir="$1" label="$2"; shift 2
    local expected=("$@")
    local fail=0

    for f in "${expected[@]}"; do
        if [[ ! -f "$release_dir/$f" ]]; then
            echo "  FAIL: missing $f" >&2
            fail=1
        fi
    done

    if [[ -f "$release_dir/crispy-upload-linux-x64" && ! -x "$release_dir/crispy-upload-linux-x64" ]]; then
        echo "  FAIL: crispy-upload-linux-x64 is not executable" >&2
        fail=1
    fi

    local actual_count
    actual_count="$(ls -1 "$release_dir" | wc -l)"
    if [[ "$actual_count" -ne "${#expected[@]}" ]]; then
        echo "  FAIL: expected ${#expected[@]} files, got $actual_count" >&2
        fail=1
    fi

    if [[ "$fail" -eq 0 ]]; then
        echo "  PASS: $label (${#expected[@]} files)"
    else
        echo "  FAIL: $label" >&2
        return 1
    fi
}

ALL_FILES=(
    crispy-bootloader.elf crispy-bootloader.bin crispy-bootloader.uf2
    crispy-fw-sample-rs.elf crispy-fw-sample-rs.bin
    crispy-fw-sample-cpp.elf crispy-fw-sample-cpp.bin
    crispy-upload-linux-x64 crispy-upload-windows-x64.exe
)

# Helper: create all artifact files in a given layout
create_all_artifacts() {
    local fw="$1" cpp="$2" linux="$3" win="$4"
    mkdir -p "$fw" "$cpp" "$linux" "$win"
    echo "bl"   > "$fw/crispy-bootloader"
    echo "bl"   > "$fw/crispy-bootloader.bin"
    echo "bl"   > "$fw/crispy-bootloader.uf2"
    echo "fw"   > "$fw/crispy-fw-sample-rs"
    echo "fw"   > "$fw/crispy-fw-sample-rs.bin"
    echo "cpp"  > "$cpp/crispy-fw-sample-cpp.elf"
    echo "cpp"  > "$cpp/crispy-fw-sample-cpp.bin"
    echo "up"   > "$linux/crispy-upload"
    echo "up"   > "$win/crispy-upload.exe"
}

TMPDIRS=()
cleanup() { rm -rf "${TMPDIRS[@]}"; }
trap cleanup EXIT

new_tmpdir() {
    local d; d="$(mktemp -d)"; TMPDIRS+=("$d"); echo "$d"
}

# --- Test 1: local build layout ---
echo "Test 1: local build layout"
T="$(new_tmpdir)"
create_all_artifacts \
    "$T/target/thumbv6m-none-eabi/release" \
    "$T/crispy-fw-sample-cpp/build" \
    "$T/target/release" \
    "$T/target/x86_64-pc-windows-gnu/release"

(cd "$T" && "$SCRIPT" release release) > /dev/null
verify_files "$T/release" "local layout" "${ALL_FILES[@]}"

# --- Test 2: CI artifact layout ---
echo "Test 2: CI artifact layout"
T="$(new_tmpdir)"
create_all_artifacts \
    "$T/artifacts/firmware/target/thumbv6m-none-eabi/release" \
    "$T/artifacts/firmware/crispy-fw-sample-cpp/build" \
    "$T/artifacts/crispy-upload-linux-x64" \
    "$T/artifacts/crispy-upload-windows-x64"

(cd "$T" && "$SCRIPT" release release) > /dev/null
verify_files "$T/release" "CI layout" "${ALL_FILES[@]}"

# --- Test 3: missing artifact fails ---
echo "Test 3: missing artifact fails"
T="$(new_tmpdir)"
mkdir -p "$T/target/thumbv6m-none-eabi/release"
echo "bl" > "$T/target/thumbv6m-none-eabi/release/crispy-bootloader"
if (cd "$T" && "$SCRIPT" release release) 2>/dev/null; then
    echo "  FAIL: should have failed with missing artifacts" >&2
    exit 1
else
    echo "  PASS: missing artifact rejected"
fi

# --- Test 4: invalid profile rejected ---
echo "Test 4: invalid profile rejected"
T="$(new_tmpdir)"
if (cd "$T" && "$SCRIPT" banana /dev/null) 2>/dev/null; then
    echo "  FAIL: should have rejected invalid profile" >&2
    exit 1
else
    echo "  PASS: invalid profile rejected"
fi

echo ""
echo "All tests passed."
