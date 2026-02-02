#!/usr/bin/env python3
# Convert a raw binary file to UF2 format for RP2040
# Usage: bin2uf2.py <input.bin> <output.uf2> [base_address]

import struct
import sys

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY_ID = 0x00002000
RP2040_FAMILY_ID = 0xE48BFF56
PAYLOAD_SIZE = 256

def convert(input_path, output_path, base_address):
    with open(input_path, "rb") as f:
        data = f.read()

    num_blocks = (len(data) + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE
    blocks = []

    for i in range(num_blocks):
        offset = i * PAYLOAD_SIZE
        chunk = data[offset : offset + PAYLOAD_SIZE]
        chunk = chunk.ljust(PAYLOAD_SIZE, b"\x00")

        header = struct.pack(
            "<IIIIIIII",
            UF2_MAGIC_START0,
            UF2_MAGIC_START1,
            UF2_FLAG_FAMILY_ID,
            base_address + offset,
            PAYLOAD_SIZE,
            i,
            num_blocks,
            RP2040_FAMILY_ID,
        )
        padding = b"\x00" * (512 - 32 - PAYLOAD_SIZE - 4)
        footer = struct.pack("<I", UF2_MAGIC_END)
        blocks.append(header + chunk + padding + footer)

    with open(output_path, "wb") as f:
        for block in blocks:
            f.write(block)

    print(f"UF2: {output_path} ({len(blocks)} blocks, {len(data)} bytes)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.bin> <output.uf2> [base_address]")
        sys.exit(1)
    base = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x10000000
    convert(sys.argv[1], sys.argv[2], base)
