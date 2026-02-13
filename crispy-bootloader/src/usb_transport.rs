// SPDX-License-Identifier: MIT
// Copyright (c) 2026 ADNT Sarl <info@adnt.io>

//! USB CDC transport with COBS-framed postcard serialization.

use crispy_common::protocol::{Command, Response};
use rp2040_hal::usb::UsbBus;
use usb_device::class_prelude::UsbBusAllocator;
use usb_device::prelude::*;
use usbd_serial::SerialPort;

const RX_BUF_SIZE: usize = 2048;
const TX_BUF_SIZE: usize = 2048;

#[derive(Debug, defmt::Format)]
pub enum TransportError {
    StringTooLong,
}

pub struct UsbTransport {
    serial: SerialPort<'static, UsbBus>,
    usb_dev: UsbDevice<'static, UsbBus>,
    rx_buf: [u8; RX_BUF_SIZE],
    rx_pos: usize,
    /// Command decoded during drain_rx_to_buffer, delivered on next try_receive().
    pending_cmd: Option<Command>,
}

impl UsbTransport {
    pub fn new(usb_bus: &'static UsbBusAllocator<UsbBus>) -> Result<Self, TransportError> {
        let serial = SerialPort::new(usb_bus);
        let usb_dev = UsbDeviceBuilder::new(usb_bus, UsbVidPid(0x2E8A, 0x000A))
            .strings(&[StringDescriptors::default()
                .manufacturer("ADNT")
                .product("Crispy Bootloader")
                .serial_number("0001")])
            .map_err(|_| TransportError::StringTooLong)?
            .device_class(usbd_serial::USB_CLASS_CDC)
            .build();

        Ok(Self {
            serial,
            usb_dev,
            rx_buf: [0u8; RX_BUF_SIZE],
            rx_pos: 0,
            pending_cmd: None,
        })
    }

    /// Poll USB device. Must be called frequently.
    pub fn poll(&mut self) -> bool {
        self.usb_dev.poll(&mut [&mut self.serial])
    }

    /// Try to receive a complete COBS-framed command.
    /// Returns `Some(Command)` when a full frame has been decoded.
    /// Delivers commands buffered during TX drain before reading new data.
    pub fn try_receive(&mut self) -> Option<Command> {
        // Deliver command that was decoded during drain_rx_to_buffer first
        if let Some(cmd) = self.pending_cmd.take() {
            return Some(cmd);
        }

        const USB_READ_BUF_SIZE: usize = 64;
        let mut tmp = [0u8; USB_READ_BUF_SIZE];

        let count = self.serial.read(&mut tmp).ok()?;
        if count == 0 {
            return None;
        }

        for &byte in &tmp[..count] {
            if let Some(cmd) = self.process_byte(byte) {
                return Some(cmd);
            }
        }
        None
    }

    /// Process a single received byte, handling COBS framing.
    /// Returns `Some(Command)` when a complete frame is decoded.
    fn process_byte(&mut self, byte: u8) -> Option<Command> {
        match byte {
            // COBS frame delimiter
            0x00 => self.try_decode_frame(),
            // Regular data byte
            _ => {
                self.append_byte(byte);
                None
            }
        }
    }

    /// Append a byte to the receive buffer, handling overflow.
    fn append_byte(&mut self, byte: u8) {
        if self.rx_pos < RX_BUF_SIZE {
            self.rx_buf[self.rx_pos] = byte;
            self.rx_pos += 1;
        } else {
            // Buffer overflow - discard current frame
            self.rx_pos = 0;
        }
    }

    /// Try to decode the accumulated frame buffer as a Command.
    fn try_decode_frame(&mut self) -> Option<Command> {
        if self.rx_pos == 0 {
            return None;
        }

        let result = postcard::from_bytes_cobs::<Command>(&mut self.rx_buf[..self.rx_pos]);
        self.rx_pos = 0;
        result.ok()
    }

    /// Send a response as a COBS-framed postcard message.
    ///
    /// Returns true if the response was fully sent.
    pub fn send(&mut self, resp: &Response) -> bool {
        defmt::println!("Transport: Sending response");
        let mut buf = [0u8; TX_BUF_SIZE];
        let encoded = match postcard::to_slice_cobs(resp, &mut buf) {
            Ok(data) => {
                defmt::println!("Transport: Encoded {} bytes", data.len());
                data
            }
            Err(_) => {
                defmt::error!("Failed to encode response");
                return false;
            }
        };

        let success = self.write_all(encoded);
        defmt::println!("Transport: write_all returned {}", success);
        success
    }

    /// Write all bytes to USB serial, handling WouldBlock by polling.
    ///
    /// Returns true if all data was sent, false if some data was dropped.
    fn write_all(&mut self, data: &[u8]) -> bool {
        let mut offset = 0;
        let mut poll_count = 0;
        const MAX_POLLS: usize = 100; // Prevent infinite blocking

        while offset < data.len() {
            match self.serial.write(&data[offset..]) {
                Ok(n) => {
                    offset += n;
                    poll_count = 0; // Reset on progress
                }
                Err(UsbError::WouldBlock) => {
                    poll_count += 1;
                    if poll_count > MAX_POLLS {
                        defmt::warn!(
                            "TX buffer full after {} polls, dropping {} bytes",
                            MAX_POLLS,
                            data.len() - offset
                        );
                        return false;
                    }

                    // Poll device AND read RX to prevent buffer overflow
                    self.poll();
                    self.drain_rx_to_buffer();
                }
                Err(_) => {
                    defmt::error!("USB write error");
                    return false;
                }
            }
        }
        true
    }

    /// Drain RX buffer without blocking, accumulating data for next try_receive()
    fn drain_rx_to_buffer(&mut self) {
        // Don't drain if RX buffer is already >75% full to prevent corruption
        if self.rx_pos > (RX_BUF_SIZE * 3 / 4) {
            defmt::warn!("RX buffer nearly full ({}), skipping drain", self.rx_pos);
            return;
        }

        const USB_READ_BUF_SIZE: usize = 64;
        let mut tmp = [0u8; USB_READ_BUF_SIZE];

        // Read whatever is available (non-blocking)
        if let Ok(count) = self.serial.read(&mut tmp) {
            if count > 0 {
                defmt::trace!("Drained {} RX bytes during TX", count);
                // Process bytes into our RX buffer
                for &byte in &tmp[..count] {
                    // Stop draining if buffer is getting full
                    if self.rx_pos >= (RX_BUF_SIZE * 3 / 4) {
                        defmt::warn!("RX buffer filling up during drain, stopping");
                        break;
                    }

                    // Accumulate data - will be processed on next try_receive()
                    if byte == 0x00 {
                        // Frame delimiter - decode and buffer the command
                        if let Some(cmd) = self.try_decode_frame() {
                            if self.pending_cmd.is_some() {
                                defmt::warn!("Pending command slot full, dropping command");
                            }
                            self.pending_cmd = Some(cmd);
                        }
                    } else {
                        self.append_byte(byte);
                    }
                }
            }
        }
    }
}
