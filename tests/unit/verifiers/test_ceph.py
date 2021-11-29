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
from unittest.mock import MagicMock, PropertyMock

import pytest
from juju.errors import JujuError
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import CharmException, JujuActionFailed
from juju_verify.verifiers.ceph import (
    AvailabilityZone,
    CephCommon,
    CephMon,
    CephOsd,
    NodeInfo,
)
from juju_verify.verifiers.result import Result, Severity

CEPH_MON_QUORUM_OK = "Ceph-mon quorum check passed."
CEPH_MON_QUORUM_FAIL = "Removing unit {} will lose Ceph mon quorum"
JUJU_VERSION_ERR = (
    "The machine for unit {} does not have a hostname attribute, "
    "please ensure that Juju controller is 2.8.10 or higher."
)
TEST_NODES_OUTPUT = [
    {
        "id": -1,
        "name": "default",
        "type_id": 10,
        "type": "root",
        "kb": 100,
        "kb_used": 60,
        "kb_avail": 40,
        "children": [-2, -3],
    },
    {
        "id": -2,
        "name": "rack.1",
        "type_id": 3,
        "type": "rack",
        "kb": 50,
        "kb_used": 45,
        "kb_avail": 5,
        "children": [0, 1],
    },
    {
        "id": 0,
        "name": "osd.0",
        "type_id": 0,
        "type": "osd",
        "kb": 25,
        "kb_used": 23,
        "kb_avail": 2,
    },
    {
        "id": 1,
        "name": "osd.1",
        "type_id": 0,
        "type": "osd",
        "kb": 25,
        "kb_used": 22,
        "kb_avail": 3,
    },
    {
        "id": -3,
        "name": "rack.2",
        "type_id": 3,
        "type": "rack",
        "kb": 50,
        "kb_used": 15,
        "kb_avail": 35,
        "children": [2, 3],
    },
    {
        "id": 2,
        "name": "osd.2",
        "type_id": 0,
        "type": "osd",
        "kb": 35,
        "kb_used": 7,
        "kb_avail": 28,
    },
    {
        "id": 3,
        "name": "osd.3",
        "type_id": 0,
        "type": "osd",
        "kb": 15,
        "kb_used": 8,
        "kb_avail": 7,
    },
]


def test_node_info():
    """Test initialization of NodeInfo and comparison."""
    node = {
        "id": 10,
        "name": "osd.0",
        "type": "osd",
        "type_id": 0,
        "kb": 10485760,
        "kb_used": 1051648,
        "kb_avail": 9434112,
    }
    node_info = NodeInfo(**node)

    assert node_info.id == 10
    assert node_info == NodeInfo(**node)
    assert str(node_info) == "0-osd.0(10)"
    assert hash(node_info) == hash("0-osd.0(10)")


def test_availability_zone_method():
    """Test AvailabilityZone object method, e.g. __str__, __eq__, ..."""
    nodes = [
        NodeInfo(**node)
        for node in sorted(
            TEST_NODES_OUTPUT, key=lambda node: node["type_id"], reverse=True
        )
    ]
    az_str = ",".join(str(node) for node in nodes)
    az = AvailabilityZone(nodes=nodes)

    assert az is not None
    assert az == AvailabilityZone(nodes)
    assert az != NodeInfo(**TEST_NODES_OUTPUT[0])
    assert az != az_str
    assert str(az) == az_str
    assert hash(az) == hash(az_str)


