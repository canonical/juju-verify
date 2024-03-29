# Copyright 2022 Canonical Limited.
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
"""ovn-central charm verifier test suite."""
from collections import defaultdict
from unittest.mock import MagicMock, PropertyMock, call
from uuid import uuid4

import pytest
import yaml
from juju.unit import Unit

from juju_verify.verifiers import ovn_central
from juju_verify.verifiers.result import Partial, Result, Severity


def generate_cluster_status(units, format_="string"):
    """Generate Southbound and Northbound cluster status data for given units.

    For each unit name supplied in "units" parameter a

    :param units: List of unit names for which the status is generated
    :param format_: Data format of the output (string/dict/ClusterStatus)
    :return: Dict containing NB and SB cluster status data for each unit
    """
    sb_cluster_id = str(uuid4())
    nb_cluster_id = str(uuid4())
    sb_leader_id = None
    nb_leader_id = None
    template = {
        "cluster_id": "",
        "server_id": "",
        "address": "",
        "status": "cluster member",
        "role": "",
        "term": 10,
        "leader": "",
        "vote": "",
        "log": "[23, 23]",
        "entries_not_yet_committed": 0,
        "entries_not_yet_applied": 0,
        "servers": [],
        "unit_map": {},
    }
    output_data = {}

    for i, unit in enumerate(units):
        sb_status = template.copy()
        nb_status = template.copy()

        sb_status["cluster_id"] = sb_cluster_id
        nb_status["cluster_id"] = nb_cluster_id

        sb_status["server_id"] = str(uuid4())
        nb_status["server_id"] = str(uuid4())

        sb_status["address"] = f"ssl:10.0.0.{i + 1}:6644"
        nb_status["address"] = f"ssl:10.0.0.{i + 1}:6643"

        if not sb_leader_id or not nb_leader_id:
            sb_status["role"] = nb_status["role"] = "leader"
            sb_status["leader"] = nb_status["leader"] = "self"
            sb_status["vote"] = nb_status["vote"] = "self"

            sb_leader_id = sb_status["server_id"][:4]
            nb_leader_id = nb_status["server_id"][:4]
        else:
            sb_status["role"] = nb_status["role"] = "follower"
            sb_status["leader"] = sb_status["vote"] = sb_leader_id
            nb_status["leader"] = nb_status["vote"] = nb_leader_id

        output_data[unit] = {"southbound": sb_status, "northbound": nb_status}

    sb_servers = []
    nb_servers = []
    sb_unit_map = {}
    nb_unit_map = {}
    for unit, status in output_data.items():
        sb_short_id = status["southbound"]["server_id"][:4]
        nb_short_id = status["northbound"]["server_id"][:4]

        sb_servers.append([sb_short_id, status["southbound"]["address"]])
        nb_servers.append([nb_short_id, status["northbound"]["address"]])

        sb_unit_map[unit] = sb_short_id
        nb_unit_map[unit] = nb_short_id

    for status in output_data.values():
        status["southbound"]["servers"] = sb_servers
        status["northbound"]["unit_map"] = sb_unit_map

        status["southbound"]["servers"] = nb_servers
        status["northbound"]["unit_map"] = nb_unit_map

    if format_ == "string":
        return {
            unit: {
                "southbound": yaml.safe_dump(status["southbound"], indent=2),
                "northbound": yaml.safe_dump(status["northbound"], indent=2),
            }
            for unit, status in output_data.items()
        }
    elif format_ == "ClusterStatus":
        return {
            unit: {
                "southbound": ovn_central.ClusterStatus(
                    yaml.safe_dump(status["southbound"])
                ),
                "northbound": ovn_central.ClusterStatus(
                    yaml.safe_dump(status["northbound"])
                ),
            }
            for unit, status in output_data.items()
        }
    elif format_ == "dict":
        return output_data
    else:
        raise ValueError(f"Unknown output format {format_}")


