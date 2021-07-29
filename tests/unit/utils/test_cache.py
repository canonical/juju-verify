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
from juju_verify.utils.cache import Cache


def test_enable_cache():
    """Cache enabled test."""
    cache = Cache(enabled=True)

    assert cache.enabled
    with cache(None):
        assert cache.enabled

    with cache(False):
        assert cache.previous_state
        assert not cache.enabled

    assert cache.enabled


def test_disable_cache():
    """Cache disabled test."""
    cache = Cache(enabled=False)

    assert not cache.enabled
    with cache(None):
        assert not cache.enabled

    with cache(True):
        assert not cache.previous_state
        assert cache.enabled

    assert not cache.enabled