@pytest.mark.parametrize(
    "exp_child, exp_parent, can_remove_node",
    [
        ("rack.1", "default", False),
        ("osd.0", "rack.1", False),
        ("osd.2", "rack.2", False),
        ("osd.3", "rack.2", True),
    ],
)
def test_availability_zone(exp_child, exp_parent, can_remove_node):
    """Test AvailabilityZone object."""
    nodes = [
        NodeInfo(**node)
        for node in sorted(
            TEST_NODES_OUTPUT, key=lambda node: node["type_id"], reverse=True
        )
    ]
    az = AvailabilityZone(nodes=nodes)
    child = az.get_nodes(exp_child)[0]

    assert exp_child == child.name
    assert exp_parent == az.find_parent(child.id).name
    assert can_remove_node == az.can_remove_node(exp_child)

    with pytest.raises(KeyError):
        az.get_nodes("not-valid-child-name")

    with pytest.raises(KeyError):
        az.can_remove_node("not-valid-child-name")

    # try to find parent for root
    assert az.find_parent(-1) is None
    # test if root could be removed
    assert az.can_remove_node("default") is False


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
@pytest.mark.parametrize(
    "message, exp_result",
    [
        ("HEALTH_OK ...", Result(Severity.OK, "ceph-mon/0: Ceph cluster is healthy")),
        (
            "HEALTH_WARN ...",
            Result(
                Severity.WARN,
                f"ceph-mon/0: Ceph cluster is in a warning state"
                f"{os.linesep}  HEALTH_WARN ...",
            ),
        ),
        (
            "HEALTH_ERR ...",
            Result(
                Severity.FAIL,
                f"ceph-mon/0: Ceph cluster is unhealthy{os.linesep}  HEALTH_ERR ...",
            ),
        ),
        (
            "not valid message",
            Result(
                Severity.FAIL,
                f"ceph-mon/0: Ceph cluster is in an unknown state"
                f"{os.linesep}  not valid message",
            ),
        ),
    ],
)
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
    exp_result = Result()
    exp_result.add_partial_result(Severity.OK, "ceph-mon/0: Ceph cluster is healthy")
    exp_result.add_partial_result(
        Severity.FAIL, f"ceph-mon/1: Ceph cluster is unhealthy{os.linesep}  HEALTH_ERR"
    )

    action_healthy = MagicMock()
    action_healthy.data.get.side_effect = {"results": {"message": "HEALTH_OK"}}.get
    action_unhealthy = MagicMock()
    action_unhealthy.data.get.side_effect = {"results": {"message": "HEALTH_ERR"}}.get
    mock_run_action_on_units.return_value = {
        "ceph-mon/0": action_healthy,
        "ceph-mon/1": action_unhealthy,
    }

    result = CephCommon.check_cluster_health(
        model.units["ceph-mon/0"], model.units["ceph-mon/1"]
    )

    assert result == exp_result


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_check_cluster_health_unknown_state(mock_run_action_on_units, model):
    """Test check Ceph cluster health in unknown state."""
    mock_run_action_on_units.return_value = {}

    result = CephCommon.check_cluster_health(
        model.units["ceph-mon/0"], model.units["ceph-mon/1"]
    )

    assert result == Result(Severity.FAIL, "Ceph cluster status could not be obtained")


def test_check_cluster_health_error(model):
    """Test check Ceph cluster health raise CharmException."""
    model.units["ceph-mon/0"].run_action.side_effect = JujuError("action not exists")
    with pytest.raises(JujuActionFailed):
        CephCommon.check_cluster_health(model.units["ceph-mon/0"])


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_get_replication_number(mock_run_action_on_units, model):
    """Test get minimum replication number from ceph-mon unit."""
    action = MagicMock()
    action.data.get.side_effect = {
        "results": {
            "message": json.dumps(
                [
                    {"pool": 1, "name": "test_1", "size": 5, "min_size": 2},
                    {"pool": 2, "name": "test_2", "size": 5, "min_size": 2},
                    {"pool": 3, "name": "test_3", "size": 3, "min_size": 2},
                ]
            )
        }
    }.get
    mock_run_action_on_units.return_value = {"ceph-mon/0": action}

    # test find minimum replication in list of 3 pools
    assert CephCommon.get_replication_number(model.units["ceph-mon/0"]) == 1

    # test return None if list of pools is empty
    action.data.get.side_effect = {"results": {"message": json.dumps([])}}.get
    assert CephCommon.get_replication_number(model.units["ceph-mon/0"]) is None


