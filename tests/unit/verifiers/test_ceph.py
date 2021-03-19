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
import os
from unittest import mock
from unittest.mock import MagicMock

import pytest

from juju_verify.verifiers import CephOsd, Result
from juju_verify.verifiers.ceph import CephCommon


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
@pytest.mark.parametrize("message, exp_result", [
    ("HEALTH_OK ...", Result(True, "ceph-mon/0: Ceph cluster is healthy")),
    ("HEALTH_WARN ...", Result(False, "ceph-mon/0: Ceph cluster is unhealthy")),
    ("HEALTH_ERR ...", Result(False, "ceph-mon/0: Ceph cluster is unhealthy")),
    ("not valid message",
     Result(False, "ceph-mon/0: Ceph cluster is in an unknown state")),
])
def test_check_cluster_health(mock_run_action_on_units, message, exp_result, model):
    """Test check Ceph cluster health."""
    action = MagicMock()
    action.data.get.side_effect = {"results": {"message": message}}.get
    mock_run_action_on_units.return_value = {"ceph-mon/0": action}

    result = CephCommon.check_cluster_health(model.units["ceph-mon/0"])

    assert result == exp_result


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_check_cluster_health_combination(mock_run_action_on_units, model):
    """Test check Ceph cluster health combination of two diff state."""
    exp_result = Result(False,
                        os.linesep.join(["ceph-mon/0: Ceph cluster is healthy",
                                         "ceph-mon/1: Ceph cluster is unhealthy"]))
    action_healthy = MagicMock()
    action_healthy.data.get.side_effect = {"results": {"message": "HEALTH_OK"}}.get
    action_unhealthy = MagicMock()
    action_unhealthy.data.get.side_effect = {"results": {"message": "HEALTH_ERR"}}.get
    mock_run_action_on_units.return_value = {"ceph-mon/0": action_healthy,
                                             "ceph-mon/1": action_unhealthy}

    result = CephCommon.check_cluster_health(model.units["ceph-mon/0"],
                                             model.units["ceph-mon/1"])

    assert result == exp_result


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_check_cluster_health_unknown_state(mock_run_action_on_units, model):
    """Test check Ceph cluster health in unknown state."""
    mock_run_action_on_units.return_value = {}

    result = CephCommon.check_cluster_health(model.units["ceph-mon/0"],
                                             model.units["ceph-mon/1"])

    assert result == Result(False, "Ceph cluster is in an unknown state")


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
    assert units == {unit: ceph_mon_units[0] for unit in ceph_osd_units}


@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
def test_verify_reboot(mock_check_cluster_health, mock_get_ceph_mon_units, model):
    """Test reboot verification on CephOsd."""
    units = [model.units["ceph-osd/0"]]
    mock_get_ceph_mon_units.return_value = {unit: model.units["ceph-mon/0"]
                                            for unit in units}
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd(units).verify_reboot()

    assert result == Result(True, "Ceph cluster is healthy")


@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
def test_verify_shutdown(mock_check_cluster_health, mock_get_ceph_mon_units, model):
    """Test shutdown verification on CephOsd."""
    units = [model.units["ceph-osd/0"]]
    mock_get_ceph_mon_units.return_value = {unit: model.units["ceph-mon/0"]
                                            for unit in units}
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd(units).verify_shutdown()

    assert result == Result(True, "Ceph cluster is healthy")
