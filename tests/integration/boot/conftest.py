# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

"""Common fixtures for boot integration tests."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def device_port(request):
    """Get the device port from command line (optional override)."""
    return request.config.getoption("--device")


@pytest.fixture(scope="session")
def skip_build(request):
    """Check if build should be skipped."""
    return request.config.getoption("--skip-build")


@pytest.fixture(scope="session")
def skip_flash(request):
    """Check if flash should be skipped."""
    return request.config.getoption("--skip-flash")


@pytest.fixture(scope="session")
def project_root():
    """Get the project root directory.

    Path: tests/integration/boot/conftest.py  →  4 parents up = workspace root.
    """
    return Path(__file__).parent.parent.parent.parent