def test_get_replication_number_error(model):
    """Test get minimum replication number from ceph-mon unit raise CharmException."""
    with pytest.raises(CharmException):
        CephCommon.get_replication_number(model.units["ceph-osd/0"])


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_get_disk_utilization(mock_run_action_on_units, model):
    """Test get disk utilization for ceph."""
    action = MagicMock()
    action.data.get.side_effect = {
        "results": {
            "message": json.dumps(
                {
                    "nodes": [
                        {
                            "id": -1,
                            "name": "default",
                            "type": "root",
                            "type_id": 10,
                            "reweight": -1.000000,
                            "kb": 31457280,
                            "kb_used": 3154944,
                            "kb_used_data": 9024,
                            "kb_used_omap": 0,
                            "kb_used_meta": 3145728,
                            "kb_avail": 28302336,
                            "utilization": 10.029297,
                            "var": 1.000000,
                            "pgs": 0,
                            "children": [-7, -3, -5],
                        },
                        {
                            "id": -3,
                            "name": "juju-2ecfef-zaza-a0e73f67a6c0-1",
                            "type": "host",
                            "type_id": 1,
                            "pool_weights": {},
                            "reweight": -1.000000,
                            "kb": 10485760,
                            "kb_used": 1051648,
                            "kb_used_data": 3008,
                            "kb_used_omap": 0,
                            "kb_used_meta": 1048576,
                            "kb_avail": 9434112,
                            "utilization": 10.029297,
                            "var": 1.000000,
                            "pgs": 0,
                            "children": [0],
                        },
                        {
                            "id": 0,
                            "device_class": "hdd",
                            "name": "osd.0",
                            "type": "osd",
                            "type_id": 0,
                            "crush_weight": 0.009796,
                            "depth": 2,
                            "pool_weights": {},
                            "reweight": 1.000000,
                            "kb": 10485760,
                            "kb_used": 1051648,
                            "kb_used_data": 3008,
                            "kb_used_omap": 0,
                            "kb_used_meta": 1048576,
                            "kb_avail": 9434112,
                            "utilization": 10.029297,
                            "var": 1.000000,
                            "pgs": 0,
                        },
                    ],
                    "stray": [],
                    "summary": {
                        "total_kb": 31457280,
                        "total_kb_used": 3154944,
                        "total_kb_used_data": 9024,
                        "total_kb_used_omap": 0,
                        "total_kb_used_meta": 3145728,
                        "total_kb_avail": 28302336,
                        "average_utilization": 10.029297,
                        "min_var": 1.000000,
                        "max_var": 1.000000,
                        "dev": 0.000000,
                    },
                }
            )
        }
    }.get
    mock_run_action_on_units.return_value = {"ceph-mon/0": action}

    nodes = CephCommon.get_disk_utilization(model.units["ceph-mon/0"])
    assert any(
        node.name == "juju-2ecfef-zaza-a0e73f67a6c0-1" and node.children == [0]
        for node in nodes
    )
    assert any(node.name == "osd.0" and node.id == 0 for node in nodes)


