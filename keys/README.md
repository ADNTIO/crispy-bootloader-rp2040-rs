# Firmware signing keys

The bootloader verifies an **Ed25519** signature over each firmware image before
committing it to a bank (see
[`docs/how-to/sign-firmware.md`](../docs/how-to/sign-firmware.md)).

## Files

| File                     | Committed?          | Purpose                                                           |
| ------------------------ | ------------------- | ----------------------------------------------------------------- |
| `public_key.bin.example` | yes                 | 32-byte all-zero placeholder so the project builds out of the box |
| `public_key.bin`         | **no** (gitignored) | the real 32-byte Ed25519 public key embedded into the bootloader  |
| `private_key.bin`        | **no** (gitignored) | the 32-byte secret seed used by the host to sign firmware         |

## Generating a key pair

```bash
make keygen          # writes keys/private_key.bin + keys/public_key.bin
# or directly:
cargo run --release -p crispy-upload-rs -- keygen --out-dir keys
```

The bootloader's `build.rs` embeds `keys/public_key.bin` if present, otherwise it
falls back to `public_key.bin.example` (all zeros) and prints a warning. With the
placeholder key, **no signature can ever be valid**, so a real key pair is
required for signed uploads.

## Security notes

- **Never commit `private_key.bin`.** It is the root of trust for firmware
  authenticity. Keep it in a secret store / HSM / CI secret for production.
- The placeholder `public_key.bin.example` is intentionally all zeros and must
  not be used in production.
- Verification happens **at upload time** (`FinishUpdate`). Builds with the
  `allow-unsigned` feature (enabled by default for development) also accept
  unsigned uploads. Build the bootloader with `--no-default-features` for a
  signature-only (secure) bootloader.
