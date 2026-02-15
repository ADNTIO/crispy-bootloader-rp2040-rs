# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Root pytest configuration for integration tests.

Environment variables (used as defaults when CLI options are not provided):
    CRISPY_DEVICE       Serial port (e.g. /dev/ttyACM0)
    CRISPY_SKIP_BUILD   Set to "1" to skip building
    CRISPY_SKIP_FLASH   Set to "1" to skip flashing
"""

import os
import sys
from pathlib import Path

# Add the boot/ directory so that ``import hardware`` works everywhere.
_BOOT_DIR = str(Path(__file__).parent / "boot")
if _BOOT_DIR not in sys.path:
    sys.path.insert(0, _BOOT_DIR)


def _env_bool(name: str) -> bool:
    """Read an environment variable as a boolean (truthy: '1', 'true', 'yes')."""
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--device",
        action="store",
        default=os.environ.get("CRISPY_DEVICE"),
        help="Serial port for the device (env: CRISPY_DEVICE)",
    )
    parser.addoption(
        "--skip-build",
        action="store_true",
        default=_env_bool("CRISPY_SKIP_BUILD"),
        help="Skip building firmware (env: CRISPY_SKIP_BUILD=1)",
    )
    parser.addoption(
        "--skip-flash",
        action="store_true",
        default=_env_bool("CRISPY_SKIP_FLASH"),
        help="Skip flashing device (env: CRISPY_SKIP_FLASH=1)",
    )