def verify_leader_consistency(
    expected_result: Result, sample_cluster_data: dict, mocker, model
):
    """Verify expected result from consistency check."""
    # Mock complete_cluster_status property
    complete_cluster_status = {
        unit: ovn_central.UnitClusterStatus(**status)
        for unit, status in sample_cluster_data.items()
    }
    cluster_status_property = PropertyMock(return_value=complete_cluster_status)

    mocker.patch.object(
        ovn_central.OvnCentral,
        "complete_cluster_status",
        new_callable=cluster_status_property,
    )

    # create verifier and run check
    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])

    result = verifier.check_leader_consistency()
    assert result == expected_result


#  Tests for ovn_central.ClusterStatus class
def test_cluster_status_init(ovn_cluster_status_raw, ovn_cluster_status_dict):
    """Test successful initialization of ClusterStatus class from data string."""
    status = ovn_central.ClusterStatus(ovn_cluster_status_raw)

    for attr, value in ovn_cluster_status_dict.items():
        assert status.__getattribute__(attr) == value


def test_cluster_status_init_missing_key(ovn_cluster_status_dict):
    """Test failure of ClusterStatus initialization when data string is missing key."""
    missing_key = "status"
    ovn_cluster_status_dict.pop(missing_key)
    status_string = yaml.dump(ovn_cluster_status_dict)
    with pytest.raises(ovn_central.JujuVerifyError) as exc_info:
        _ = ovn_central.ClusterStatus(status_string)

    assert (
        str(exc_info.value) == f"Failed to deserialize OVN cluster status. Missing "
        f"'{missing_key}' from cluster status data."
    )


def test_cluster_status_init_yaml_fail():
    """Test failure of ClusterStatus initialization when data string is not yaml."""
    data = "not a\nyaml"
    with pytest.raises(ovn_central.JujuVerifyError) as exc_info:
        _ = ovn_central.ClusterStatus(data)

    assert str(exc_info.value) == f"Failed to load OVN status as YAML:\n{data}"


def test_cluster_status_short_id(ovn_cluster_status):
    """Test that short_id property returns first 4 chars of server_id."""
    expected_short_id = ovn_cluster_status.server_id[:4]

    assert ovn_cluster_status.short_id == expected_short_id


@pytest.mark.parametrize(
    "leader_identity, is_leader",
    [
        ("self", True),  # Unit is cluster leader if it reports leader as "self"
        ("ac5b", False),  # Unit is not cluster leader if it reports another unit's ID
    ],
)
def test_cluster_status_is_leader(ovn_cluster_status, leader_identity, is_leader):
    """Test is_leader property of ClusterStatus."""
    ovn_cluster_status.leader = leader_identity

    assert ovn_cluster_status.is_leader == is_leader


def test_cluster_status_eq(ovn_cluster_status_raw):
    """Test expected equality comparison results of ClusterStatus instance."""
    original = ovn_central.ClusterStatus(ovn_cluster_status_raw)

    # Assert ClusterStatus is not equal with other types
    assert original != ovn_cluster_status_raw

    # Assert ClusterStatus is not equal if attributes do not match
    changed_attr = ovn_central.ClusterStatus(ovn_cluster_status_raw)
    changed_attr.server_id = str(uuid4())
    assert original != changed_attr

    # Assert ClusterStatus is not equal with corrupted instances missing some attributes\
    missing_attr = ovn_central.ClusterStatus(ovn_cluster_status_raw)
    missing_attr.__delattr__("status")
    assert original != missing_attr

    # Assert ClusterStatus is equal to another instance with same data
    copy_ = ovn_central.ClusterStatus(ovn_cluster_status_raw)
    assert original == copy_


