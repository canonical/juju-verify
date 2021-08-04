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
"""Utils cache test suite."""
from juju.action import Action
from juju.model import Model

from juju_verify.utils.cache import Cache, CacheManager


def test_cache():
    """Test cache functions."""
    default_cache_maxsize = 128
    cache = Cache(default_cache_maxsize)
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


def test_enable_cache():
    """Cache enabled test."""
    cache = CacheManager(enabled=True)

    assert cache.enabled
    with cache(None):
        assert cache.enabled

    with cache(False):
        assert cache.previous_state
        assert not cache.enabled

    assert cache.enabled


def test_disable_cache():
    """Cache disabled test."""
    cache = CacheManager(enabled=False)

    assert not cache.enabled
    with cache(None):
        assert not cache.enabled

    with cache(True):
        assert not cache.previous_state
        assert cache.enabled

    assert not cache.enabled
