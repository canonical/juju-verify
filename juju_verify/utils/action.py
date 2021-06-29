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
"""Helper function to manage Juju action."""
from collections import OrderedDict
from typing import List, Any, Generator

from juju.action import Action


def data_from_action(action: Action, key: str, default: str = '') -> str:
    """Extract value from Action.data['results'] dictionary.

    :param action: juju.Action instance
    :param key: key to search for in action's results
    :param default: default value to return if the 'key' is not found
    :return: value from the action's results identified by 'key' or default
    """
    return action.data.get('results', {}).get(key, default)


class _Cache:
    """Cache class for action outputs."""

    def __init__(self, maxsize: int):
        """Initialize cache object."""
        self._cache: OrderedDict = OrderedDict()
        self.maxsize: int = maxsize

    def __getitem__(self, key: int) -> Any:
        """Get cached value."""
        if key in self._cache:
            self._cache.move_to_end(key)  # reorder cache

        return self._cache[key]

    def __setitem__(self, key: int, value: Any) -> None:
        """Cache the value using the key."""
        self._cache[key] = value

        # remove the oldest key
        if len(self._cache) > self.maxsize:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

    def __iter__(self) -> Generator:
        """Iterate over cache keys."""
        for key in self._cache:
            yield key

    def clear(self) -> None:
        """Clear cached data."""
        self._cache.clear()

    @property
    def keys(self) -> List[Any]:
        """Return cached keys."""
        return list(self._cache.keys())


cache = _Cache(128)
