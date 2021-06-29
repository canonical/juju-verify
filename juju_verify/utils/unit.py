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
"""Helper function to manage Juju unit."""
import asyncio
import os
import re
from typing import List, Dict, Any, Optional

from juju.action import Action
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import VerificationError, CharmException
from juju_verify.utils.action import cache

CHARM_URL_PATTERN = re.compile(r'^(.*):(.*/)?(?P<charm>.*)(-\d+)$')


def get_cache_key(unit: Unit, action: str, **params: Any) -> int:
    """Create hash key from unit, action and params."""
    return hash(
        hash(unit.entity_id) + hash(action) + hash(tuple(sorted(params.items())))
    )


async def run_action(unit: Unit, action: str, use_cache: bool = True,
                     params: Optional[Dict[str, Any]] = None) -> Action:
    """Run Juju action and wait for results."""
    params = params or {}
    key = get_cache_key(unit, action, **params)

    if key not in cache or not use_cache:
        _action = await unit.run_action(action, **params)
        result = await _action.wait()  # wait for result
        cache[key] = result  # save result to cache
        return result

    return cache[key]


def run_action_on_units(units: List[Unit], action: str, use_cache: bool = True,
                        params: Optional[Dict[str, Any]] = None) -> Dict[str, Action]:
    """Run Juju action on specified units.

    :param units: List/Tuple of Unit object
    :param action: Action to run on units
    :param use_cache: Use the cache to gather the result of the action
    :param params: Additional parameters for the action
    :return: Dict in format {unit_id: action} where unit_ids are strings
             provided in 'units' and actions are their matching,
             juju.Action objects that have been executed and awaited.
    """
    task_map = {unit.entity_id: run_action(unit, action, use_cache, params)
                for unit in units}
    loop = asyncio.get_event_loop()
    tasks = asyncio.gather(*task_map.values())
    results: List[Action] = loop.run_until_complete(tasks)

    result_map = dict(zip(task_map.keys(), results))

    failed_actions_msg = []
    for unit_id, action_result in result_map.items():
        if action_result.status != 'completed':
            failed_actions_msg.append(
                f'Action {action} (ID: {action_result.entity_id}) failed to complete '
                f'on unit {unit_id}. For more info see '
                f'"juju show-action-output {action_result.entity_id}"'
            )

    if failed_actions_msg:
        raise VerificationError(os.linesep.join(failed_actions_msg))

    return result_map


def run_action_on_unit(unit: Unit, action: str,  use_cache: bool = True,
                       params: Optional[Dict[str, Any]] = None) -> Action:
    """Run juju action on single unit.

    For more info, see docstring for 'run_action_on_units'. The only
    difference is that this function returns Action object directly, not
    dict {unit_id: action}.
    """
    results = run_action_on_units([unit], action, use_cache, params)
    return results[unit.entity_id]


def parse_charm_name(charm_url: str) -> str:
    """Parse charm name from full charm url.

    Example: 'cs:focal/nova-compute-141' -> 'nova-compute'
    """
    match = CHARM_URL_PATTERN.match(charm_url)
    if match is None:
        raise CharmException(f'Failed to parse charm-url: "{charm_url}"')
    return match.group('charm')


def verify_charm_unit(charm_name: str, *units: Unit) -> None:
    """Verify that units are based on required charm."""
    for unit in units:
        if not parse_charm_name(unit.charm_url) == charm_name:
            raise CharmException(f"The unit {unit.entity_id} does not belong to the "
                                 f"charm {charm_name}.")


def get_first_active_unit(units: List[Unit]) -> Optional[Unit]:
    """Find first unit in active workload status."""
    for unit in units:
        if unit.workload_status == "active":
            return unit

    return None


def get_applications_names(model: Model, application: str) -> List[str]:
    """Get all names of application based on the same charm."""
    applications = []
    for app_name, app in model.applications.items():
        unit = get_first_active_unit(app.units)
        if unit and parse_charm_name(unit.charm_url) == application:
            applications.append(app_name)

    return applications
