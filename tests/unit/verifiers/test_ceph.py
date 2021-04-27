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
from unittest import mock
from unittest.mock import MagicMock

import pytest
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import CharmException
from juju_verify.verifiers.ceph import AvailabilityZone, CephCommon, CephOsd, CephMon
from juju_verify.verifiers.result import Result, Severity


@pytest.mark.parametrize("az_info, ex_az", [
    ({"root": "default", "host": "test"}, "root=default,host=test"),
    ({"root": "default", "rack": "nova", "row": "row1", "host": "test"},
     "root=default,row=row1,rack=nova,host=test"),
    ({"root": "default", "skip_argument": "test"}, "root=default"),
])
def test_az(az_info, ex_az):
    """Test availability zone object."""
    availability_zone = AvailabilityZone(**az_info)
    assert str(availability_zone) == ex_az
    assert hash(availability_zone) == hash(ex_az)


def test_az_getattr():
    """Test get attribute from AZ."""
    availability_zone = AvailabilityZone(root="default", host="juju-1", test="test")
    assert availability_zone.root == "default"
    assert availability_zone.host == "juju-1"
    with pytest.raises(AttributeError):
        assert availability_zone.test == "test"


def test_az_eq():
    """Test AZ.__eq__."""
    assert AvailabilityZone(root="default", host="juju-1") == \
           AvailabilityZone(root="default", host="juju-1")
    assert AvailabilityZone(root="default", host="juju-1") != \
           AvailabilityZone(root="default", host="juju-2")
    assert AvailabilityZone(root="default", host="juju-1") is not None
    assert AvailabilityZone(root="default", host="juju-1") != 1
    assert AvailabilityZone(root="default", host="juju-1") != "root=default,host=juju-1"


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
@pytest.mark.parametrize("message, exp_result", [
    ("HEALTH_OK ...", Result(Severity.OK, "ceph-mon/0: Ceph cluster is healthy")),
    ("HEALTH_WARN ...", Result(Severity.FAIL, "ceph-mon/0: Ceph cluster is unhealthy")),
    ("HEALTH_ERR ...", Result(Severity.FAIL, "ceph-mon/0: Ceph cluster is unhealthy")),
    ("not valid message",
     Result(Severity.FAIL, "ceph-mon/0: Ceph cluster is in an unknown state")),
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
    exp_result = Result()
    exp_result.add_partial_result(Severity.OK, "ceph-mon/0: Ceph cluster is healthy")
    exp_result.add_partial_result(Severity.FAIL, "ceph-mon/1: Ceph cluster is unhealthy")

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

    assert result == Result(Severity.FAIL, "Ceph cluster is in an unknown state")


def test_check_cluster_health_error(model):
    """Test check Ceph cluster health raise CharmException."""
    with pytest.raises(CharmException):
        CephCommon.check_cluster_health(model.units["ceph-osd/0"])


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_get_replication_number(mock_run_action_on_units, model):
    """Test get minimum replication number from ceph-mon unit."""
    action = MagicMock()
    action.data.get.side_effect = {"results": {"message": json.dumps([
        {"pool": 1, "name": "test_1", "size": 5, "min_size": 2},
        {"pool": 2, "name": "test_2", "size": 5, "min_size": 2},
        {"pool": 3, "name": "test_3", "size": 3, "min_size": 2},
    ])}}.get
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


def test_get_number_of_free_units(model):
    """Test get number of free units from ceph df."""
    assert CephCommon.get_number_of_free_units(model.units["ceph-mon/0"])

    with pytest.raises(CharmException):
        CephCommon.get_number_of_free_units(model.units["ceph-osd/0"])


@mock.patch("juju_verify.verifiers.ceph.run_action_on_units")
def test_get_availability_zones(mock_run_action_on_units, model):
    """Test get information about availability zones for ceph-osd units."""
    mock_action = MagicMock()
    mock_action.data.get.side_effect = {"results": {"availability-zone": json.dumps(
        {"unit": {"root": "default", "rack": "nova", "host": "test"}})}}.get
    mock_run_action_on_units.return_value = {"ceph-osd/0": mock_action}

    availability_zone = CephCommon.get_availability_zones(model.units["ceph-osd/0"])
    assert availability_zone["ceph-osd/0"] == AvailabilityZone(root="default",
                                                               rack="nova")


def test_get_ceph_mon_unit(model):
    """Test get ceph-mon unit related to application."""
    ceph_mon_units = [model.units["ceph-mon/0"], model.units["ceph-mon/1"],
                      model.units["ceph-mon/2"]]
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
    ceph_osd_units = [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]
    mock_get_ceph_mon_unit.return_value = model.units["ceph-mon/0"]

    units = CephOsd(ceph_osd_units)._get_ceph_mon_app_map()

    assert units == {"ceph-osd": model.units["ceph-mon/0"]}


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_app_map")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
def test_check_ceph_cluster_health(
        mock_check_cluster_health, mock_get_ceph_mon_app_map, model):
    """Test check the Ceph cluster health for unique ceph-mon units."""
    expected_result = Result(Severity.OK, 'foo')
    mock_get_ceph_mon_app_map.return_value = {"ceph-osd": model.units["ceph-mon/0"]}
    mock_check_cluster_health.return_value = expected_result

    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    assert ceph_osd_verifier.check_ceph_cluster_health() == expected_result
    mock_check_cluster_health.assert_called_once_with(model.units["ceph-mon/0"])


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_app_map")
@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_replication_number")
def test_check_replication_number(
        mock_get_replication_number, mock_get_ceph_mon_app_map, model):
    """Test check the minimum number of replications for related applications."""
    check_passed_result = Result(Severity.OK, 'Minimum replica number check passed.')
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
    expected_fail_result = Result(Severity.FAIL, "The minimum number of replicas in "
                                                 "'ceph-osd' is 1 and it's not safe to"
                                                 " restart/shutdown 2 units. 0 units "
                                                 "are not active.")
    assert ceph_osd_verifier.check_replication_number() == expected_fail_result

    # [min_replication_number=1] verified one ceph-osd unit,
    # if there is an unit that is not in an active state
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "blocked"
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"]])
    expected_fail_result = Result(Severity.FAIL, "The minimum number of replicas in "
                                                 "'ceph-osd' is 1 and it's not safe to "
                                                 "restart/shutdown 1 units. 1 units "
                                                 "are not active.")
    assert ceph_osd_verifier.check_replication_number() == expected_fail_result

    # [min_replication_number=1] verified one ceph-osd unit that is not active
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/1"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result
    model.units["ceph-osd/1"].data["workload-status"]["current"] = "active"

    mock_get_replication_number.return_value = 2

    # [min_replication_number=2] verified two ceph-osd unit
    ceph_osd_verifier = CephOsd([model.units["ceph-osd/0"], model.units["ceph-osd/1"]])
    assert ceph_osd_verifier.check_replication_number() == check_passed_result


@mock.patch("juju_verify.verifiers.ceph.CephOsd._get_ceph_mon_unit")
@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_number_of_free_units")
def test_get_free_app_units(
        mock_get_number_of_free_units, mock_get_ceph_mon_unit, model
):
    """Test get number of free units for each application."""
    mock_get_ceph_mon_unit.return_value = model.units["ceph-mon/0"]
    mock_get_number_of_free_units.return_value = 1

    free_units = CephOsd([model.units["ceph-osd/0"]]).get_free_app_units(["ceph-osd"])
    assert free_units == {"ceph-osd": 1}
    mock_get_number_of_free_units.assert_called_once_with(model.units["ceph-mon/0"])


@mock.patch("juju_verify.verifiers.ceph.CephCommon.get_availability_zones")
def test_get_apps_availability_zones(mock_get_availability_zones, model):
    """Test get information about availability zone for each unit in application."""
    exp_az = AvailabilityZone(root="default", rack="nova")
    mock_get_availability_zones.return_value = {
        "ceph-osd/0": exp_az, "ceph-osd/1": exp_az
    }
    azs = CephOsd([model.units["ceph-osd/0"]]).get_apps_availability_zones(["ceph-osd"])
    assert azs == {exp_az: [model.units["ceph-osd/0"], model.units["ceph-osd/1"]]}
    mock_get_availability_zones.assert_called_once_with(model.units["ceph-osd/0"],
                                                        model.units["ceph-osd/1"])


@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_free_app_units")
@mock.patch("juju_verify.verifiers.ceph.CephOsd.get_apps_availability_zones")
def test_check_availability_zone(
        mock_get_apps_availability_zones,
        mock_get_free_app_units,
        model
):
    """Test check availability zone resources."""
    mock_get_free_app_units.return_value = {"ceph-osd": 1}
    mock_get_apps_availability_zones.return_value = {
        AvailabilityZone(root="default"): [model.units["ceph-osd/0"],
                                           model.units["ceph-osd/1"]]
    }

    # verified one ceph-osd unit
    result_success = CephOsd([model.units["ceph-osd/0"]]).check_availability_zone()
    assert result_success == Result(Severity.OK, 'Availability zone check passed.')

    # verified two ceph-osd unit
    result_fail = CephOsd([model.units["ceph-osd/0"],
                           model.units["ceph-osd/1"]]).check_availability_zone()
    expected_msg = "availability zone 'root=default'. [free_units=1, inactive_units=0]"

    assert result_fail.success is False
    assert any((partial.severity == Severity.FAIL and expected_msg in partial.message)
               for partial in result_fail.partials)


@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_ceph_cluster_health",
            return_value=Result(Severity.OK, "Ceph cluster is healthy"))
@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_replication_number",
            return_value=Result(Severity.OK, "Minimum replica number check passed."))
