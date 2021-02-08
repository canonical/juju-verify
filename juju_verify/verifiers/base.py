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

"""Base for other modules that implement verification checks for specific
charms"""
import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List

from juju.unit import Unit

from juju_verify.exceptions import VerificationError

logger = logging.getLogger(__name__)


class BaseVerifier(ABC):
    """Base class for implementation of verification checks for specific charms.

    Class that inherits form this base must override class variable 'NAME' to
    match charm name (e.g. 'nova-compute') and property '_action_map' to return
    map between verification check name (e.g. 'shutdown') and callable method
    that implements the check.

    Example:
        ```
        @property
        def _action_map(self):
            return {
                'reboot': self.verify_reboot,
                'shutdown': self.verify_shutdown,
            }
        ```
    """
    NAME = ''

    def __init__(self, units: List[Unit]):
        """Initiate verifier linked to the Juju units.

        All the checks that the verifier implements must expect that the action
        that is being verified is intended to be performed on all juju units
        in the 'self.units' simultaneously.
        """
        self.units = units

    @property
    def supported_checks(self) -> List[str]:
        """Returns list of supported checks on the specific charm"""
        return list(self._action_map.keys())

    @property
    @abstractmethod
    def _action_map(self) -> Dict[str, Callable]:
        """Returns map between verification check names and callable methods
        that implement them. See class Docstring for example."""

    def verify(self, check: str) -> None:
        """Execute requested verification check.

        :param check: Check to execute
        :return: None
        :raises VerificationError: If requested check is unsupported/unknown
        """
        verify_action = self._action_map.get(check)
        if verify_action is None:
            raise VerificationError('Unsupported verification check "{}" for '
                                    'charm {}'.format(check, self.NAME))
        try:
            logger.debug('Running check %s on units: %s', check,
                         ','.join([unit.entity_id for unit in self.units]))
            verify_action()
        except NotImplementedError as exc:
            err = VerificationError('Requested check "{}" is not implemented '
                                    'on "{}" charm.'.format(check, self.NAME))
            raise err from exc
        except Exception as exc:
            err = VerificationError('Verification failed: {}'.format(exc))
            raise err from exc
