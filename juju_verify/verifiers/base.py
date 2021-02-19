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
"""Base for other modules that implement verification checks for specific charms."""
import asyncio
import logging
from typing import Callable, Dict, List

from juju.action import Action
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import VerificationError

logger = logging.getLogger(__name__)


class Result:  # pylint: disable=too-few-public-methods
    """Convenience class that represents result of the check."""

    def __init__(self, success: bool, reason: str = ''):
        """Set values of the check result.

        :param success: Indicates whether check passed or failed. True/False
        :param reason: Additional information about result. Can stay empty for
        positive results
        """
        self.success = success
        self.reason = reason

    def __str__(self) -> str:
        """Return formatted string representing the result."""
        result = 'OK' if self.success else 'FAIL'
        output = 'Result: {}'.format(result)
        if self.reason:
            output += '\nReason: {}'.format(self.reason)
        return output

    def __add__(self, other: 'Result') -> 'Result':
        """Add together two Result instances.

        Boolean AND operation is applied on 'success' attribute and 'reason'
        attributes are concatenated.
        """
        if not isinstance(other, Result):
            raise NotImplementedError()

        new_success = self.success and other.success
        if other.reason and self.reason and not self.reason.endswith('\n'):
            self.reason += '\n'
        new_reason = self.reason + other.reason

        return Result(new_success, new_reason)


