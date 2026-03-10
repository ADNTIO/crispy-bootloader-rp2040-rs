# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import os


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def pytest_addoption(parser):
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
