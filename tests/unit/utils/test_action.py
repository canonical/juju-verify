# Copyright 2021 Canonical Limited.
#
# This file is part of juju-verify.
#
# juju-verify is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# juju-verify is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see https://www.gnu.org/licenses/.
"""Juju action helpers test suite."""
from unittest.mock import Mock

import pytest
from juju.action import Action

from juju_verify.utils.action import data_from_action


@pytest.mark.parametrize(
    "data, key, exp_value",
    [
        ({"results": {"host": "compute.0", "test": "test"}}, "host", "compute.0"),
        ({"results": {"test": "test"}}, "host", "default"),
        ({"results": {"ids": "[1, 2, 3]", "test": "test"}}, "ids", "[1, 2, 3]"),
        ({"test": "test"}, "host", "default"),
    ],
)
def test_data_from_action(data, key, exp_value):
    """Test helper function that parses data from Action.data.results dict."""
    action = Mock(spec_set=Action)
    action.data = data

    output = data_from_action(action, key, "default")
    assert output == exp_value