class BaseVerifier:
    """Base class for implementation of verification checks for specific charms.

    Classes that inherit from this base must override class variable 'NAME' to
    match charm name (e.g. 'nova-compute') and override methods named
    `verify_<check_name>` with actual implementation of the  checks.

    NotImplemented exception will be raised if attempt is made to perform check
    that is not implemented in child class.
    """

    NAME = ''

    def __init__(self, units: List[Unit]):
        """Initiate verifier linked to the Juju units.

        All the checks that the verifier implements must expect that the action
        that is being verified is intended to be performed on all juju units
        in the 'self.units' simultaneously.

        :raises VerificationError: If 'units' parameter is empty
        :raises VerificationError: If 'units' parameter contains units from
                                   different models.
        """
        self.units = units
        self.affected_machines = set()

        if not self.units:
            raise VerificationError('Can not run verification. This verifier'
                                    ' is not associated with any units.')
        for unit in self.units:
            self.affected_machines.add(unit.machine.entity_id)

        # Unit.model is mandatory property, so we end up either with one model
        # (correct) or multiple models (incorrect) in the 'models' set.
        models = {unit.model for unit in self.units}
        if len(models) > 1:
            raise VerificationError('Verifier initiated with units from '
                                    'multiple models.')
        self.model: Model = models.pop()
        self._unit_ids: List[str] = []

    @property
    def unit_ids(self) -> List[str]:
        """Return entity IDs of self.units."""
        return self._unit_ids or [unit.entity_id for unit in self.units]

    @classmethod
    def supported_checks(cls) -> List[str]:
        """Return list of supported checks."""
        return list(cls._action_map().keys())

    @classmethod
    def _action_map(cls) -> Dict[str, Callable[['BaseVerifier'], Result]]:
        """Return verification checks mapper.

        The key is the verification name. The value is a callable method that
        implements the logic.
        """
        return {
            'shutdown': cls.verify_shutdown,
            'reboot': cls.verify_reboot,
        }

    @staticmethod
    def data_from_action(action: Action, key: str, default: str = '') -> str:
        """Extract value from Action.data['results'] dictionary.

        :param action: juju.Action instance
        :param key: key to search for in action's results
        :param default: default value to return if the 'key' is not found
        :return: value from the action's result identified by 'key' or default
        """
        return action.data.get('results', {}).get(key, default)

    def unit_from_id(self, unit_id: str) -> Unit:
        """Search self.units for unit that matches 'unit_id'.

        :param unit_id: ID of the unit to find
        :return: Unit that matches 'unit_id'
        """
        for unit in self.units:
            if unit.entity_id == unit_id:
                return unit
        else:
            raise VerificationError('Unit {} was not found in {} verifier.'
                                    ''.format(unit_id, self.NAME))

    def check_affected_machines(self) -> None:
        """Check if affected machines run other principal units.

        Log warning if machine that run units checked by this verifier also
        runs other principal units that are not being checked.
        """
        machine_map: Dict = {machine: [] for machine in self.affected_machines}
        for _, unit in self.model.units.items():
            if unit.machine.entity_id in self.affected_machines \
                    and not unit.data.get('subordinate'):
                machine_map[unit.machine.entity_id].append(unit.entity_id)

        for machine, unit_list in machine_map.items():
            for unit in unit_list:
                if unit not in self.unit_ids:
                    logger.warning('Machine %s runs other principal unit that '
                                   'is not being checked: '
                                   '%s', machine, unit)

    def verify(self, check: str) -> Result:
        """Execute requested verification check.

        :param check: Check to execute
        :return: None
        :raises NotImplementedError: If requested check is unsupported/unknown
        :raises VerificationError: If check fails in unexpected manner or if
                                   list of self.units is empty
        """
        self.check_affected_machines()
        verify_action = self._action_map().get(check)
        if verify_action is None:
            raise NotImplementedError('Unsupported verification check "{}" for'
                                      ' charm {}'.format(check, self.NAME))

        try:
            logger.debug('Running check %s on units: %s', check,
                         ','.join([unit.entity_id for unit in self.units]))
            return verify_action(self)
        except NotImplementedError as exc:
            raise exc
        except Exception as exc:
            err = VerificationError('Verification failed: {}'.format(exc))
            raise err from exc

    def run_action_on_all(self, action: str,
                          **params: str) -> Dict[str, Action]:
        """Run juju action on all units in self.units.

        For more info, see docstring for 'run_action_on_units'.
        """
        return self.run_action_on_units(self.unit_ids, action, **params)

    def run_action_on_unit(self, unit: str, action: str,
                           **params: str) -> Action:
        """Run juju action on single unit.

        For more info, see docstring for 'run_action_on_units'. The only
        difference is that this function returns Action object directly, not
        dict {unit_id: action}.
        """
        results = self.run_action_on_units([unit], action, **params)
        return results[unit]

    def run_action_on_units(self, units: List[str], action: str,
                            **params: str) -> Dict[str, Action]:
        """Run juju action on specified units.

        Units are specified by string that must match Unit.entity_id in
        self.units. All actions that are executed are also awaited, if any
        of the actions fails, VerificationError is raised.

        :param units: List of unit IDs on which to run action
        :param action: Action to run on units
        :param params: Additional parameters for the action
        :return: Dict in format {unit_id: action} where unit_ids are strings
                 provided in 'units' and actions are their matching,
                 juju.Action objects that have been executed and awaited.
        """
        target_units = [self.unit_from_id(unit_id) for unit_id in units]
        task_map = {unit.entity_id: unit.run_action(action, **params)
                    for unit in target_units}

        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(*task_map.values())
        actions = loop.run_until_complete(tasks)
        action_futures = asyncio.gather(*[action.wait() for action in actions])
        results: List[Action] = loop.run_until_complete(action_futures)

        result_map = dict(zip(task_map.keys(), results))

        for unit, action_result in result_map.items():
            if action_result.status != 'completed':
                err_msg = 'Action {0} (ID: {1}) failed to complete on unit ' \
                          '{2}. For more info see "juju show-action-output ' \
                          '{1}"'.format(action, action_result.entity_id,
                                        unit)
                raise VerificationError(err_msg)
        return dict(zip(task_map.keys(), results))

    def verify_shutdown(self) -> Result:
        """Child classes must override this method with custom implementation.

        'shutdown' check needs to be implemented on child classes.
        """
        raise NotImplementedError('Requested check "shutdown" is not '
                                  'implemented for "{}" '
                                  'charm.'.format(self.NAME))

    def verify_reboot(self) -> Result:
        """Child classes must override this method with custom implementation.

        'reboot' check needds to be implemented on child classes.
        """
        raise NotImplementedError('Requested check "reboot" is not '
                                  'implemented for "{}" '
                                  'charm.'.format(self.NAME))
