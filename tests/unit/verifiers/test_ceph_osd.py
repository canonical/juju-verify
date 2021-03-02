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
"""CephOsd verifier class test suite."""
import pytest
from juju.model import Model
from juju.unit import Unit

from juju_verify.verifiers import CephOsd


def test_verify_reboot():
    """Test reboot verification on CephOsd.

    This is a placeholder unit test.
    """
    unit = Unit('ceph-osd/0', Model())
    verifier = CephOsd([unit])

    with pytest.raises(NotImplementedError):
        verifier.verify_reboot()


def test_verify_shutdown():
    """Test shutdown verification on CephOsd.

    This is a placeholder unit test.
    """
    unit = Unit('ceph-osd/0', Model())
    verifier = CephOsd([unit])

    with pytest.raises(NotImplementedError):
        verifier.verify_shutdown()
