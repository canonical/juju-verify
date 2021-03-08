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
from unittest import mock
from unittest.mock import MagicMock

from juju_verify.verifiers import CephOsd, Result


def test_get_ceph_mon_units(model):
    """Test function to get ceph-mon units related to verified units."""
    ceph_osd_units = [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]
    ceph_mon_units = [model.units["ceph-mon/0"], model.units["ceph-mon/1"],
                      model.units["ceph-mon/2"]]
    mock_relation = MagicMock()
    mock_relation.matches = {"ceph-osd:mon": True}.get
    mock_relation.provides.application.units = ceph_mon_units
    model.relations = [mock_relation]

    units = CephOsd(ceph_osd_units).get_ceph_mon_units()
    assert {ceph_mon_units[0]} == units


@mock.patch("juju_verify.verifiers.ceph_osd.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph_osd.check_cluster_health")
def test_verify_reboot(mock_check_cluster_health, mock_get_ceph_mon_units, model):
    """Test reboot verification on CephOsd."""
    mock_get_ceph_mon_units.return_value = [model.units["ceph-mon/0"]]
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd([model.units["ceph-osd/0"]]).verify_reboot()

    assert result == Result(True, "Ceph cluster is healthy")


@mock.patch("juju_verify.verifiers.ceph_osd.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph_osd.check_cluster_health")
def test_verify_shutdown(mock_check_cluster_health, mock_get_ceph_mon_units, model):
    """Test shutdown verification on CephOsd."""
    mock_get_ceph_mon_units.return_value = [model.units["ceph-mon/0"]]
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd([model.units["ceph-osd/0"]]).verify_shutdown()

    assert result == Result(True, "Ceph cluster is healthy")
