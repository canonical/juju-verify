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
import logging
from typing import Callable, Dict, List

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

    def format(self) -> str:
        """Return formatted string representing the result."""
        result = 'OK' if self.success else 'FAIL'
        output = 'Result: {}'.format(result)
        if self.reason:
            output += '\nReason: {}'.format(self.reason)
        return output


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
        """
        self.units = units

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

    def verify(self, check: str) -> Result:
        """Execute requested verification check.

        :param check: Check to execute
        :return: None
        :raises NotImplementedError: If requested check is unsupported/unknown
        :raises VerificationError: If check fails in unexpected manner or if
                                   list of self.units is empty
        """
        if not self.units:
            raise VerificationError('Can not run verification. This verifier'
                                    ' is not associated with any units.')
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