def test_get_ceph_mon_unit(model):
    """Test get ceph-mon unit related to application."""
    ceph_mon_units = [
        model.units["ceph-mon/0"],
        model.units["ceph-mon/1"],
        model.units["ceph-mon/2"],
    ]
    mock_relation = MagicMock()
    mock_relation.matches = {"ceph-osd:mon": True}.get
    mock_relation.provides.application.units = ceph_mon_units
    model.applications["ceph-osd"].relations = [mock_relation]

    # return first ceph-mon unit in "ceph-osd:mon" relations
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd")
    assert unit == ceph_mon_units[0]

    # return none for non-existent application name
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd-cluster")
    assert unit is None

    # return none for application with no units
    mock_relation.provides.application.units = []
    unit = CephOsd([model.units["ceph-osd/0"]])._get_ceph_mon_unit("ceph-osd")
    assert unit is None


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_unit")
def test_get_ceph_mon_app_map(mock_get_ceph_mon_unit, model):
    """Test function to get ceph-mon units related to verified units."""
    ceph_osd_units = [
        model.units["ceph-osd/0"],
        model.units["ceph-osd/1"],
        model.units["ceph-osd-hdd/0"],
    ]
    mock_get_ceph_mon_unit.return_value = model.units["ceph-mon/0"]

    units = CephOsd(ceph_osd_units)._get_ceph_mon_app_map()

    assert units == {
        "ceph-osd": model.units["ceph-mon/0"],
        "ceph-osd-hdd": model.units["ceph-mon/0"],
    }


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_app_map")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
def test_check_ceph_cluster_health(
    mock_check_cluster_health, mock_get_ceph_mon_app_map, model
):
    """Test check the Ceph cluster health for unique ceph-mon units."""
    expected_result = Result(Severity.OK, "foo")
    mock_get_ceph_mon_app_map.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    mock_check_cluster_health.return_value = expected_result

    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    assert ceph_osd_verifier.check_ceph_cluster_health() == expected_result
    mock_check_cluster_health.assert_called_once_with(model.units["ceph-mon/0"])


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_app_map")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_replication_number")
def test_check_replication_number(
    mock_get_replication_number, mock_get_ceph_mon_app_map, model
):
    """Test check the minimum number of replications for related applications."""
    check_passed_result = Result(Severity.OK, "Minimum replica number check passed.")
    mock_get_ceph_mon_app_map.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    mock_get_replication_number.return_value = None

    # [min_replication_number=None] verified one ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result

    # [min_replication_number=None] verified two ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"], model.units["ceph-osd/1"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result

    mock_get_replication_number.return_value = 1

    # [min_replication_number=1] verified one ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result

    # [min_replication_number=1] verified two ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"], model.units["ceph-osd/1"]])
    expected_fail_result = Result(
        Severity.FAIL,
        "The minimum number of replicas in 'ceph-osd' is 1 and it's not safe to "
        "reboot/shutdown 2 units. 0 units are not active.",
    )
    assert ceph_osd_verifier.check_replication_number() == expected_fail_result

    # [min_replication_number=1] verified one ceph-osd unit,
    # if there is an unit that is not in an active state
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "blocked"
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    expected_fail_result = Result(
        Severity.FAIL,
        "The minimum number of replicas in 'ceph-osd' is 1 and it's not safe to "
        "reboot/shutdown 1 units. 1 units are not active.",
    )
    assert ceph_osd_verifier.check_replication_number() == expected_fail_result

    # [min_replication_number=1] verified one ceph-osd unit that is not active
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/1"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "active"

    mock_get_replication_number.return_value = 2

    # [min_replication_number=2] verified two ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"], model.units["ceph-osd/1"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_app_map")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_disk_utilization")
