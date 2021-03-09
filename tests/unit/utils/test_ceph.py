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
"""Ceph helper test suite."""
import os
from unittest import mock
from unittest.mock import MagicMock

import pytest

from juju_verify.utils.ceph import check_cluster_health
from juju_verify.utils.unit import parse_charm_name
from juju_verify.verifiers.result import Result


@mock.patch("juju_verify.utils.ceph.run_action_on_units")
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

    result = check_cluster_health(model.units["ceph-mon/0"])

    assert result == exp_result


@mock.patch("juju_verify.utils.ceph.run_action_on_units")
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

    result = check_cluster_health(model.units["ceph-mon/0"], model.units["ceph-mon/1"])

    assert result == exp_result


@mock.patch("juju_verify.utils.ceph.run_action_on_units")
def test_check_cluster_health_unknown_state(mock_run_action_on_units, model):
    """Test check Ceph cluster health in unknown state."""
    mock_run_action_on_units.return_value = {}

    result = check_cluster_health(model.units["ceph-mon/0"], model.units["ceph-mon/1"])

    assert result == Result(False, "Ceph cluster is in an unknown state")


@pytest.mark.parametrize("charm_url, exp_name", [
    ("cs:focal/nova-compute-141", "nova-compute"),
    ("cs:hacluster-74", "hacluster"),
])
def test_parse_charm_name(charm_url, exp_name):
    """Test function for parsing charm name from charm-ulr."""
    assert parse_charm_name(charm_url) == exp_name
