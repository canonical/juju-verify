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