def test_check_availability_zone(
    mock_get_disk_utilization, mock_get_ceph_mon_app_map, model
):
    """Test check removing unit from availability zone."""
    mock_get_disk_utilization.return_value = [
        NodeInfo(**node) for node in TEST_NODES_OUTPUT
    ]

    # test empty ceph_mon_app_map, aka default result
    mock_get_ceph_mon_app_map.return_value = {}

    result = CephOsd([model.units["ceph-osd/0"]]).check_availability_zone()
    assert result == Result(Severity.OK, "Availability zone check passed.")

    # test to remove unit, which could be removed
    mock_get_ceph_mon_app_map.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    unit = model.units["ceph-osd/0"]
    unit.machine = mock.PropertyMock(hostname="osd.3")

    result = CephOsd([unit]).check_availability_zone()
    assert result == Result(Severity.OK, "Availability zone check passed.")

    # test removing multiple units from which one could not be removed
    mock_get_ceph_mon_app_map.return_value = {
        "ceph-osd-hdd": model.units["ceph-mon/0"],
        "ceph-osd-ssd": model.units["ceph-mon/0"],
    }
    unit_1 = model.units["ceph-osd-hdd/0"]
    unit_1.machine = mock.PropertyMock(hostname="osd.0")
    unit_2 = model.units["ceph-osd-ssd/1"]
    unit_2.machine = mock.PropertyMock(hostname="osd.3")

    result = CephOsd([unit_1, unit_2]).check_availability_zone()
    assert result == Result(
        Severity.FAIL,
        "It's not safe to reboot/shutdown unit(s) ceph-osd-hdd/0 in the availability "
        "zone '10-default(-1),3-rack.1(-2),3-rack.2(-3),0-osd.0(0),0-osd.1(1),"
        "0-osd.2(2),0-osd.3(3)'.",
    )

    # test removing multiple units from same application and both could not be removed
    mock_get_ceph_mon_app_map.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    unit_1 = model.units["ceph-osd/0"]
    unit_1.machine = mock.PropertyMock(hostname="osd.0")
    unit_2 = model.units["ceph-osd/1"]
    unit_2.machine = mock.PropertyMock(hostname="osd.1")
    result = CephOsd([unit_1, unit_2]).check_availability_zone()
    assert result == Result(
        Severity.FAIL,
        "It's not safe to reboot/shutdown unit(s) ceph-osd/0, ceph-osd/1 in the "
        "availability zone '10-default(-1),3-rack.1(-2),3-rack.2(-3),"
        "0-osd.0(0),0-osd.1(1),0-osd.2(2),0-osd.3(3)'.",
    )


@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_ceph_cluster_health",
    return_value=Result(Severity.OK, "Ceph cluster is healthy"),
)
@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_replication_number",
    return_value=Result(Severity.OK, "Minimum replica number check passed."),
)
@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_availability_zone",
    return_value=Result(Severity.OK, "Availability zone check passed."),
)
def test_verify_reboot(
    mock_check_availability_zone,
    mock_check_replication_number,
    mock_check_ceph_cluster_health,
    model,
):
    """Test reboot verification on CephOsd."""
    result = CephOsd([model.units["ceph-osd/0"]]).verify_reboot()
    expected_result = Result()
    expected_result.add_partial_result(Severity.OK, "Ceph cluster is healthy")
    expected_result.add_partial_result(
        Severity.OK, "Minimum replica number check passed."
    )
    expected_result.add_partial_result(Severity.OK, "Availability zone check passed.")
    assert result == expected_result
    mock_check_ceph_cluster_health.assert_called_once_with()
    mock_check_replication_number.assert_called_once_with()
    mock_check_availability_zone.assert_called_once_with()


@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_ceph_cluster_health",
    return_value=Result(Severity.OK, "Ceph cluster is healthy"),
)
@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_replication_number",
    return_value=Result(Severity.OK, "Minimum replica number check passed."),
)
@mock.patch(
    "juju_verify.verifiers.ceph.CephOsd.check_availability_zone",
    return_value=Result(Severity.OK, "Availability zone check passed."),
)
def test_verify_shutdown(
    mock_check_availability_zone,
    mock_check_replication_number,
    mock_check_ceph_cluster_health,
    model,
):
    """Test shutdown verification on CephOsd."""
    result = CephOsd([model.units["ceph-osd/0"]]).verify_shutdown()
    expected_result = Result()
    expected_result.add_partial_result(Severity.OK, "Ceph cluster is healthy")
    expected_result.add_partial_result(
        Severity.OK, "Minimum replica number check passed."
    )
    expected_result.add_partial_result(Severity.OK, "Availability zone check passed.")
    assert result == expected_result
    mock_check_ceph_cluster_health.assert_called_once_with()
    mock_check_replication_number.assert_called_once_with()
    mock_check_availability_zone.assert_called_once_with()