@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_availability_zone",
            return_value=Result(Severity.OK, "Availability zone check passed."))
def test_verify_reboot(
        mock_check_availability_zone,
        mock_check_replication_number,
        mock_check_ceph_cluster_health,
        model
):
    """Test reboot verification on CephOsd."""
    result = CephOsd([model.units["ceph-osd/0"]]).verify_reboot()
    expected_result = Result()
    expected_result.add_partial_result(Severity.OK, "Ceph cluster is healthy")
    expected_result.add_partial_result(Severity.OK,
                                       "Minimum replica number check passed.")
    expected_result.add_partial_result(Severity.OK, "Availability zone check passed.")
    assert result == expected_result
    mock_check_ceph_cluster_health.assert_called_once_with()
    mock_check_replication_number.assert_called_once_with()
    mock_check_availability_zone.assert_called_once_with()


@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_ceph_cluster_health",
            return_value=Result(Severity.OK, "Ceph cluster is healthy"))
@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_replication_number",
            return_value=Result(Severity.OK, "Minimum replica number check passed."))
@mock.patch("juju_verify.verifiers.ceph.CephOsd.check_availability_zone",
            return_value=Result(Severity.OK, "Availability zone check passed."))
def test_verify_shutdown(
        mock_check_availability_zone,
        mock_check_replication_number,
        mock_check_ceph_cluster_health,
        model
):
    """Test shutdown verification on CephOsd."""
    result = CephOsd([model.units["ceph-osd/0"]]).verify_shutdown()
    expected_result = Result()
    expected_result.add_partial_result(Severity.OK, "Ceph cluster is healthy")
    expected_result.add_partial_result(Severity.OK,
                                       "Minimum replica number check passed.")
    expected_result.add_partial_result(Severity.OK, "Availability zone check passed.")
    assert result == expected_result
    mock_check_ceph_cluster_health.assert_called_once_with()
    mock_check_replication_number.assert_called_once_with()
    mock_check_availability_zone.assert_called_once_with()


