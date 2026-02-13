# Bootloader Architecture Design

## Overview

This bootloader implements a dual-bank firmware update system for the RP2040 microcontroller. The design prioritizes reliability, safety, and efficient USB communication while working within the constraints of bare-metal embedded systems.

## FSM (Finite State Machine) Architecture

### State Machine Design

The bootloader uses a finite state machine (FSM) to manage the firmware update process. This design choice provides several key advantages:

#### Update State Machine

```
Inactive
   ↓ (Event::RequestUpdate)
Initializing
   ↓ (USB initialized)
Idle
   ↓ (StartUpdate command)
Receiving
   ↓ (FinishUpdate command)
[Flash write & verify]
   ↓
Idle
```

**States:**

1. **Inactive**: Bootloader not in update mode
2. **Initializing**: Setting up USB CDC communication
3. **Idle**: Ready to receive firmware update commands
4. **Receiving**: Actively receiving firmware data blocks in RAM
5. **Persisting** (reserved): Future state for multi-step flash writes

### Key Design Decisions

#### 1. RAM Buffering Strategy

**Problem**: Flash write operations disable interrupts for 1-2ms, preventing USB communication and causing timeouts.

**Solution**: Firmware data is buffered in RAM during reception, then written to flash in one operation after all data is received.

**Implementation Details:**
- Uses firmware RAM region (0x20000000 - 0x20030000, 192KB) which is unused during bootloader operation
- Bootloader only has 16KB of dedicated RAM, but can safely use the firmware region as a temporary buffer
- Buffer size: 128KB (configurable via `FW_RAM_BUFFER_SIZE`)
- Zero-copy design using raw pointers for performance

**Benefits:**
- No interrupt disruption during data reception
- Fast ACK responses to host
- USB remains responsive throughout upload
- Reduced flash wear (single erase + write cycle instead of multiple)

**Tradeoffs:**
- Firmware size limited to 128KB (well within typical requirements; sample firmware ~32KB)
- Full firmware must be received before flash write begins
- Memory safety relies on correct size validation

#### 2. Service-Based Architecture

The bootloader uses a cooperative multitasking service architecture:

```rust
enum ServiceType {
    UsbTransport(UsbTransportService),  // Polls USB, enqueues commands
    Trigger(TriggerCheckService),        // Checks boot/update trigger
    Update(UpdateService),               // Processes commands, manages FSM
    Led(LedBlinkService),                // Status indication
}
```

**Why Services?**
- **Single-threaded simplicity**: Avoids RTOS complexity and multicore synchronization
- **Predictable execution**: Each service processes once per loop iteration
- **Easy testing**: Services can be tested independently
- **Clear separation of concerns**: USB I/O separate from command processing

**Command Queue Pattern:**
- `UsbTransportService` receives commands via USB → enqueues to `heapless::spsc::Queue`
- `UpdateService` dequeues commands → dispatches to handlers
- Queue size: 8 commands (sufficient for typical command rates)
- Lock-free single-producer single-consumer design

#### 3. Flash Write Optimization

**Flash Erase**: Done once at `FinishUpdate`, not during `StartUpdate`
- Rationale: Erasing can take 80-100ms for multi-sector firmware
- Moving it to the end allows quick `StartUpdate` ACK
- Host doesn't send commands during `FinishUpdate`, so long flash write is acceptable

**Flash Write Loop**: Writes RAM buffer to flash in page-aligned chunks
```rust
while offset < expected_size {
    let chunk_size = (expected_size - offset).min(FLASH_PAGE_SIZE);
    // Write page-aligned chunk from RAM buffer to flash
    flash::flash_program(flash_offset + offset, src_ptr, padded_size);
    offset += chunk_size;
}
```

**CRC Verification**: Two-stage verification
1. Verify CRC of RAM buffer before flash write (fail fast)
2. Verify CRC of written flash data (ensure write success)

#### 4. Event-Driven State Transitions

Uses an event bus for decoupled communication between services:
```rust
// TriggerCheckService publishes event
ctx.events.publish(Event::RequestUpdate);

// UpdateService consumes event and transitions state
ctx.events.consume(|event| {
    if matches!(event, Event::RequestUpdate) {
        // Transition to Initializing
    }
});
```

**Benefits:**
- Services don't need direct references to each other
- Easy to add new trigger conditions (e.g., GPIO, timeout)
- Clear audit trail of state transitions

## Memory Layout

```
RP2040 RAM (264KB total):
  0x20000000 - 0x20030000: Firmware RAM (192KB)
                           ├─ Used as FW_RAM_BUFFER during bootloader operation
                           └─ Firmware executes from here after boot
  0x20030000 - 0x2003C000: Firmware data/BSS/stack (48KB)
  0x2003C000 - 0x20040000: Bootloader data/BSS/stack (16KB)

Flash (2MB):
  0x10000000 - 0x10000100: Boot2 (256B)
  0x10000100 - 0x10010000: Bootloader (64KB)
  0x10010000 - 0x100D0000: Firmware Bank A (768KB)
  0x100D0000 - 0x10190000: Firmware Bank B (768KB)
  0x10190000 - 0x10191000: Boot metadata (4KB)
```

## Security Considerations

1. **CRC32 Validation**: Every firmware update is CRC-validated before and after flash write
2. **Size Validation**: Firmware size checked against buffer limits
3. **Offset Validation**: Data blocks must be sequential (prevents gaps/overlaps)
4. **State Validation**: Commands rejected if FSM not in correct state
5. **Bank Validation**: Only banks 0-1 allowed

## Performance Characteristics

- **USB Poll Rate**: Once per main loop iteration (~microseconds)
- **Command Processing**: Sub-millisecond for most commands
- **Data Block Reception**: ~1ms (RAM copy only, no flash)
- **Flash Write**: 1-2ms per 256-byte page (only during FinishUpdate)
- **Full Update**: ~5-10 seconds for 32KB firmware (dominated by USB transfer time)

## Future Enhancements

1. **Incremental Flash Writes**: Add `Persisting` state to write large firmware in chunks
2. **Compression**: Support compressed firmware upload
3. **Signature Verification**: Add cryptographic signature checking
4. **Rollback Protection**: Anti-rollback version enforcement
5. **Differential Updates**: Only write changed sectors

## Testing Strategy

All changes are:
1. Tested on real hardware (RP2040-based device)
2. Verified through integration tests covering:
   - Basic bootloader status queries
   - Firmware upload (full 32KB firmware)
   - Bank switching
   - Error handling (invalid commands, CRC mismatch, etc.)
3. Supervised by human review at each iteration

## References

- RP2040 Datasheet: Flash controller behavior, interrupt handling
- `rp2040-hal` Documentation: USB CDC implementation
- `heapless` Documentation: Lock-free queue patterns