@pytest.mark.parametrize(
    "action_output, exp_output",
    [
        ('{"quorum_names": ["host0"], "monmap": {"mons": []}}', (0, {"host0"})),
        (
            '{"quorum_names": ["host0", "host1", "host2"], '
            '"monmap": {"mons": [{"name": "host0"}, {"name": "host1"}, '
            '{"name": "host2"}]}}',
            (3, {"host0", "host1", "host2"}),
        ),
        (
            '{"quorum_names": ["host0", "host1", "host1"], '
            '"monmap": {"mons": [{"name": "host0"}, {"name": "host1"}, '
            '{"name": "host2"}]}}',
            (3, {"host0", "host1"}),
        ),
    ],
)
def test_parse_quorum_status(action_output, exp_output):
    """Test function to parse `get-quorum-status` action output."""
    mock_action = MagicMock()
    mock_action.data = {"results": {"message": action_output}}

    unit = Unit("ceph-mon/0", Model())
    verifier = CephMon([unit])
    mon_count, online_mons = verifier._parse_quorum_status(mock_action)

    assert (mon_count, online_mons) == exp_output


@pytest.mark.parametrize(
    "mon_count, online_mons, severity, msg, hostname",
    [
        (3, {"host0", "host1", "host2"}, Severity.OK, CEPH_MON_QUORUM_OK, "host1"),
        (2, {"host0", "host1"}, Severity.FAIL, CEPH_MON_QUORUM_FAIL, "host1"),
        (3, {"host0", "host1", "host2"}, Severity.OK, CEPH_MON_QUORUM_OK, "host5"),
    ],
)
def test_check_ceph_mon_quorum(mocker, mon_count, online_mons, severity, msg, hostname):
    """Test Ceph quorum verification on CephMon."""
    unit_to_remove = "ceph-mon/0"
    unit = Unit(unit_to_remove, Model())
    verifier = CephMon([unit])
    mocker.patch.object(verifier, "run_action_on_all").return_value = {
        unit_to_remove: None
    }
    mocker.patch.object(verifier, "_parse_quorum_status").return_value = (
        mon_count,
        online_mons,
    )
    unit.machine = mock.PropertyMock(hostname=hostname)

    expected_msg = msg if severity == Severity.OK else msg.format(unit_to_remove)
    expected_result = Result(severity, expected_msg)
    result = verifier.check_quorum()
    assert result == expected_result


def test_check_ceph_mon_quorum_failed_to_parse_action(mocker):
    """Test Ceph quorum verification on CephMon."""
    unit_to_remove = "ceph-mon/0"
    unit = Unit(unit_to_remove, Model())
    verifier = CephMon([unit])
    mock_action = MagicMock()
    mock_action.entity_id = 12
    mocker.patch.object(verifier, "run_action_on_all").return_value = {
        unit_to_remove: mock_action
    }
    mocker.patch.object(verifier, "_parse_quorum_status").side_effect = KeyError(
        "monmap"
    )

    result = verifier.check_quorum()
    assert result == Result(
        Severity.FAIL, "Failed to parse quorum status from action 12."
    )


@pytest.mark.parametrize(
    "juju_version, expected_severity",
    [
        pytest.param("2.8.0", Severity.FAIL, id="version-low"),
        pytest.param("2.8.10", Severity.OK, id="version-match"),
        pytest.param("2.8.11", Severity.OK, id="version-high"),
    ],
)
def test_ceph_mon_version_check(juju_version, expected_severity, mocker):
    """Test expected results of ceph-mon juju version check."""
    mock_unit_data = {"agent-status": {"version": juju_version}}
    mocker.patch.object(
        Unit, "safe_data", new_callable=PropertyMock(return_value=mock_unit_data)
    )
    unit_name = "ceph-mon/0"
    if expected_severity == Severity.OK:
        expected_result = Result(Severity.OK, "Minimum juju version check passed.")
    else:
        fail_msg = (
            f"Juju agent on unit {unit_name} has lower than "
            f"minimum required version. {juju_version} < 2.8.10"
        )
        expected_result = Result(Severity.FAIL, fail_msg)

    verifier = CephMon([Unit(unit_name, Model())])
    result = verifier.check_version()

    assert result == expected_result


