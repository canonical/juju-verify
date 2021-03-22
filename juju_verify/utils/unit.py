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
import re
from typing import List, Dict, Any

from juju.action import Action
from juju.unit import Unit

from juju_verify.exceptions import VerificationError, CharmException

CHARM_URL_PATTERN = re.compile(r'^(.*):(.*/)?(?P<charm>.*)(-\d+)$')


def run_action_on_units(units: List[Unit], action: str,
                        **params: str) -> Dict[str, Action]:
    """Run juju action on specified units.

    :param units: List/Tuple of Unit object
    :param action: Action to run on units
    :param params: Additional parameters for the action
    :return: Dict in format {unit_id: action} where unit_ids are strings
             provided in 'units' and actions are their matching,
             juju.Action objects that have been executed and awaited.
    """
    task_map = {unit.entity_id: unit.run_action(action, **params) for unit in units}

    loop = asyncio.get_event_loop()
    tasks = asyncio.gather(*task_map.values())
    actions = loop.run_until_complete(tasks)
    action_futures = asyncio.gather(*[action.wait() for action in actions])
    results: List[Action] = loop.run_until_complete(action_futures)

    result_map = dict(zip(task_map.keys(), results))

    failed_actions_msg = []
    for unit, action_result in result_map.items():
        if action_result.status != 'completed':
            failed_actions_msg.append('Action {0} (ID: {1}) failed to '
                                      'complete on unit {2}. For more info'
                                      ' see "juju show-action-output {1}"'
                                      ''.format(action,
                                                action_result.entity_id,
                                                unit))

    if failed_actions_msg:
        raise VerificationError('\n'.join(failed_actions_msg))

    return result_map


def run_action_on_unit(unit: Unit, action: str, **params: str) -> Any:
    """Run Juju action on single unit, returning the result."""
    results = run_action_on_units([unit], action=action, **params)
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
