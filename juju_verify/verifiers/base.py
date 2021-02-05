"""Base for other modules that implement verification checks for specific
charms"""
from abc import ABC, abstractmethod
from typing import Callable, Dict, List

from juju.unit import Unit

from juju_verify.exceptions import VerificationError


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
        verify_action()
