#!/usr/bin/env bash
# Flash UF2 to Pico in BOOTSEL mode
set -e

UF2_FILE="${1:-target/thumbv6m-none-eabi/release/combined.uf2}"
MOUNT_POINT="${MOUNT_POINT:-/media/$USER/RPI-RP2}"

if [ ! -f "$UF2_FILE" ]; then
    echo "Error: $UF2_FILE not found"
    echo "Usage: $0 [uf2_file]"
    exit 1
fi

if [ ! -d "$MOUNT_POINT" ]; then
    echo "Error: Pico not found at $MOUNT_POINT"
    echo "Put Pico in BOOTSEL mode (hold BOOTSEL while plugging USB)"
    exit 1
fi

echo "Flashing $UF2_FILE to $MOUNT_POINT..."
cp "$UF2_FILE" "$MOUNT_POINT/"
echo "Done!"