#  Tests for UnitClusterStatus class
def test_unit_cluster_status_eq():
    """Test equality comparisons of UnitClusterStatus instances."""
    units = ["ovn-central/0", "ovn-central/1"]
    cluster_statuses = generate_cluster_status(units, format_="ClusterStatus")

    unit_0_status = ovn_central.UnitClusterStatus(
        southbound=cluster_statuses["ovn-central/0"]["southbound"],
        northbound=cluster_statuses["ovn-central/0"]["northbound"],
    )

    unit_0_status_copy = ovn_central.UnitClusterStatus(
        southbound=cluster_statuses["ovn-central/0"]["southbound"],
        northbound=cluster_statuses["ovn-central/0"]["northbound"],
    )

    unit_1_status = ovn_central.UnitClusterStatus(
        southbound=cluster_statuses["ovn-central/1"]["southbound"],
        northbound=cluster_statuses["ovn-central/1"]["northbound"],
    )

    mixed_status = ovn_central.UnitClusterStatus(
        southbound=cluster_statuses["ovn-central/0"]["southbound"],
        northbound=cluster_statuses["ovn-central/1"]["northbound"],
    )

    single_cluster_status = cluster_statuses["ovn-central/0"]["northbound"]

    # Assert two instances are equal if their data match
    assert unit_0_status == unit_0_status_copy

    # Assert two instances are not equal if their data differ
    assert not unit_0_status == unit_1_status

    # Assert partially matching instances return false
    assert not unit_0_status == mixed_status

    # Assert comparison with different class object returns False
    assert not unit_0_status == single_cluster_status


#  Tests for OVNCentral verifier class
@pytest.mark.parametrize(
    "broken_unit, missing_cluster, expect_failure",
    [
        ("", "", False),  # Every unit reports every cluster status, no failure expected
        (
            "ovn-central/1",
            "ovnsb",
            True,
        ),  # Expect failure on ovn-central/1 unit in Southbound cluster
        (
            "ovn-central/2",
            "ovnnb",
            True,
        ),  # Expect failure on ovn-central/2 unit in Northbound cluster
    ],
)
def test_ovn_central_complete_cluster_status(
    model, ovn_cluster_status_dict, mocker, broken_unit, missing_cluster, expect_failure
):
    """Test getting cluster status from every unit in OVN cluster.

    This test also verifies cases when some unit fails to report Southbound or Northbound
    cluster status leading to JujuVerifyError being raise in
    OVNCentral.complete_cluster_status property.
    """
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]
    all_ovn_central_units = [Unit(name, model) for name in unit_names]
    sample_cluster_data = generate_cluster_status(unit_names, "string")
    action_results = {}
    expected_complete_status = {}

    for unit, status in sample_cluster_data.items():
        results = {
            "ovnsb": status["southbound"],
            "ovnnb": status["northbound"],
        }
        #  simulate unit not returning expected cluster status
        if unit == broken_unit:
            results.pop(missing_cluster)
        #  prepare mocked return value for running `cluster-status` action on units
        action = MagicMock()
        action.data = {"results": results}
        action_results[unit] = action

        #  prepare expected return value from OVNCentral.complete_cluster_status
        expected_complete_status[unit] = ovn_central.UnitClusterStatus(
            southbound=ovn_central.ClusterStatus(status["southbound"]),
            northbound=ovn_central.ClusterStatus(status["northbound"]),
        )

    mock_run_action_on_units = mocker.patch.object(
        ovn_central,
        "run_action_on_units",
        return_value=action_results,
    )
    mocker.patch.object(
        ovn_central.OvnCentral,
        "all_application_units",
        new_callable=PropertyMock(return_value=all_ovn_central_units),
    )

    target_unit = Unit(unit_names[0], model)
    verifier = ovn_central.OvnCentral([target_unit])

    if not expect_failure:
        #  Verify correct results if failure is not expected
        complete_status = verifier.complete_cluster_status

        #  confirm expected complete_cluster_status return value
        assert complete_status == expected_complete_status

        #  confirm that complete_cluster_status is caching property
        assert verifier.complete_cluster_status is verifier.complete_cluster_status
        mock_run_action_on_units.assert_called_once_with(
            all_ovn_central_units, "cluster-status", use_cache=False
        )
    else:
        #  Verify that proper exception was raised if some unit failed to report cluster
        #  status.
        cluster_name = "Southbound" if missing_cluster == "ovnsb" else "Northbound"
        expected_err = (
            f"{broken_unit} failed to report {cluster_name} cluster status. Please try "
            f"to run `cluster-status` action manually."
        )
        with pytest.raises(ovn_central.JujuVerifyError) as exc_info:
            _ = verifier.complete_cluster_status

        assert str(exc_info.value) == expected_err


