# Sign firmware (Ed25519)

The bootloader verifies an **Ed25519** signature over each firmware image before
it is committed to a bank. Verification happens at **upload time**
(`FinishUpdate`), using a public key embedded into the bootloader at build time.

## 1. Generate a key pair

```bash
make keygen
# writes keys/private_key.bin (secret, gitignored) and keys/public_key.bin
```

- `keys/private_key.bin` is a 32-byte Ed25519 secret seed. **Keep it secret.**
- `keys/public_key.bin` is the 32-byte public key embedded into the bootloader.

Both files are gitignored. For production, generate the key pair on a trusted
machine / HSM and never commit the private key.

## 2. Build the bootloader with the public key

`crispy-bootloader/build.rs` embeds `keys/public_key.bin` automatically (falling
back to an all-zero placeholder if absent). Rebuild after `make keygen`:

```bash
make bootloader        # or: make all
```

You can point the build at a different key without touching the repo:

```bash
CRISPY_PUBLIC_KEY_FILE=/path/to/public_key.bin make bootloader
```

## 3. Upload a signed firmware

```bash
cargo run --release -p crispy-upload-rs -- \
    --port /dev/ttyACM0 \
    upload firmware.bin --bank 0 --fw-version 1 \
    --key keys/private_key.bin
```

The host signs `firmware.bin` and sends it via `StartUpdateSigned`. If the
signature does not match the bootloader's embedded public key, the upload is
rejected with `SignatureInvalid`.

## Unsigned uploads and build modes

| Bootloader build                      | Unsigned upload (`upload` without `--key`) | Signed upload               |
| ------------------------------------- | ------------------------------------------ | --------------------------- |
| default (`allow-unsigned` feature on) | accepted (with warning) — **development**  | accepted if signature valid |
| `--no-default-features` (secure)      | rejected with `SignatureRequired`          | accepted if signature valid |

Build a signature-only (secure) bootloader with:

```bash
cargo build --release -p crispy-bootloader \
    --target thumbv6m-none-eabi --no-default-features
```

## Notes and limitations

- The signed message is the **raw firmware image** (exactly the bytes written to
  the bank).
- Verification is performed on the firmware buffered in RAM, **before** erasing
  or writing flash, so a bad signature never touches the target bank.
- Signatures are verified at **upload time only**. They are not persisted in
  `BootData`, so boot-time integrity still relies on the CRC-32 check. Firmware
  written through another path (e.g. SWD) is not signature-checked at boot.
- The algorithm is Ed25519 (`ed25519-dalek`), interoperable between the host
  signer and the device verifier.