@pytest.mark.parametrize(
    "action_return_value, expected_result, hostname",
    [('["host0", "host1", "host2"]', Result(True), "host1"),
     ('["host0", "host1"]', Result(False), "host1"),
     ('["host0", "host1", "host2"]', Result(False), None),
     ('["host0", "host1", "host2"]', Result(True), "host5"),
     ],
)
def test_check_ceph_mon_quorum(mocker, action_return_value, expected_result, hostname):
    """Test Ceph quorum verification on CephMon."""
    unit = Unit("ceph-mon/0", Model())
    verifier = CephMon([unit])
    mocker.patch.object(verifier, "run_action_on_all").return_value = {
        "ceph-mon/0": action_return_value,
    }
    unit.machine = mock.Mock(hostname=hostname)
    mocker.patch(
        "juju_verify.verifiers.ceph.data_from_action"
    ).return_value = action_return_value
    result = verifier.check_quorum()
    assert result.success == expected_result.success


def test_verify_ceph_mon_shutdown(mocker):
    """Test that verify_shutdown links to verify_reboot."""
    mocker.patch.object(CephMon, "verify_reboot")
    unit = Unit("ceph-mon/0", Model())
    verifier = CephMon([unit])
    verifier.verify_shutdown()
    verifier.verify_reboot.assert_called_once()


@mock.patch("juju_verify.verifiers.ceph.CephCommon.check_cluster_health")
@mock.patch("juju_verify.verifiers.ceph.CephMon.check_quorum")
def test_verify_ceph_mon_reboot(mock_quorum, mock_health):
    """Test reboot verification on CephMon."""
    unit = Unit("ceph-mon/0", Model())
    mock_health.return_value = Result(True, "Ceph cluster is healthy")
    mock_quorum.return_value = Result(True)
    verifier = CephMon([unit])
    result = verifier.verify_reboot()

    assert result.success