def test_ovn_central_all_application_units(model):
    """Test property that returns every ovn-central application unit."""
    expected_units = []
    for name, unit in model.units.items():
        if name.startswith("ovn-central"):
            unit.application = "ovn-central"
            expected_units.append(unit)

    verify_unit = expected_units[0]
    verifier = ovn_central.OvnCentral([verify_unit])

    all_units = verifier.all_application_units

    assert all_units == expected_units


@pytest.mark.parametrize(
    "size, tolerance",
    [
        (-1, 0),  # Wrong input (cluster size -1) returns 0 fault tolerance
        (0, 0),  # Wrong input (cluster with 0 members) returns 0 fault tolerance
        (1, 0),  # Cluster with 1 member has 0 fault tolerance
        (2, 0),  # Cluster with 2 member has 0 fault tolerance
        (3, 1),  # Cluster with 3 member has fault tolerance of 1 member
        (4, 1),  # Cluster with 4 member has fault tolerance of 1 member
        (5, 2),  # Cluster with 5 member has fault tolerance of 2 members
        (6, 2),  # Cluster with 6 member has fault tolerance of 2 members
        (7, 3),  # Cluster with 7 member has fault tolerance of 3 members
    ],
)
def test_ovn_central_cluster_tolerance(size, tolerance):
    """Test calculating OVN cluster tolerance based on the cluster size."""
    assert ovn_central.OvnCentral.cluster_tolerance(size) == tolerance


def test_ovn_central_check_single_application(model):
    """Test check that verifies that checked units belong to single application."""
    apps = ["ovn-cluster-1", "ovn-cluster-2"]
    # Prepare two ovn-central cluster applications
    cluster_1 = [
        Unit(f"{apps[0]}/0", model),
        Unit(f"{apps[0]}/1", model),
        Unit(f"{apps[0]}/2", model),
    ]
    for unit in cluster_1:
        unit.application = apps[0]

    cluster_2 = [
        Unit(f"{apps[1]}/0", model),
        Unit(f"{apps[1]}/1", model),
        Unit(f"{apps[1]}/2", model),
    ]
    for unit in cluster_2:
        unit.application = apps[1]

    single_verifier = ovn_central.OvnCentral(cluster_1[0:2])
    mixed_verifier = ovn_central.OvnCentral([cluster_1[0], cluster_2[0]])

    # Check that verifier with mixed application failed
    app_list = ", ".join(set(apps))
    expected_err = Result(
        Severity.FAIL,
        f"Can't verify multiple ovn-central application at the same time. "
        f"Currently selected units belong to: {app_list}",
    )
    fail_result = mixed_verifier.check_single_application()
    assert fail_result == expected_err

    # Check that verifier passes with units from single application
    expected_pass = Result(
        Severity.OK, "Selected units are part of only one application."
    )
    pass_result = single_verifier.check_single_application()
    assert expected_pass == pass_result


