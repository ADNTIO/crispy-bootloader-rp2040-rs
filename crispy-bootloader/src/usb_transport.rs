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
        })
    }

    /// Poll USB device. Must be called frequently.
    pub fn poll(&mut self) -> bool {
        self.usb_dev.poll(&mut [&mut self.serial])
    }

    /// Try to receive a complete COBS-framed command.
    /// Returns `Some(Command)` when a full frame has been decoded.
    pub fn try_receive(&mut self) -> Option<Command> {
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
    pub fn send(&mut self, resp: &Response) {
        let mut buf = [0u8; TX_BUF_SIZE];
        let encoded = match postcard::to_slice_cobs(resp, &mut buf) {
            Ok(data) => data,
            Err(_) => return,
        };

        self.write_all(encoded);
    }

    /// Write all bytes to USB serial, handling WouldBlock by polling.
    fn write_all(&mut self, data: &[u8]) {
        let mut offset = 0;
        while offset < data.len() {
            match self.serial.write(&data[offset..]) {
                Ok(n) => offset += n,
                Err(UsbError::WouldBlock) => {
                    self.poll();
                }
                Err(_) => break,
            }
        }
    }
}
