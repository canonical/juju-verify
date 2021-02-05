"""ceph-osd verification"""
from typing import Dict, Callable

from juju_verify.verifiers.base import BaseVerifier


class CephOsd(BaseVerifier):
    """Implementation of verification checks for the ceph-osd charm"""
    NAME = 'ceph-osd'

    @property
    def _action_map(self) -> Dict[str, Callable]:
        """Returns map between verification check names and methods
        implementing them """
        actions = {
            'reboot': self.verify_reboot,
            'shutdown': self.verify_shutdown,
        }
        return actions

    def verify_reboot(self) -> None:
        """Implementation of the 'reboot' verification check"""
        raise NotImplementedError()

    def verify_shutdown(self) -> None:
        """Implementation of the 'shutdown' verification check"""
        raise NotImplementedError()