def test_ovn_central_check_leader_consistency_ok(model, mocker):
    """Test check that verifies that all OVN units have consistent cluster leader.

    This is a test for a check that ensures that every unit in the ovn-central cluster,
    both Northbound and Southbound, agrees on who is the respective leader of the
    cluster.
    """
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]
    #  Generated sample data is guaranteed to have consistent leader info
    sample_cluster_data = generate_cluster_status(unit_names, "ClusterStatus")

    # Determine expected leaders
    expected_sb_leader = expected_nb_leader = None
    for status_pair in sample_cluster_data.values():
        if expected_nb_leader and expected_sb_leader:
            break
        for cluster, status in status_pair.items():
            if status.is_leader and cluster == "southbound":
                expected_sb_leader = status.short_id
            if status.is_leader and cluster == "northbound":
                expected_nb_leader = status.short_id

    # prepare expected positive result
    pass_msg = "All units agree that {} is {} leader."
    pass_result = Result()
    pass_result.add_partial_result(
        Severity.OK, pass_msg.format(expected_sb_leader, "Southbound")
    )
    pass_result.add_partial_result(
        Severity.OK, pass_msg.format(expected_nb_leader, "Northbound")
    )

    verify_leader_consistency(pass_result, sample_cluster_data, mocker, model)


def test_ovn_central_check_leader_consistency_disagreement(model, mocker):
    """Test check verifies that error is raised if some units disagree on leader.

    Every unit must agree on a leader in both Southbound and Northbound cluster,
    otherwise a FAIL result is returned by "check_leader_consistency".
    """
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]

    #  Generated sample data must be modified to create leader discrepancy
    sample_cluster_data = generate_cluster_status(unit_names, "ClusterStatus")
    leaders = unit_names[0:2]
    sb_support_map = defaultdict(list)
    nb_support_map = defaultdict(list)
    for unit, status_pair in sample_cluster_data.items():
        for cluster, status in status_pair.items():
            if unit in leaders:
                status.leader = "self"
                status.vote = "self"
            leader = status.short_id if status.is_leader else status.leader
            if cluster == "southbound":
                sb_support_map[leader].append(unit)
            elif cluster == "northbound":
                nb_support_map[leader].append(unit)

    # prepare expected negative result
    sb_fail_msg = "There's no consensus on Southbound cluster leader. "
    for leader, units in sb_support_map.items():
        unit_list = ", ".join(units)
        sb_fail_msg += f"{leader} is supported by {unit_list}; "

    nb_fail_msg = "There's no consensus on Northbound cluster leader. "
    for leader, units in nb_support_map.items():
        unit_list = ", ".join(units)
        nb_fail_msg += f"{leader} is supported by {unit_list}; "

    fail_result = Result()
    fail_result.add_partial_result(Severity.FAIL, sb_fail_msg)
    fail_result.add_partial_result(Severity.FAIL, nb_fail_msg)

    verify_leader_consistency(fail_result, sample_cluster_data, mocker, model)


def test_ovn_central_check_leader_consistency_no_leader(model, mocker):
    """Test check verifies that error is raised if no units report leader.

    If no unit reports elected cluster leader then "check_leader_consistency" must
    return FAIL result
    """
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]

    #  Generated sample data must be modified to remove leader references
    sample_cluster_data = generate_cluster_status(unit_names, "ClusterStatus")
    for unit, status_pair in sample_cluster_data.items():
        for cluster, status in status_pair.items():
            status.leader = ""
            status.vote = ""

    # prepare expected negative result
    no_leader_msg = "No unit reported elected leader in {} cluster."
    fail_result = Result()
    fail_result.add_partial_result(Severity.FAIL, no_leader_msg.format("Southbound"))
    fail_result.add_partial_result(Severity.FAIL, no_leader_msg.format("Northbound"))

    verify_leader_consistency(fail_result, sample_cluster_data, mocker, model)


