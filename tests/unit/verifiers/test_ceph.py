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
import json
import os
from unittest import mock
from unittest.mock import MagicMock

import pytest

from juju_verify.exceptions import CharmException
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


def test_check_cluster_health_error(model):
    """Test check Ceph cluster health raise CharmException."""
    with pytest.raises(CharmException):
        CephCommon.check_cluster_health(model.units["ceph-osd/0"])


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_get_replication_number(mock_run_action_on_units, model):
    """Test get minimum replication number from ceph-mon unit."""
    action = MagicMock()
    action.data.get.side_effect = {"results": {"pools": json.dumps([
        {"pool": 1, "name": "test_1", "size": 5, "min_size": 2},
        {"pool": 2, "name": "test_2", "size": 5, "min_size": 2},
        {"pool": 3, "name": "test_3", "size": 3, "min_size": 2},
    ])}}.get
    mock_run_action_on_units.return_value = {"ceph-mon/0": action}

    # test find minimum replication in list of 3 pools
    assert CephCommon.get_replication_number(model.units["ceph-mon/0"]) == 1

    # test return None if list of pools is empty
    action.data.get.side_effect = {"results": {"pools": json.dumps([])}}.get
    assert CephCommon.get_replication_number(model.units["ceph-mon/0"]) is None


def test_get_replication_number_error(model):
    """Test get minimum replication number from ceph-mon unit raise CharmException."""
    with pytest.raises(CharmException):
        CephCommon.get_replication_number(model.units["ceph-osd/0"])


def test_get_ceph_mon_unit(model):
    """Test get ceph-mon unit related to application."""
    ceph_mon_units = [model.units["ceph-mon/0"], model.units["ceph-mon/1"],
                      model.units["ceph-mon/2"]]
    mock_relation = MagicMock()
    mock_relation.matches = {"ceph-osd:mon": True}.get
    mock_relation.provides.application.units = ceph_mon_units
    mock_relations = MagicMock()
    mock_relations.relations = [mock_relation]
    model.applications = {"ceph-osd": mock_relations}

    # return first ceph-mon unit in "ceph-osd:mon" relations
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd")
    assert unit == ceph_mon_units[0]

    # return none for non-existent application name
    model.applications = {"ceph-osd-cluster": mock_relations}
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd")
    assert unit is None

    # return none for application with no units
    mock_relation.provides.application.units = []
    model.applications = {"ceph-osd": mock_relations}
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd")
    assert unit is None


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_unit")
def test_get_ceph_mon_units(mock_get_ceph_mon_unit, model):
    """Test function to get ceph-mon units related to verified units."""
    ceph_osd_units = [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]
    mock_get_ceph_mon_unit.return_value = model.units["ceph-mon/0"]

    units = CephOsd(ceph_osd_units).get_ceph_mon_units()

    assert units == {"ceph-osd": model.units["ceph-mon/0"]}


@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_replication_number")
def test_check_replication_number(mock_get_replication_number, model):
    """Test check the minimum number of replications for related applications."""
    mock_get_replication_number.return_value = 1
    ceph_mon_app_map = {"ceph-osd": model.units["ceph-mon/0"]}
    ceph_osd_units = [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]

    # verified one ceph-osd unit
    result = CephOsd(ceph_osd_units[:1]).check_replication_number(ceph_mon_app_map)
    assert result == Result(True)

    # verified two ceph-osd unit
    result = CephOsd(ceph_osd_units).check_replication_number(ceph_mon_app_map)
    assert result == Result(False,
                            "The minimum number of replications in 'ceph-osd' is 1 and "
                            "it's not safe to restart/shutdown 2 units.")


@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_replication_number")
def test_verify_reboot(
        mock_get_replication_number,
        mock_check_cluster_health,
        mock_get_ceph_mon_units,
        model
):
    """Test reboot verification on CephOsd."""
    mock_get_replication_number.return_value = 1
    mock_get_ceph_mon_units.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd([model.units["ceph-osd/0"]]).verify_reboot()
    assert result == Result(True, "Ceph cluster is healthy")

    mock_get_replication_number.return_value = None  # empty list of pools
    result = CephOsd([model.units["ceph-osd/0"]]).verify_reboot()
    assert result == Result(True, "Ceph cluster is healthy")


@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_ceph_mon_units")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_replication_number")
def test_verify_shutdown(
        mock_get_replication_number,
        mock_check_cluster_health,
        mock_get_ceph_mon_units,
        model
):
    """Test shutdown verification on CephOsd."""
    mock_get_replication_number.return_value = 1
    mock_get_ceph_mon_units.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    mock_check_cluster_health.return_value = Result(True, "Ceph cluster is healthy")

    result = CephOsd([model.units["ceph-osd/0"]]).verify_shutdown()
    assert result == Result(True, "Ceph cluster is healthy")

    mock_get_replication_number.return_value = None  # empty list of pools
    result = CephOsd([model.units["ceph-osd/0"]]).verify_shutdown()
    assert result == Result(True, "Ceph cluster is healthy")
