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
from unittest.mock import MagicMock

from juju.action import Action

from juju_verify.utils.action import data_from_action


def test_data_from_action(mocker):
    """Test helper function that parses data from Action.data.results dict."""
    host_key = "host"
    host_value = "compute.0"
    data = {host_key: host_value}
    default = "default"

    action = Action("0", MagicMock())
    action.results = data

    output = data_from_action(action, host_key, default)
    assert output == host_value

    # return default on missing key

    output = data_from_action(action, "foo", default)
    assert output == default