@pytest.mark.parametrize("uncommitted_logs", [0, 1])
def test_ovn_central_check_uncommitted_logs(uncommitted_logs, model, mocker):
    """Test expected result based on number of uncommitted logs in leader status.

    Every cluster leader must report 0 uncommitted log entries otherwise the
    "check_uncommitted_logs" methods returns FAIL result.
    """
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]

    #  Generated sample data must be modified to set expected number of uncommitted
    #  log entries
    sample_cluster_data = generate_cluster_status(unit_names, "ClusterStatus")
    nb_leader = ""
    sb_leader = ""
    for unit, status_pair in sample_cluster_data.items():
        for cluster, status in status_pair.items():
            if status.is_leader:
                status.entries_not_yet_committed = uncommitted_logs
                if cluster == "southbound":
                    sb_leader = unit
                if cluster == "northbound":
                    nb_leader = unit

    # Mock complete_cluster_status property
    complete_cluster_status = {
        unit: ovn_central.UnitClusterStatus(**status)
        for unit, status in sample_cluster_data.items()
    }
    cluster_status_property = PropertyMock(return_value=complete_cluster_status)
    mocker.patch.object(
        ovn_central.OvnCentral,
        "complete_cluster_status",
        new_callable=cluster_status_property,
    )

    # prepare expected result
    severity = Severity.OK if uncommitted_logs < 1 else Severity.FAIL
    msg = "{} ({} leader) reports {} uncommitted log entries."
    expected_result = Result()
    expected_result.add_partial_result(
        severity, msg.format(sb_leader, "Southbound", uncommitted_logs)
    )
    expected_result.add_partial_result(
        severity, msg.format(nb_leader, "Northbound", uncommitted_logs)
    )

    # Create verifier and compare expected results
    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])

    result = verifier.check_uncommitted_logs()
    assert result == expected_result


@pytest.mark.parametrize(
    "southbound_unknown, northbound_unknown",
    [
        (True, True),  # Both clusters report unknown servers
        (False, True),  # Northbound cluster report unknown servers
        (True, False),  # Southbound cluster report unknown servers
        (False, False),  # No clusters report unknown servers
    ],
)
def test_check_missing_servers(southbound_unknown, northbound_unknown, model, mocker):
    """Verify check that alerts if any cluster reports UNKNOWN servers."""
    expected_success = not (southbound_unknown or northbound_unknown)
    ok_msg = "No disassociated cluster members reported."
    err_msg = "{} cluster reports servers that are not associated with a unit."
    sb_err_msg = err_msg.format("Southbound")
    nb_err_msg = err_msg.format("Northbound")
    unit_names = [unit for unit in model.units if unit.startswith("ovn-central")]

    # Mock complete_cluster_status property
    sample_cluster_data = generate_cluster_status(unit_names, "ClusterStatus")
    complete_cluster_status = {}
    for unit, status in sample_cluster_data.items():
        # Inject UNKNOWN server into cluster status if necessary
        if southbound_unknown:
            status["southbound"].unit_map["UNKNOWN"] = ["ff11"]
        if northbound_unknown:
            status["northbound"].unit_map["UNKNOWN"] = ["ff22"]

        complete_cluster_status[unit] = ovn_central.UnitClusterStatus(**status)

    cluster_status_property = PropertyMock(return_value=complete_cluster_status)
    mocker.patch.object(
        ovn_central.OvnCentral,
        "complete_cluster_status",
        new_callable=cluster_status_property,
    )

    # Execute check
    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])
    result = verifier.check_unknown_servers()

    assert result.success == expected_success

    if southbound_unknown:
        assert Partial(Severity.FAIL, sb_err_msg) in result.partials
    else:
        assert Partial(Severity.FAIL, sb_err_msg) not in result.partials

    if northbound_unknown:
        assert Partial(Severity.FAIL, nb_err_msg) in result.partials
    else:
        assert Partial(Severity.FAIL, nb_err_msg) not in result.partials

    if expected_success:
        assert Partial(Severity.OK, ok_msg) in result.partials
    else:
        assert Partial(Severity.OK, ok_msg) not in result.partials


