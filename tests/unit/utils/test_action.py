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
from unittest.mock import PropertyMock

from juju.action import Action
from juju.model import Model

from juju_verify.utils.action import cache, data_from_action


def test_data_from_action(mocker):
    """Test helper function that parses data from Action.data.results dict."""
    host_key = "host"
    host_value = "compute.0"
    data = {"results": {host_key: host_value}}
    default = "default"

    mocker.patch.object(Action, "data", new_callable=PropertyMock(return_value=data))
    action = Action("0", Model())

    output = data_from_action(action, host_key, default)
    assert output == host_value

    # return default on missing key

    output = data_from_action(action, "foo", default)
    assert output == default


def test_cache():
    """Test cache functions."""
    default_cache_maxsize = cache.maxsize
    key_1, action_1 = hash("test-1"), Action("1", Model())
    key_2, action_2 = hash("test-2"), Action("2", Model())
    key_3, action_3 = hash("test-3"), Action("3", Model())

    cache.maxsize = 2  # change the maximum cache size for testing purposes
    assert cache.maxsize == 2
    cache[key_1] = action_1
    cache[key_2] = action_2
    assert key_1 in cache
    assert key_2 in cache
    assert key_3 not in cache
    assert cache.keys == [key_1, key_2]  # check keys order
    assert cache[key_1] == action_1
    assert cache.keys == [key_2, key_1]  # check keys order
    cache[key_3] = action_3
    assert key_2 not in cache
    assert key_3 in cache
    assert cache.keys == [key_1, key_3]  # check keys order
    cache.clear()
    assert key_1 not in cache
    assert key_2 not in cache
    assert key_3 not in cache
    # set the maximum cache size back to the default value
    cache.maxsize = default_cache_maxsize
    assert cache.maxsize == default_cache_maxsize
    cache.clear()
