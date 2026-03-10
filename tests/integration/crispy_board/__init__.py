# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Board instrumentation library for integration tests.

Provides probe-rs wrappers, SWD/UF2 flashing, USB device discovery,
serial helpers, and cargo build utilities.
"""

from crispy_board.cargo import (  # noqa: F401
    build_packages,
    project_root_from,
    run_crispy_upload,
)
from crispy_board.constants import (  # noqa: F401
    BOOT2_ADDR,
    BOOT2_SIZE,
    BOOT_DATA_ADDR,
    BOOT_DATA_SECTOR_SIZE,
    CHIP,
    DEFAULT_VID,
    EMBEDDED_TARGET,
    PID_BOOTLOADER,
    PID_FW_RUST,
    RAM_UPDATE_FLAG_ADDR,
    RAM_UPDATE_MAGIC,
)
from crispy_board.discovery import (  # noqa: F401
    find_bootloader_port,
    find_firmware_port,
    find_rpi_rp2_mount,
    poll_until,
)
from crispy_board.flash import (  # noqa: F401
    enter_update_mode_via_swd,
    erase_boot_data,
    erase_flash,
    flash_elf,
    flash_uf2,
    force_bootsel_mode,
    reset_device,
)
from crispy_board.probe import ProbeResult, download_binary  # noqa: F401
from crispy_board.probe import run as run_probe_rs  # noqa: F401
from crispy_board.serial import wait_for_serial_banner  # noqa: F401