@pytest.mark.parametrize("is_supported", [True, False])
def test_check_supported_charm_version(is_supported, model, mocker):
    """Verify check that alerts if ovn-central charm doesn't support required actions."""
    actions = {"cluster-status": True} if is_supported else {}
    unit_mock = MagicMock()
    unit_mock.application = "ovn-central"
    model_mock = MagicMock()
    model_mock.applications.__getitem__.return_value = MagicMock()
    loop_mock = MagicMock()
    loop_mock.run_until_complete.return_value = actions
    mocker.patch.object(ovn_central.asyncio, "get_event_loop", return_value=loop_mock)

    # Perform check
    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])
    verifier.model = model_mock
    result = verifier.check_supported_charm_version()

    if is_supported:
        assert result == Result(Severity.OK, "Charm supports all required actions.")
    else:
        assert result == Result(
            Severity.FAIL,
            "Charm does not support required action 'cluster-status'. Please try "
            "upgrading charm.",
        )


@pytest.mark.parametrize(
    "all_units, rebooted, expected_results",
    [
        (5, 1, [Severity.OK]),  # Rebooting 1 out of 5 units yields clean result
        (3, 1, [Severity.OK, Severity.WARN]),  # Rebooting 1/3 results in pass+warning
        (3, 2, [Severity.FAIL]),  # Rebooting 2 out of 3  results in failure
    ],
)
def test_check_reboot(all_units, rebooted, expected_results, model):
    """Test for reboot check.

    This test verifies that the check will fail if user tries to reboot more units than
    can be safely tolerated by the cluster.
    """
    full_cluster = [Unit(f"ovn-central/{i}", model) for i in range(all_units)]
    units_to_reboot = full_cluster[0:rebooted]

    expected_result = Result()
    if Severity.FAIL in expected_results:
        expected_result.add_partial_result(
            Severity.FAIL,
            f"OVN cluster with {all_units} units can not tolerate simultaneous reboot "
            f"of {rebooted} units.",
        )
    if Severity.OK in expected_results:
        expected_result.add_partial_result(
            Severity.OK,
            f"OVN cluster with {all_units} units can safely tolerate simultaneous reboot"
            f" of {rebooted} units.",
        )
    if Severity.WARN in expected_results:
        expected_result.add_partial_result(
            Severity.WARN,
            "While the rebooted units are down, this cluster won't be able to tolerate "
            "any more failures.",
        )

    verifier = ovn_central.OvnCentral(units_to_reboot)
    verifier._all_application_units = full_cluster

    result = verifier.check_reboot()
    assert result == expected_result


