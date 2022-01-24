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
from collections import defaultdict, namedtuple
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from juju.action import Action
from juju.model import Model
from juju.unit import Unit
from packaging.version import InvalidVersion, Version

from juju_verify.exceptions import CharmException, VerificationError
from juju_verify.utils.unit import run_action_on_units
from juju_verify.verifiers.result import Result, Severity, checks_executor

logger = logging.getLogger(__name__)


class BaseVerifier:
    """Base class for implementation of verification checks for specific charms.

    Classes that inherit from this base must override class variable 'NAME' to
    match charm name (e.g. 'nova-compute') and override methods named
    `verify_<check_name>` with actual implementation of the  checks.

    NotImplemented exception will be raised if attempt is made to perform check
    that is not implemented in child class.
    """

    NAME = ""

    def __init__(
        self, units: List[Unit], exclude_affected_units: Optional[List[Unit]] = None
    ):
        """Initiate verifier linked to the Juju units.

        All the checks that the verifier implements must expect that the action
        that is being verified is intended to be performed on all juju units
        in the 'self.units' simultaneously.

        Parameter `exclude_affected_units` should contain list of units that are
        explicitly checked by other Verifier(s) so that they can be excluded from
        the warnings in `check_affected_machines()`.

        :raises VerificationError: If 'units' parameter is empty
        :raises VerificationError: If 'units' parameter contains units from
                                   different models.
        """
        self.units = units
        self.affected_machines = set()
        self.exclude_affected_units = exclude_affected_units or []
        models = set()

        if not self.units:
            raise VerificationError(
                "Can not run verification. This verifier"
                " is not associated with any units."
            )
        for unit in self.units:
            self.affected_machines.add(unit.machine.entity_id)
            models.add(unit.model)

        # Unit.model is mandatory property, so we end up either with one model
        # (correct) or multiple models (incorrect) in the 'models' set.
        if len(models) > 1:
            raise VerificationError(
                "Verifier initiated with units from multiple models."
            )
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
    def _action_map(cls) -> Dict[str, Callable[["BaseVerifier"], Result]]:
        """Return verification checks mapper.

        The key is the verification name. The value is a callable method that
        implements the logic.
        """
        return {
            "shutdown": cls.verify_shutdown,
            "reboot": cls.verify_reboot,
        }

    def get_verify_action(self, check: str) -> Callable:
        """Return verification check as callable function without any arguments."""
        if check not in self.supported_checks():
            raise NotImplementedError(
                f"Unsupported verification check '{check}' for charm {self.NAME}"
            )

        _verify_action = self._action_map()[check]

        @wraps(_verify_action)
        def wrapper() -> Result:
            """Wrap the classmethod so that it is callable without any arguments."""
            return _verify_action(self)

        return wrapper

    def unit_from_id(self, unit_id: str) -> Unit:
        """Search self.units for unit that matches 'unit_id'.

        :param unit_id: ID of the unit to find
        :return: Unit that matches 'unit_id'
        """
        for unit in self.units:
            if unit.entity_id == unit_id:
                return unit
        raise VerificationError(
            f"Unit {unit_id} was not found in {self.NAME} verifier."
        )

    @staticmethod
    def check_minimum_version(min_version: Version, units: List[Unit]) -> Result:
        """Check minimum required version of juju agents on units."""
        result = Result()
        for unit in units:
            juju_version = unit.safe_data.get("agent-status", {}).get("version", "")
            try:
                if Version(juju_version) < min_version:
                    fail_msg = (
                        f"Juju agent on unit {unit.entity_id} has lower than "
                        f"minimum required version. {juju_version} < "
                        f"{min_version}"
                    )
                    result.add_partial_result(Severity.FAIL, fail_msg)
            except InvalidVersion as exc:
                raise CharmException(
                    f"Failed to parse juju version from unit {unit.entity_id}."
                ) from exc

        return result or Result(Severity.OK, "Minimum juju version check passed.")

    def check_affected_machines(self) -> Result:
        """Check if affected machines run other principal units.

        Log warning if machine that run units checked by this verifier also
        runs other principal units that are not being checked.
        """
        result = Result()
        machine_map: Dict = defaultdict(list)
        for unit in self.model.units.values():
            if unit.machine.entity_id in self.affected_machines and not unit.data.get(
                "subordinate"
            ):
                machine_map[unit.machine.entity_id].append(unit.entity_id)

        verified_units = self.unit_ids.copy()
        verified_units.extend(unit.entity_id for unit in self.exclude_affected_units)

        for machine, unit_list in machine_map.items():
            for unit in unit_list:
                if unit not in verified_units:
                    result.add_partial_result(
                        Severity.WARN,
                        f"Machine {machine} runs other principal "
                        f"unit that is not being checked: {unit}",
                    )
        return result

    def check_has_sub_machines(self) -> Result:
        """Check if the machine hosts containers or VMs.

        Logs warning if there are units running on sub machines that are children of the
        affected machines.
        """
        result = Result()
        ParentChildPair = namedtuple("ParentChildPair", "child parent")
        parent_child_pairs = {}
        parents = set()

        # Search for child machines
        for parent_unit in self.units:
            # search the list of units for any that have the unit's machine as a parent
            for _, potential_child in self.model.units.items():
                if potential_child.machine.entity_id.startswith(
                    parent_unit.machine.entity_id + "/"
                ):
                    parents.add(parent_unit.entity_id)
                    parent_child_pairs[potential_child.entity_id] = ParentChildPair(
                        child=potential_child, parent=parent_unit
                    )

        task_map = {
            child_tag: parent_child_pair.child.is_leader_from_status()
            for child_tag, parent_child_pair in parent_child_pairs.items()
        }

        loop = asyncio.get_event_loop()

        results = loop.run_until_complete(asyncio.gather(*task_map.values()))
        result_map = dict(zip(task_map.keys(), results))

        # loop through list of parents, format a message
        for check_unit_entity_id in parents:
            for _, child_parent_pair in parent_child_pairs.items():
                if child_parent_pair.parent.entity_id == check_unit_entity_id:
                    child_tag = child_parent_pair.child.entity_id
                    child_tag += "*" if result_map[child_tag] else ""
                    result.add_partial_result(
                        Severity.WARN,
                        f"{check_unit_entity_id} has units running"
                        f" on child machines: {child_tag}",
                    )
        return result

    def verify(self, check: str) -> Result:
        """Execute requested verification check.

        :param check: Check to execute
        :return: Overall verification Result
        :raises NotImplementedError: If requested check is unsupported/unknown
        :raises VerificationError: If check fails in unexpected manner or if
                                   list of self.units is empty
        """
        verify_action = self.get_verify_action(check)
        preflight_checks = (self.check_affected_machines, self.check_has_sub_machines)

        try:
            logger.debug(
                "Running check %s on units: %s", check, ",".join(self.unit_ids)
            )
            return checks_executor(*preflight_checks, verify_action)
        except NotImplementedError as exc:
            raise exc
        except Exception as exc:
            raise VerificationError(f"Verification failed: {exc}") from exc

    def run_action_on_all(
        self,
        action: str,
        use_cache: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Action]:
        """Run juju action on all units in self.units.

        For more info, see docstring for 'run_action_on_units'.
        """
        return run_action_on_units(self.units, action, use_cache, params)

    def verify_shutdown(self) -> Result:
        """Child classes must override this method with custom implementation.

        'shutdown' check needs to be implemented on child classes.
        """
        raise NotImplementedError(
            f"Requested check 'shutdown' is not implemented for '{self.NAME}' charm."
        )

    def verify_reboot(self) -> Result:
        """Child classes must override this method with custom implementation.

        'reboot' check needs to be implemented on child classes.
        """
        raise NotImplementedError(
            f"Requested check 'reboot' is not implemented for '{self.NAME}' charm."
        )
