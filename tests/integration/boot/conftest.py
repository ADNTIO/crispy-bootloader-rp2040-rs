# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ADNT Sarl <info@adnt.io>

import pytest

from crispy_board import project_root_from


def _option_fixture(name):
    @pytest.fixture(scope="session")
    def fixture(request):
        return request.config.getoption(name)
    fixture.__name__ = name.lstrip("-").replace("-", "_")
    return fixture


device_port = _option_fixture("--device")
skip_build = _option_fixture("--skip-build")
skip_flash = _option_fixture("--skip-flash")


@pytest.fixture(scope="session")
def project_root():
    return project_root_from(__file__)
