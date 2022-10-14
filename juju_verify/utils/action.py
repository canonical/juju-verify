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
from juju.action import Action

from juju_verify.utils.cache import Cache, CacheManager


def data_from_action(action: Action, key: str, default: str = "") -> str:
    """Extract value from Action.data['results'] dictionary.

    :param action: juju.Action instance
    :param key: key to search for in action's results
    :param default: default value to return if the 'key' is not found
    :return: value from the action's results identified by 'key' or default
    """
    return action.data.get("results", {}).get(key, default)


cache_manager = CacheManager(enabled=True)
cache = Cache(128)