def test_ceph_mon_fail_version_parsing(mocker):
    """Test that exception is raised if parsing of juju version fails."""
    bogus_version = "foo"
    unit_name = "ceph-mon/0"
    mock_unit_data = {"agent-status": {"version": bogus_version}}
    mocker.patch.object(
        Unit, "safe_data", new_callable=PropertyMock(return_value=mock_unit_data)
    )

    verifier = CephMon([Unit(unit_name, Model())])
    with pytest.raises(CharmException) as exc:
        verifier.check_version()
        assert str(exc.value) == f"Failed to parse juju version from unit {unit_name}."


def test_verify_ceph_mon_shutdown(mocker):
    """Test that verify_shutdown links to verify_reboot."""
    mocker.patch.object(CephMon, "verify_reboot")
    unit = Unit("ceph-mon/0", Model())
    verifier = CephMon([unit])
    verifier.verify_shutdown()
    verifier.verify_reboot.assert_called_once()


@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_quorum")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_version")
def test_verify_ceph_mon_reboot(mock_version, mock_quorum, mock_health):
    """Test reboot verification on CephMon."""
    unit = Unit("ceph-mon/0", Model())
    mock_health.return_value = Result(Severity.OK, "Ceph cluster is healthy")
    mock_quorum.return_value = Result(Severity.OK, "Ceph-mon quorum check passed.")
    mock_version.return_value = Result(
        Severity.OK, "Minimum juju version check passed."
    )
    verifier = CephMon([unit])
    result = verifier.verify_reboot()

    expected_result = Result()
    expected_result.add_partial_result(
        Severity.OK, "Minimum juju version check passed."
    )
    expected_result.add_partial_result(Severity.OK, "Ceph-mon quorum check passed.")
    expected_result.add_partial_result(Severity.OK, "Ceph cluster is healthy")

    assert result == expected_result


@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_quorum")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_version")
def test_verify_ceph_mon_reboot_stops_on_failed_version(
    mock_version, mock_quorum, mock_health
):
    """Test that if ceph-mon version check fails, not other checks are performed."""
    expected_result = Result(Severity.FAIL, "version too low")
    mock_version.return_value = expected_result

    verifier = CephMon([Unit("ceph-mon/0", Model())])
    result = verifier.verify_reboot()

    assert result == expected_result
    mock_version.assert_called_once()
    mock_quorum.assert_not_called()
    mock_health.assert_not_called()


@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_quorum")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_version")
def test_verify_ceph_mon_reboot_checks_health_once(
    mock_version, mock_quorum, mock_health, mocker
):
    """Test that ceph-mon verification runs 'health check' only once per application."""
    model = Model()
    app_1 = [Unit("ceph-mon/0", model), Unit("ceph-mon/1", model)]
    app_2 = [Unit("ceph-mon-extra/0", model), Unit("ceph-mon-extra/1", model)]
    expected_health_check_units = [app_1[-1], app_2[-1]]

    for unit in app_1:
        mocker.patch.object(
            unit,
            "data",
            new_callable=PropertyMock(return_value={"application": "ceph-mon"}),
        )

    for unit in app_2:
        mocker.patch.object(
            unit,
            "data",
            new_callable=PropertyMock(return_value={"application": "ceph-mon-extra"}),
        )

    verifier = CephMon(app_1 + app_2)
    result = verifier.verify_reboot()

    assert result.success
    mock_version.assert_called_once()
    mock_quorum.assert_called_once()
    mock_health.assert_called_with(*expected_health_check_units)