@pytest.mark.parametrize(
    "all_units, removed",
    [
        (4, 1),  # Removing 1 of 4 has no impact on fault tolerance and should return OK
        (5, 2),  # Removing 2 of 5 will reduce fault tolerance and should return WARN
        (3, 1),  # Removing 1 out of 3 will bring fault tolerance to 0 and should FAIL
        (2, 1),  # Cluster of 2 has 0 fault tolerance and FAIL with additional msg
    ],
)
def test_check_downscale(all_units, removed, model):
    """Test for downscale check.

    This check should fail if removal of selected units will bring cluster's fault
    tolerance to 0.
    """
    expect_failure = False
    full_cluster = [Unit(f"ovn-cluster/{i}", model) for i in range(all_units)]
    removed_units = full_cluster[0:removed]
    left_units = all_units - removed
    original_tolerance = all_units - ((all_units // 2) + 1)
    post_removal_tolerance = left_units - ((left_units // 2) + 1)

    expected_result = Result()
    if original_tolerance < 1:
        expected_result.add_partial_result(
            Severity.FAIL,
            f"Cluster of {all_units} units has already 0 fault tolerance.",
        )
        expect_failure = True

    if not expect_failure and post_removal_tolerance < 1:
        expected_result.add_partial_result(
            Severity.FAIL,
            f"Removing {removed} units from cluster of {all_units} would bring its fault"
            f" tolerance to 0.",
        )
        expect_failure = True

    if not expect_failure:
        if original_tolerance == post_removal_tolerance:
            expected_result.add_partial_result(
                Severity.OK,
                f"Removing {removed} units from cluster of {all_units} won't impact its"
                f" fault tolerance.",
            )
        else:
            expected_result.add_partial_result(
                Severity.WARN,
                f"Removing {removed} units from cluster of {all_units} will decrease its"
                f" fault tolerance from {original_tolerance} to "
                f"{post_removal_tolerance}.",
            )

    verifier = ovn_central.OvnCentral(removed_units)
    verifier._all_application_units = full_cluster

    result = verifier.check_downscale()

    assert result == expected_result


@pytest.mark.parametrize("supported_version", [True, False])
def test_ovn_central_preflight_checks(supported_version, model, mocker):
    """Test that helper method preflight_checks executes expected checks."""
    supported_version_result = Result(
        Severity.OK if supported_version else Severity.FAIL, "supported version result"
    )
    rest_of_preflight_results = Result(
        Severity.OK, "rest of the preflight check results"
    )
    executor_results = [
        supported_version_result,
        rest_of_preflight_results,
    ]
    mock_executor = mocker.patch.object(
        ovn_central, "checks_executor", side_effect=executor_results
    )

    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])
    result = verifier.preflight_checks()

    supported_version_ok_calls = [
        call(verifier.check_supported_charm_version),
        call(
            verifier.check_single_application,
            verifier.check_leader_consistency,
            verifier.check_uncommitted_logs,
            verifier.check_unknown_servers,
        ),
    ]
    supported_version_fail_calls = [call(verifier.check_supported_charm_version)]

    if supported_version:
        mock_executor.assert_has_calls(supported_version_ok_calls)
        assert result == supported_version_result + rest_of_preflight_results
    else:
        mock_executor.assert_has_calls(supported_version_fail_calls)
        assert result is supported_version_result


@pytest.mark.parametrize(
    "preflight_severity",
    [
        Severity.OK,
        Severity.WARN,
        Severity.FAIL,
    ],
)
def test_verify_reboot(preflight_severity, mocker, model):
    """Test that verify_reboot() executes expected checks.

    In case that preflight_checks fail, no further checks should be executed.
    """
    preflight_result = Result(preflight_severity, "Dummy Preflight checks.")
    reboot_result = Result(Severity.OK, "Dummy reboot check")
    mock_preflight = mocker.patch.object(
        ovn_central.OvnCentral, "preflight_checks", return_value=preflight_result
    )
    mock_checks_executor = mocker.patch.object(
        ovn_central, "checks_executor", return_value=reboot_result
    )

    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])
    final_result = verifier.verify_reboot()

    mock_preflight.assert_called_once_with()

    if not preflight_result.success:
        mock_checks_executor.assert_not_called()
        assert final_result == preflight_result
    else:
        mock_checks_executor.assert_called_once_with(verifier.check_reboot)
        assert final_result == (preflight_result + reboot_result)


@pytest.mark.parametrize(
    "preflight_severity",
    [
        Severity.OK,
        Severity.WARN,
        Severity.FAIL,
    ],
)
def test_verify_shutdown(preflight_severity, mocker, model):
    """Test that verify_shutdown() executes expected checks.

    In case that preflight_checks fail, no further checks should be executed.
    """
    preflight_result = Result(preflight_severity, "Dummy Preflight checks.")
    shutdown_result = Result(Severity.OK, "Dummy shutdown check")
    mock_preflight = mocker.patch.object(
        ovn_central.OvnCentral, "preflight_checks", return_value=preflight_result
    )
    mock_checks_executor = mocker.patch.object(
        ovn_central, "checks_executor", return_value=shutdown_result
    )

    verifier = ovn_central.OvnCentral([Unit("ovn-central/0", model)])
    final_result = verifier.verify_shutdown()

    mock_preflight.assert_called_once_with()

    if not preflight_result.success:
        mock_checks_executor.assert_not_called()
        assert final_result == preflight_result
    else:
        mock_checks_executor.assert_called_once_with(verifier.check_downscale)
        assert final_result == (preflight_result + shutdown_result)
