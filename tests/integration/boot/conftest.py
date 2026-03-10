# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import pytest

from crispy_board import project_root_from


@pytest.fixture(scope="session")
def device_port(request):
    return request.config.getoption("--device")


@pytest.fixture(scope="session")
def skip_build(request):
    return request.config.getoption("--skip-build")


@pytest.fixture(scope="session")
def skip_flash(request):
    return request.config.getoption("--skip-flash")


@pytest.fixture(scope="session")
def project_root():
    return project_root_from(__file__)
